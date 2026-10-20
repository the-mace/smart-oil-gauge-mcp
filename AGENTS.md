# Smart Oil Gauge MCP: agent instructions

Shared rules (pull before work, tests and lint, secrets, commit attribution)
live in the global `~/.config/agents/AGENTS.md`. If that file is not loaded
(cloud or CI sessions), the short version is: `git pull --ff-only` first, run
the tests below before committing, never commit secrets, and end agent commits
with a `Co-Authored-By: <Tool> (<model>) <email>` trailer.

## Which coding agent

Claude Code with Sonnet for small fixes (a renamed JSON field, a changed
login form). Opus 5.5 for multi-file or auth/session changes. Grok Build is
the second opinion.

## Repo specifics

- Setup: `python3.12 -m venv .venv && .venv/bin/pip install -r requirements.txt`.
  Re-run the install after a pull that touches `requirements.txt`.
- Tests: `.venv/bin/python -m pytest` (CI runs the same suite).
- Lint: `ruff check src tests`.
- Live check against the real account: `.venv/bin/python src/smart_oil_gauge_mcp.py --check`.
  Output is the owner's real tank data; do not paste it into commits, issues,
  fixtures or docs.

## Layout

- `src/client.py`: sync httpx client for app.smartoilgauge.com. Logs in with
  the web form (`login.php` + `ccf_nonce`), then calls
  `ajax/main_ajax.php` actions `get_tanks_list` and `get_graph_data`. The
  PHPSESSID cookie lives in memory; on "Access Denied" it logs in once more.
- `src/parse.py`: turns responses into tool results. Estimates and the 96 h
  offline rule mirror the web app's JavaScript, so numbers should match the
  site.
- `src/smart_oil_gauge_mcp.py`: MCP server (mcp v2, stdio) with two
  read-only tools, `get_tank_status` and `get_usage_history`. Credentials
  come from `SMARTOILGAUGE_USERNAME` / `SMARTOILGAUGE_PASSWORD` in the
  environment, falling back to `~/.env`.
- `tests/fixtures/`: synthetic responses in the site's shape. Never real data.

## When the site changes

There is no official free API, so this breaks if Smart Oil Gauge changes the
login form or the ajax JSON. Confirm the new shape from the browser's
network tab (or the upstream Home Assistant integrations listed in the
README) rather than guessing, update the fixture to the new shape with
synthetic values, and check `--check` output against app.smartoilgauge.com
by hand before calling it fixed.

## Guardrails

- Read-only. Do not add calls that change account settings, alerts or orders.
- Never print or log the password or the PHPSESSID cookie.
- No on-disk session or data cache unless Rob asks for one.
