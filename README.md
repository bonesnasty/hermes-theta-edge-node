# Theta Edge Node for Hermes Desktop

A Hermes Desktop plugin that runs and monitors a Theta Edge Node from a left-hand pane.

> Built for the Nous Research Hermes Agent Plugin Hackathon (Nov 2026).
> Not affiliated with or endorsed by Theta Labs.

## What it does

- **Node** — first-run setup downloads the official Theta Edge Node installer, verifies its
  Authenticode signature and SHA-256, installs it, and launches it. After that: launch, stop,
  reinstall/update, version, holder address, sync/peer status, pending/paid TFUEL rewards, a
  7-day rewards sparkline, offline notification, node logs and a **Copy diagnostics** button.
- **Wallet** — reads the Edge Node's own internal wallet (the wallet the app creates and funds
  with Cache/Compute rewards). Shows the address, liquid TFUEL balance and USD value. Exports the
  wallet two ways: the app's **Info → Export Wallet as Keystore** flow (recommended, with a
  verify step), or an advanced in-Hermes decrypt with the node password.
- **Agent tools** — `theta_node_status` and `theta_wallet_address`, both read-only. They never
  return a private key.

The pane is Theta-skinned: dark navy surface, cyan-to-green gradient, text wordmark. The pane tab
strip and sash remain native Hermes chrome.

## Requirements

- Windows 10/11. The Edge Node app is Windows/macOS; this plugin targets the Windows build.
- Hermes Desktop 0.21.5 or newer.
- The Edge Node's minimum hardware: 4 CPU cores, 16 GB RAM, 64 GB free disk (256 GB+ recommended).
  A CUDA GPU is optional.

## Install

From the catalog after the entry is merged:

```bash
hermes plugins install theta-edge-node
```

From this repo:

```bash
hermes plugins install https://github.com/bonesnasty/hermes-theta-edge-node
```

Then open **Capabilities → Plugins** and enable **Theta Edge Node**. The desktop half of a
unified package is opt-in; without that toggle the pane does not appear.

The first time the pane opens, it asks before downloading the ~230 MB installer. Nothing is
downloaded or executed at plugin install time.

## How it reads the node

- Local RPC: `http://127.0.0.1:15888/rpc` (`edgelauncher.GetPastJobs`) and
  `http://127.0.0.1:17888/rpc` (`edgecore.GetVersion`, `GetStatus`, `GetPeers`,
  `GetEdgeNodeSummary`).
- Node wallet keystore: `%APPDATA%\Theta Edge Node\ThetaEdgeNode\edgecore\key\encrypted`
  (also checks `%APPDATA%\Theta Edge Node\edgecore\key\encrypted` and
  `%USERPROFILE%\.edgelauncher\edgecore\key\encrypted`).
- TFUEL balance: `https://eth-rpc-api.thetatoken.org/rpc` (`eth_getBalance`, chain 361).
- USD price: `https://api.coingecko.com/api/v3/simple/price?ids=theta-fuel&vs_currencies=usd`.

If the Windows build does not expose the local RPC ports, the pane shows process and keystore
state and says the RPC is offline. It does not invent reward numbers.

## Security and privacy

**Network calls**

| Destination | Purpose |
|---|---|
| `https://theta-mkt-api.thetatoken.org/v1/downloads/edge-node/windows` | Official installer download, user-initiated |
| `https://s3.us-east-2.amazonaws.com/assets.thetatoken.org/...` | Installer redirect target; host is allowlisted |
| `https://eth-rpc-api.thetatoken.org/rpc` | Public TFUEL balance read |
| `https://api.coingecko.com/api/v3/simple/price` | Public TFUEL/USD price |
| `http://127.0.0.1:15888` / `:17888` | Local Edge Node RPC |

**Data that leaves the machine:** the public node wallet address in balance and price queries.
No private key, no telemetry, no analytics, no LLM calls.

**Local state:** `%LOCALAPPDATA%\hermes\plugin-data\theta-edge-node\` (download progress, settings),
`downloads\ThetaEdgeNodeSetup.exe`, and `verify_signature.ps1`. The node keystore is read in place
and never copied by the plugin.

**Processes:** the plugin starts the downloaded installer and `Theta Edge Node.exe` only after an
explicit click. `Stop node` runs `taskkill /IM "Theta Edge Node.exe" /F`. No `shell=True`, no
user-controlled command strings.

**Private key handling:** the recommended export path uses the Edge Node app's own keystore
export; the plugin only verifies the exported file's address. The advanced path decrypts the node
keystore in memory with the node password, is loopback-only, rate-limits failures, and returns the
key only to the local pane. There is no agent tool for export, and the key is never logged.

**Installer trust:** the download must end on an allowlisted HTTPS host; the installer must carry
a valid Authenticode signature with a Theta-looking signer subject. The SHA-256 is shown in the
pane. The installer is never bundled in this repository.

## Legal / IP

- This plugin is **not affiliated with or endorsed by Theta Labs**.
- The Edge Node desktop app is distributed as a binary installer. This repository does **not**
  bundle, redistribute, repackage or reverse-engineer it. The installer is downloaded at runtime
  from Theta's official endpoint.
- No Theta icons, fonts or screenshots are shipped in this repository. The pane uses a text
  wordmark and the brand gradient only.
- This repository's MIT license covers the plugin code only. It grants no rights to Theta's
  software or trademarks.
- License facts checked on 2026-11-09: `thetatoken/theta-protocol-ledger` is GPL-3.0,
  `thetatoken/theta-wallet-web` is GPL-3.0, `thetatoken/theta-protocol-delivery-lib` is MIT, the
  ledger explorer is MIT, and `thetatoken/theta-eth-rpc-adaptor` has no license file. There is no
  Edge Node source repository in the public `thetatoken` org.
- Before a public release, read the installer's EULA and the `thetatoken` repository LICENSE
  files. They are authoritative; this section is a summary, not legal advice.

## Development

```bash
python -m venv %LOCALAPPDATA%\venvs\theta-edge-node
%LOCALAPPDATA%\venvs\theta-edge-node\Scripts\python.exe -m pip install -r requirements-dev.txt

%LOCALAPPDATA%\venvs\theta-edge-node\Scripts\python.exe -m unittest discover -s tests -v
node --check desktop/plugin.js
node tests/desktop_smoke.mjs

hermes plugins validate . --install-deps
hermes plugins doctor . --ci
```

## License

MIT. See `LICENSE`.
