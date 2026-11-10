"""Theta Edge Node keystore: locate, read, decrypt and verify a web3 v3 keystore.

The node's internal wallet is created by the Edge Node app. Its keystore lives
under the app's data folder on Windows and under ~/.edgelauncher on Docker.
This module never logs or persists a private key.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
import uuid
from pathlib import Path
from typing import Any

from Crypto.Hash import keccak
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

CURVE_N = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141
ADDRESS_RE = re.compile(r"^0x[0-9a-fA-F]{40}$")
STEM_RE = re.compile(r"^[0-9a-fA-F]{40}$")


class KeystoreError(ValueError):
    """A user-correctable keystore error. Messages are safe to show in the pane."""


def _keccak(data: bytes) -> str:
    return keccak.new(digest_bits=256, data=data).hexdigest()


def private_key_to_address(private_key: bytes) -> str:
    if len(private_key) != 32:
        raise KeystoreError("private key must be 32 bytes")
    value = int.from_bytes(private_key, "big")
    if not 1 <= value < CURVE_N:
        raise KeystoreError("private key is outside the secp256k1 range")
    key = ec.derive_private_key(value, ec.SECP256K1())
    numbers = key.public_key().public_numbers()
    uncompressed = b"\x04" + numbers.x.to_bytes(32, "big") + numbers.y.to_bytes(32, "big")
    digest = keccak.new(digest_bits=256, data=uncompressed[1:]).digest()
    return "0x" + digest[-20:].hex()


def keystore_dir() -> Path:
    override = os.environ.get("THETA_KEYSTORE_DIR")
    if override:
        return Path(override)
    appdata = Path(os.environ.get("APPDATA", ""))
    profile = Path(os.environ.get("USERPROFILE", ""))
    candidates = [
        appdata / "Theta Edge Node" / "ThetaEdgeNode" / "edgecore" / "key" / "encrypted",
        appdata / "Theta Edge Node" / "edgecore" / "key" / "encrypted",
        profile / ".edgelauncher" / "edgecore" / "key" / "encrypted",
    ]
    for candidate in candidates:
        if candidate.is_dir():
            return candidate
    return candidates[0]


def _normalize_address(value: str) -> str:
    cleaned = str(value or "").strip()
    if cleaned.startswith(("0x", "0X")):
        cleaned = cleaned[2:]
    if not STEM_RE.match(cleaned):
        raise KeystoreError("invalid Theta address")
    return "0x" + cleaned.lower()


def read_keystore(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise KeystoreError(f"cannot read keystore: {exc}") from exc
    if not isinstance(data, dict):
        raise KeystoreError("keystore is not a JSON object")
    crypto = data.get("crypto") or data.get("Crypto")
    if not isinstance(crypto, dict):
        raise KeystoreError("keystore has no crypto section")
    return data


def keystore_address(path: Path) -> str:
    try:
        data = read_keystore(path)
        address = data.get("address")
        if address:
            return _normalize_address(str(address))
    except KeystoreError:
        pass
    if STEM_RE.match(path.name):
        return "0x" + path.name.lower()
    raise KeystoreError("keystore address is missing")


def latest_keystore() -> Path | None:
    directory = keystore_dir()
    if not directory.is_dir():
        return None
    candidates: list[Path] = []
    for entry in directory.iterdir():
        try:
            if not entry.is_file() or entry.stat().st_size > 5_000_000:
                continue
            read_keystore(entry)
            candidates.append(entry)
        except (OSError, KeystoreError):
            continue
    if not candidates:
        return None
    return max(candidates, key=lambda path: path.stat().st_mtime)


def decrypt_keystore(blob: dict[str, Any], password: str) -> bytes:
    crypto = blob.get("crypto") or blob.get("Crypto")
    if not isinstance(crypto, dict):
        raise KeystoreError("keystore has no crypto section")
    if not password:
        raise KeystoreError("password is required")

    kdf = str(crypto.get("kdf") or "scrypt").lower()
    params = crypto.get("kdfparams") or {}
    password_bytes = password.encode("utf-8")
    try:
        if kdf == "scrypt":
            n = int(params.get("n") or 262144)
            r = int(params.get("r") or 8)
            p = int(params.get("p") or 1)
            dklen = int(params.get("dklen") or 32)
            salt = bytes.fromhex(str(params.get("salt") or ""))
            maxmem = max(128 * n * r + 16 * 1024 * 1024, 64 * 1024 * 1024)
            derived = hashlib.scrypt(
                password_bytes, salt=salt, n=n, r=r, p=p, dklen=dklen, maxmem=maxmem
            )
        elif kdf == "pbkdf2":
            iterations = int(params.get("c") or 262144)
            dklen = int(params.get("dklen") or 32)
            salt = bytes.fromhex(str(params.get("salt") or ""))
            derived = hashlib.pbkdf2_hmac("sha256", password_bytes, salt, iterations, dklen)
        else:
            raise KeystoreError(f"unsupported keystore KDF: {kdf}")

        cipher_name = str(crypto.get("cipher") or "aes-128-ctr").lower()
        if cipher_name != "aes-128-ctr":
            raise KeystoreError(f"unsupported keystore cipher: {cipher_name}")
        iv = bytes.fromhex(str((crypto.get("cipherparams") or {}).get("iv") or ""))
        ciphertext = bytes.fromhex(str(crypto.get("ciphertext") or ""))
        mac = str(crypto.get("mac") or "").lower().removeprefix("0x")
    except (TypeError, ValueError) as exc:
        raise KeystoreError("keystore parameters are malformed") from exc

    expected_mac = _keccak(derived[16:32] + ciphertext)
    if mac != expected_mac:
        raise KeystoreError("wrong password or corrupt keystore")

    decryptor = Cipher(algorithms.AES(derived[:16]), modes.CTR(iv)).decryptor()
    private_key = decryptor.update(ciphertext) + decryptor.finalize()
    if len(private_key) != 32:
        raise KeystoreError("decrypted key has the wrong length")

    address = blob.get("address")
    if address and private_key_to_address(private_key).lower() != _normalize_address(str(address)):
        raise KeystoreError("keystore address does not match the decrypted key")
    return private_key


def encrypt_keystore(private_key: bytes, password: str, n: int = 2**15) -> dict[str, Any]:
    """Create a standard web3 v3 keystore. Used by tests and by the export path."""
    if len(password) < 8:
        raise KeystoreError("password must be at least 8 characters")
    address = private_key_to_address(private_key)
    salt = os.urandom(32)
    iv = os.urandom(16)
    maxmem = max(128 * n * 8 + 16 * 1024 * 1024, 64 * 1024 * 1024)
    derived = hashlib.scrypt(
        password.encode("utf-8"), salt=salt, n=n, r=8, p=1, dklen=32, maxmem=maxmem
    )
    encryptor = Cipher(algorithms.AES(derived[:16]), modes.CTR(iv)).encryptor()
    ciphertext = encryptor.update(private_key) + encryptor.finalize()
    mac = _keccak(derived[16:32] + ciphertext)
    return {
        "version": 3,
        "id": uuid.uuid4().hex,
        "address": address[2:],
        "crypto": {
            "cipher": "aes-128-ctr",
            "cipherparams": {"iv": iv.hex()},
            "ciphertext": ciphertext.hex(),
            "kdf": "scrypt",
            "kdfparams": {"dklen": 32, "n": n, "r": 8, "p": 1, "salt": salt.hex()},
            "mac": mac,
        },
    }


def downloads_dir() -> Path:
    override = os.environ.get("THETA_DOWNLOADS_DIR")
    if override:
        return Path(override)
    return Path(os.environ.get("USERPROFILE", "")) / "Downloads"


def scan_downloads(max_age_days: int = 7) -> dict[str, Any] | None:
    """Find the newest keystore-looking JSON in Downloads. Never reads key material."""
    directory = downloads_dir()
    if not directory.is_dir():
        return None
    cutoff = time.time() - max_age_days * 86400
    candidates: list[tuple[float, Path, str]] = []
    for entry in directory.iterdir():
        try:
            if not entry.is_file() or entry.stat().st_size > 5_000_000:
                continue
            if entry.stat().st_mtime < cutoff:
                continue
            blob = read_keystore(entry)
            address = keystore_address(entry)
            candidates.append((entry.stat().st_mtime, entry, address))
        except (OSError, KeystoreError):
            continue
        _ = blob  # read_keystore already validated the shape
    if not candidates:
        return None
    modified, path, address = max(candidates, key=lambda row: row[0])
    return {"path": str(path), "address": address, "modified": int(modified)}
