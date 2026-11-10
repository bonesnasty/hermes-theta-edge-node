from __future__ import annotations

import os
import sys
import unittest
from unittest.mock import patch

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from theta_core import chain


class ChainTests(unittest.TestCase):
    def test_balance_converts_wei_to_tfuel(self):
        with patch.object(chain, "_post", return_value={"result": "0xde0b6b3a7640000"}):
            self.assertAlmostEqual(chain.tfuel_balance("0x" + "1" * 40), 1.0)

    def test_price_reads_coingecko(self):
        with patch.object(chain, "_price_json", return_value={"theta-fuel": {"usd": 0.0075}}):
            chain._CACHE.update(at=0.0, usd=None)
            self.assertAlmostEqual(chain.tfuel_usd(force=True), 0.0075)

    def test_wallet_value_multiplies_balance_by_price(self):
        with patch.object(chain, "tfuel_balance", return_value=100.0), patch.object(
            chain, "tfuel_usd", return_value=0.01
        ):
            value = chain.wallet_value("0x" + "1" * 40)
        self.assertAlmostEqual(value["total_usd"], 1.0)
        self.assertEqual(value["price_source"], "coingecko")

    def test_price_failure_keeps_tfuel(self):
        with patch.object(chain, "tfuel_balance", return_value=100.0), patch.object(
            chain, "tfuel_usd", side_effect=RuntimeError("rate limited")
        ):
            value = chain.wallet_value("0x" + "1" * 40)
        self.assertEqual(value["tfuel"], 100.0)
        self.assertEqual(value["price_source"], "unavailable")
        self.assertIn("rate limited", value["price_error"])

    def test_bad_address_is_rejected(self):
        with self.assertRaises(ValueError):
            chain.tfuel_balance("not-an-address")


if __name__ == "__main__":
    unittest.main()
