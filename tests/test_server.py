from __future__ import annotations

import os
import subprocess
import sys
from collections.abc import AsyncIterator

import pytest
from mcp import Client, StdioServerParameters

from tcmcp import __version__
from tcmcp.config import Settings
from tcmcp.server import SERVER_NAME, build_server

MODERN = "2026-07-28"
EXPECTED_TOOLS = ["classify_news", "classify_sentiment", "list_reports"]


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def client() -> AsyncIterator[Client]:
    async with Client(build_server(Settings()), raise_exceptions=True) as c:
        yield c


@pytest.mark.anyio
async def test_in_memory_connect_modern(client: Client) -> None:
    assert client.protocol_version == MODERN
    assert client.server_info is not None
    assert client.server_info.name == SERVER_NAME
    assert client.server_info.version == __version__


@pytest.mark.anyio
async def test_registered_tools(client: Client) -> None:
    result = await client.list_tools()
    assert [t.name for t in result.tools] == EXPECTED_TOOLS


def _stdio_params() -> StdioServerParameters:
    return StdioServerParameters(command=sys.executable, args=["-m", "tcmcp"])


@pytest.mark.anyio
async def test_stdio_subprocess_modern() -> None:
    async with Client(_stdio_params()) as c:
        assert c.protocol_version == MODERN
        assert c.server_info is not None
        assert c.server_info.name == SERVER_NAME
        assert [t.name for t in (await c.list_tools()).tools] == EXPECTED_TOOLS


@pytest.mark.anyio
async def test_stdio_subprocess_legacy_handshake() -> None:
    async with Client(_stdio_params(), mode="legacy") as c:
        assert c.protocol_version != MODERN
        assert [t.name for t in (await c.list_tools()).tools] == EXPECTED_TOOLS


def test_stdout_stays_clean_when_stdin_closes() -> None:
    """Nothing but protocol may reach stdout; with no input, stdout must be empty."""
    proc = subprocess.run(
        [sys.executable, "-m", "tcmcp"],
        input=b"",
        capture_output=True,
        timeout=60,
        check=False,
        env={"TCMCP_LOG_LEVEL": "DEBUG", **_minimal_env()},
    )
    assert proc.stdout == b""
    assert b"starting turkish-nlp-tools" in proc.stderr


def _minimal_env() -> dict[str, str]:
    keep = ("PATH", "SYSTEMROOT", "SYSTEMDRIVE", "HOME", "USERPROFILE", "TEMP", "TMP")
    return {k: v for k, v in os.environ.items() if k in keep}
