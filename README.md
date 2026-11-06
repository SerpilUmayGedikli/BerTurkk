# mcp-turkish-nlp-tools

An [MCP](https://modelcontextprotocol.io) server that will expose the Turkish news-category
and sentiment classifiers from the [BERTurk project](https://github.com/SerpilUmayGedikli/BERTurk)
as tools for an AI agent (Claude Code, MCP Inspector, ...).

The server itself never calls an LLM and needs no API key.

## Status

| Stage | Scope | State |
|---|---|---|
| Aşama 1 | Skeleton, backend interface, `FakeBackend`, stdio server, tests, CI | Done |
| Aşama 2 | `classify_news`, `classify_sentiment`, `list_reports` tools | Done |
| Aşama 3 | `reports://{name}` resources, `analyze_text` prompt | Not started |
| Aşama 4 | Real backends (TF-IDF joblib, BERTurk via transformers) | Not started |
| Aşama 5 | stdio integration test, Inspector CLI script, demo | Not started |
| Aşama 6 | Docker, SECURITY.md, optional Streamable HTTP | Not started |

The tools run on `FakeBackend` only, which returns hash-derived scores with **no meaning**;
it exists for tests and demos. No real model has been run in this repository, and no accuracy
or latency number is claimed. Real backends come in Aşama 4.

## Tools

All tools are read-only (`readOnlyHint: true`, `openWorldHint: false`), take no file paths,
URLs or shell commands, and make no network calls.

| Tool | Input | Structured output |
|---|---|---|
| `classify_news` | `text` (string, 1 to `TCMCP_MAX_TEXT_CHARS` chars) | `label`, `confidence`, `scores`, `model_id`, `latency_ms` |
| `classify_sentiment` | `text` (same limits) | same fields + `notes` |
| `list_reports` | none | `reports`: sorted file names |

- News labels (BERTurk project, `savasy/ttc4900`): `dunya`, `ekonomi`, `kultur`, `saglik`,
  `siyaset`, `spor`, `teknoloji`.
- Sentiment labels: `Negative`, `Notr`, `Positive`. Every sentiment result carries a note on
  the **Notr source shortcut** found in the BERTurk project: almost all Notr training examples
  come from Wikipedia, so real neutral-opinion detection was not measured.
- `latency_ms` is the server-side time of the backend call, measured per request. With
  `FakeBackend` it says nothing about model speed.
- `list_reports` lists `.md`/`.json` files directly inside `TCMCP_REPORTS_DIR`, skipping
  hidden files, sub-folders, symbolic links and `README.md`. Reading reports comes in Aşama 3.

### Errors

Tool failures return `isError: true` with a short message:

| Case | Message |
|---|---|
| empty / whitespace-only text | `text must not be empty or whitespace only.` |
| text over the limit | `text is too long: limit is N characters.` |
| backend raises | `classification backend failed.` |
| backend returns a label or scores outside the label set | `classification backend returned an invalid result.` |
| backend slower than `TCMCP_CALL_TIMEOUT_S` | `classification timed out; try a shorter text or retry later.` |

These messages never contain the input text, paths, tokens or stack traces; details go to the
stderr log only (without the text). The length limits are published in the input schema
(`minLength`/`maxLength`) but enforced by the server code, because pydantic's own constraint
error would echo part of the input back.

Known limitation: a **missing** `text` argument or a **non-string** value is rejected by the
SDK's argument validation before the tool runs. That message is the SDK's pydantic error,
which includes the offending value (for example `input_value=5`).

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
| `TCMCP_BACKEND` | `fake` | Only `fake` exists so far |
| `TCMCP_MAX_TEXT_CHARS` | `5000` | Maximum input length (1 to 100000) |
| `TCMCP_CALL_TIMEOUT_S` | `10` | Per-call backend timeout in seconds |
| `TCMCP_REPORTS_DIR` | `<repo>/reports` | Folder that `list_reports` scans |

## Checks

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy          # strict
uv run pytest
```

Tests use no network and no model. They include an in-memory client, a real stdio subprocess
client (modern and legacy handshake), a check that stdout stays empty when no client speaks,
and tool tests for invalid input, over-long text, unknown labels, backend errors, timeouts,
lazy loading, report listing and the published schemas. The symlink test is skipped on
Windows accounts without symlink permission.

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

## Inspector check (Aşama 2)

Same environment and Inspector version as above (FakeBackend, so the scores are meaningless):

```bash
npx -y @modelcontextprotocol/inspector@2.14.0 --cli --protocol-era modern .venv/Scripts/python.exe -m tcmcp --method tools/list
# -> classify_news, classify_sentiment, list_reports; text has minLength 1 / maxLength 5000;
#    output schemas and readOnlyHint/openWorldHint as documented above. Exit 0.
npx -y @modelcontextprotocol/inspector@2.14.0 --cli --protocol-era modern .venv/Scripts/python.exe -m tcmcp --method tools/list --strict
# -> exit 0 (no schema portability error)
npx -y @modelcontextprotocol/inspector@2.14.0 --cli --protocol-era modern .venv/Scripts/python.exe -m tcmcp --method tools/call --tool-name classify_news --tool-arg "text=Galatasaray deplasmanda 3-1 kazandı."
# -> isError false, structuredContent {label, confidence, scores (7 labels), model_id "fake-news", latency_ms}
npx -y @modelcontextprotocol/inspector@2.14.0 --cli --protocol-era modern .venv/Scripts/python.exe -m tcmcp --method tools/call --tool-name classify_news --tool-arg "text=   "
# -> isError true, "text must not be empty or whitespace only."; Inspector exit code 5 (tool error)
```

`classify_sentiment` (with `notes`) and `list_reports` (`{"reports": []}`) were also called
successfully, and `tools/list` with `--protocol-era legacy` returned the same three tools.

## License

MIT
