from __future__ import annotations

import os
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from mcp import Client, MCPError
from mcp.types import TextResourceContents

from tcmcp.config import Settings
from tcmcp.resources import (
    MAX_REPORT_BYTES,
    ReportAccessError,
    list_report_names,
    read_report,
)
from tcmcp.server import build_server

SECRET = "TOP-SECRET-OUTSIDE-REPORTS"

# Raw names handed straight to read_report (bypassing the SDK's own URI checks).
ATTACK_NAMES = [
    "../secret.md",
    "..\\secret.md",
    "../../secret.md",
    "..",
    "/etc/passwd",
    "C:\\Windows\\win.ini",
    "C:win.ini",
    "\\\\server\\share\\x.md",
    "sub/inner.md",
    "sub\\inner.md",
    "good.md\x00.txt",
    ".hidden.md",
    "README.md",
    "notes.txt",
    "a..b.md",
    "%2e%2e%2fsecret.md",
    "",
    " good.md",
]

# Percent-encoded URIs as a client would send them.
ATTACK_URIS = [
    "reports://../secret.md",
    "reports://..%2Fsecret.md",
    "reports://%2E%2E%2Fsecret.md",
    "reports://..%5Csecret.md",
    "reports://%2Fetc%2Fpasswd",
    "reports://C:%5CWindows%5Cwin.ini",
    "reports://good.md%00.txt",
    "reports://sub%2Finner.md",
    "reports://.hidden.md",
    "reports://README.md",
    "reports://notes.txt",
]


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def layout(tmp_path: Path) -> Path:
    """tmp/secret.md (outside) and tmp/reports/ with valid and decoy files."""
    (tmp_path / "secret.md").write_text(SECRET, encoding="utf-8")
    reports = tmp_path / "reports"
    reports.mkdir()
    (reports / "good.md").write_text("# Good report\n\nçğıöşü", encoding="utf-8")
    (reports / "metrics.json").write_text('{"macro_f1": 0.9}', encoding="utf-8")
    (reports / "README.md").write_text("readme", encoding="utf-8")
    (reports / ".hidden.md").write_text("hidden", encoding="utf-8")
    (reports / "notes.txt").write_text("txt", encoding="utf-8")
    (reports / "sub").mkdir()
    (reports / "sub" / "inner.md").write_text("inner", encoding="utf-8")
    return reports


def _settings(reports: Path) -> Settings:
    return Settings(reports_dir=reports, log_level="WARNING")


@pytest.fixture
async def client(layout: Path) -> AsyncIterator[Client]:
    async with Client(build_server(_settings(layout)), raise_exceptions=True) as c:
        yield c


# ------------------------------------------------------------ unit: reader


def test_read_valid_reports(layout: Path) -> None:
    assert read_report(layout, "good.md").startswith("# Good report")
    assert "çğıöşü" in read_report(layout, "good.md")
    assert read_report(layout, "metrics.json") == '{"macro_f1": 0.9}'


@pytest.mark.parametrize("name", ATTACK_NAMES)
def test_attack_names_rejected(layout: Path, name: str) -> None:
    with pytest.raises(ReportAccessError) as info:
        read_report(layout, name)
    assert SECRET not in str(info.value)
    assert str(layout) not in str(info.value)


def test_missing_report(layout: Path) -> None:
    with pytest.raises(ReportAccessError, match="not found"):
        read_report(layout, "nope.md")


def test_symlink_escape_rejected(layout: Path) -> None:
    try:
        os.symlink(layout.parent / "secret.md", layout / "link.md")
    except OSError:
        pytest.skip("symlinks not permitted on this system")
    with pytest.raises(ReportAccessError):
        read_report(layout, "link.md")
    assert "link.md" not in list_report_names(layout)


def test_symlinked_reports_dir_does_not_leak_outside(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "x.md").write_text(SECRET, encoding="utf-8")
    inside = tmp_path / "reports"
    inside.mkdir()
    try:
        os.symlink(outside, inside / "linkdir", target_is_directory=True)
    except OSError:
        pytest.skip("symlinks not permitted on this system")
    with pytest.raises(ReportAccessError):
        read_report(inside, "linkdir/x.md")


def test_oversized_report_rejected(layout: Path) -> None:
    (layout / "big.md").write_bytes(b"a" * (MAX_REPORT_BYTES + 1))
    with pytest.raises(ReportAccessError, match="too large"):
        read_report(layout, "big.md")


def test_non_utf8_report_rejected(layout: Path) -> None:
    (layout / "latin.md").write_bytes(b"\xff\xfe\xfa bad")
    with pytest.raises(ReportAccessError, match="could not be read"):
        read_report(layout, "latin.md")


def test_list_only_servable_reports(layout: Path) -> None:
    assert list_report_names(layout) == ["good.md", "metrics.json"]


# ---------------------------------------------------------- protocol level


@pytest.mark.anyio
async def test_resources_list_has_reports_with_mime(client: Client) -> None:
    listed = {str(r.uri): r.mime_type for r in (await client.list_resources()).resources}
    assert listed == {
        "reports://good.md": "text/markdown",
        "reports://metrics.json": "application/json",
    }


@pytest.mark.anyio
async def test_resource_template_listed(client: Client) -> None:
    templates = (await client.list_resource_templates()).resource_templates
    assert [t.uri_template for t in templates] == ["reports://{name}"]


@pytest.mark.anyio
async def test_read_markdown_and_json(client: Client, layout: Path) -> None:
    md = (await client.read_resource("reports://good.md")).contents[0]
    assert isinstance(md, TextResourceContents)
    assert md.mime_type == "text/markdown"
    assert md.text == (layout / "good.md").read_text(encoding="utf-8")
    js = (await client.read_resource("reports://metrics.json")).contents[0]
    assert isinstance(js, TextResourceContents)
    assert js.mime_type == "application/json"


@pytest.mark.anyio
async def test_report_added_after_start_served_by_template(client: Client, layout: Path) -> None:
    (layout / "late.md").write_text("# late", encoding="utf-8")
    contents = (await client.read_resource("reports://late.md")).contents[0]
    assert isinstance(contents, TextResourceContents)
    assert contents.text == "# late"


@pytest.mark.anyio
async def test_deleted_report_not_served(client: Client, layout: Path) -> None:
    (layout / "good.md").unlink()
    with pytest.raises(MCPError) as info:
        await client.read_resource("reports://good.md")
    assert "not found" in info.value.error.message


@pytest.mark.anyio
@pytest.mark.parametrize("uri", ATTACK_URIS)
async def test_attack_uris_rejected(client: Client, layout: Path, uri: str) -> None:
    with pytest.raises(MCPError) as info:
        await client.read_resource(uri)
    message = info.value.error.message
    assert SECRET not in message
    assert str(layout) not in message
    assert "Traceback" not in message


@pytest.mark.anyio
async def test_list_reports_tool_matches_resources(client: Client) -> None:
    result = await client.call_tool("list_reports", {})
    assert result.structured_content == {"reports": ["good.md", "metrics.json"]}
