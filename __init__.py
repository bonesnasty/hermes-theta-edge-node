"""Agent half: two read-only tools. The desktop half owns the UI."""

from __future__ import annotations

from . import schemas, tools


def register(ctx) -> None:
    ctx.register_tool(
        name="theta_node_status",
        toolset="theta_edge_node",
        schema=schemas.THETA_NODE_STATUS,
        handler=tools.theta_node_status,
    )
    ctx.register_tool(
        name="theta_wallet_address",
        toolset="theta_edge_node",
        schema=schemas.THETA_WALLET_ADDRESS,
        handler=tools.theta_wallet_address,
    )
