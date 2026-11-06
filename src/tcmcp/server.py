"""MCP server entry point (stdio by default).

Aşama 1: the server starts and answers discovery/list requests but registers no
tools yet. Tools, resources and prompts are added in later stages.
"""

from __future__ import annotations

import logging
from typing import Any

from mcp.server import MCPServer

from tcmcp import __version__
from tcmcp.config import Settings, load_settings
from tcmcp.logging_config import configure_logging

SERVER_NAME = "turkish-nlp-tools"
INSTRUCTIONS = "Turkish text classification tools. Read-only."

logger = logging.getLogger(__name__)


def build_server(settings: Settings | None = None) -> MCPServer[Any]:
    """Create the MCP server. Does not load any model (models load lazily)."""
    cfg = settings if settings is not None else load_settings()
    configure_logging(cfg.log_level)
    server: MCPServer[Any] = MCPServer(
        name=SERVER_NAME,
        version=__version__,
        instructions=INSTRUCTIONS,
        log_level=cfg.log_level,
    )
    logger.debug("server built (backend=%s)", cfg.backend)
    return server


def main() -> None:
    """Run the server over stdio. stdout is reserved for the protocol."""
    server = build_server()
    logger.info("starting %s %s over stdio", SERVER_NAME, __version__)
    server.run(transport="stdio")


if __name__ == "__main__":
    main()
