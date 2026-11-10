"""OpenAI-style function schemas for the agent half."""

_EMPTY_PARAMETERS = {"type": "object", "properties": {}, "additionalProperties": False}

THETA_NODE_STATUS = {
    "name": "theta_node_status",
    "description": "Report Theta Edge Node status, local reward totals, and the node wallet's TFUEL balance and USD value. Never returns a private key.",
    "parameters": _EMPTY_PARAMETERS,
}

THETA_WALLET_ADDRESS = {
    "name": "theta_wallet_address",
    "description": "Return the Theta Edge Node's public wallet address and TFUEL balance. Never returns a private key.",
    "parameters": _EMPTY_PARAMETERS,
}
