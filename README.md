# mcp-turkish-nlp-tools

An [MCP](https://modelcontextprotocol.io) server that will expose the Turkish news-category
and sentiment classifiers from the [BERTurk project](https://github.com/SerpilUmayGedikli/BERTurk)
as tools for an AI agent (Claude Code, MCP Inspector, ...).

The server itself never calls an LLM and needs no API key.

## Status

| Stage | Scope | State |
|---|---|---|
| Aşama 1 | Skeleton, backend interface, `FakeBackend`, stdio server, tests, CI | Done |
| Aşama 2 | `classify_news`, `classify_sentiment`, `list_reports` tools | Not started |
| Aşama 3 | `reports://{name}` resources, `analyze_text` prompt | Not started |
| Aşama 4 | Real backends (TF-IDF joblib, BERTurk via transformers) | Not started |
| Aşama 5 | stdio integration test, Inspector CLI script, demo | Not started |
| Aşama 6 | Docker, SECURITY.md, optional Streamable HTTP | Not started |

Right now the server starts and answers discovery and list requests, but it registers **no
tools**. `FakeBackend` returns hash-derived scores with no meaning; it exists only for tests.
No real model has been run in this repository, and no accuracy or latency number is claimed.

## Stack

- Python 3.11, [uv](https://docs.astral.sh/uv)
- Official MCP Python SDK, `mcp` 2.3.x (`from mcp.server import MCPServer`). The separate
  third-party `fastmcp` package is not used.
- Protocol: the SDK speaks the stateless **2026-07-28** revision (`server/discover`, no
  `initialize` handshake) and still accepts legacy `initialize` clients (2025-11-25).

## Run

```bash
uv sync
uv run tcmcp            # or: uv run python -m tcmcp
```

The process waits on stdin for a client. With stdio, **stdout is the protocol channel**; all
logs go to stderr (`src/tcmcp/logging_config.py`).

Settings (environment variables, see `src/tcmcp/config.py`):

| Variable | Default | Meaning |
|---|---|---|
| `TCMCP_LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` |
| `TCMCP_BACKEND` | `fake` | Only `fake` exists in Aşama 1 |
| `TCMCP_MAX_TEXT_CHARS` | `5000` | Input length limit (enforced from Aşama 2) |

## Checks

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy          # strict
uv run pytest
```

Tests use no network and no model. They include an in-memory client, a real stdio subprocess
client (modern and legacy handshake) and a check that stdout stays empty when no client speaks.

## Inspector check (Aşama 1)

Run locally on Windows 11 with MCP Inspector 2.14.0 via `npx`. Node.js here is v22.13.0, which
is **below** the Inspector's declared engine range (`^22.23.4 || ^24.22.1 || >=26.12.1`); npm
printed `EBADENGINE` warnings, but the commands below completed with exit code 0.

```bash
npx -y @modelcontextprotocol/inspector@2.14.0 --cli --protocol-era modern .venv/Scripts/python.exe -m tcmcp --method initialize
# -> serverInfo.name "turkish-nlp-tools", protocolVersion "2026-07-28"
npx -y @modelcontextprotocol/inspector@2.14.0 --cli --protocol-era legacy .venv/Scripts/python.exe -m tcmcp --method initialize
# -> protocolVersion "2025-11-25"
npx -y @modelcontextprotocol/inspector@2.14.0 --cli --protocol-era modern .venv/Scripts/python.exe -m tcmcp --method tools/list
# -> {"tools": []}
```

The graphical (web) Inspector was not run.

## License

MIT
