# Smart Oil Gauge MCP

A small [MCP](https://modelcontextprotocol.io) server that reads your
[Smart Oil Gauge](https://www.smartoilgauge.com) (Connected Consumer Fuel)
heating-oil tank data on demand. You don't need Home Assistant.

Smart Oil Gauge has no free owner API. This server logs in to
app.smartoilgauge.com with your normal account and calls the same JSON
endpoints the web app uses. Each tool call fetches live data, and nothing is
stored on disk. It is unofficial and not affiliated with Smart Oil Gauge or
Connected Consumer Fuel, so it can break if they change their site.

**License:** MIT (see [LICENSE](LICENSE)).

## Tools

| Tool | Returns |
|---|---|
| `get_tank_status(tank_name=None)` | Gallons, percent full, capacity, gallons to fill, usage (gal/day), days until low / one-eighth / empty, battery, sensor status, last reading time |
| `get_usage_history(tank_name=None, include_daily_levels=False)` | Gallons used and average gal/day for today, 7, 30 and 365 days, tank temperature (°F), last delivery date and size; optionally the level for each day of the past year |

"Days to" estimates use the same rules as the web app: they are null when
usage is zero or the sensor hasn't reported for more than 96 hours.

## Install

Python 3.11 or newer.

```bash
git clone https://github.com/the-mace/smart-oil-gauge-mcp.git
cd smart-oil-gauge-mcp
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## Credentials

Use the email and password you sign in to app.smartoilgauge.com with. Set
them in the environment, or put them in a `.env` file in this repo's folder
(git ignores it) or in `~/.env`. They are looked up in that order:

```bash
SMARTOILGAUGE_USERNAME=you@example.com
SMARTOILGAUGE_PASSWORD=your-password
```

Check that it works (prints both tools' output for your tanks):

```bash
.venv/bin/python src/smart_oil_gauge_mcp.py --check
```

## Weekly summary email

Set `WEEKLY_SUMMARY_EMAIL` in the same `.env` (or the environment) to get the
polled data by email:

```bash
WEEKLY_SUMMARY_EMAIL=you@example.com
```

```bash
.venv/bin/python src/smart_oil_gauge_mcp.py --summary       # print it
.venv/bin/python src/smart_oil_gauge_mcp.py --send-summary  # email it
scripts/install-launchd.sh            # macOS: send every Sunday 08:00
scripts/install-launchd.sh 1 7 30     # or weekday (0=Sunday), hour, minute
scripts/install-launchd.sh --uninstall
```

Mail goes through the local `sendmail` (Postfix or another MTA must already
relay outbound mail). The subject is a one-line headline per tank. The body
is every field of both tools as `key: value` lines, plus the last 7 days of
daily levels, so it is easy to read and easy for a script or bot to parse:

```
format: smart-oil-gauge-summary/v1
generated: 2026-09-21T15:13:20+00:00
tanks: 1

[tank Basement]
gallons: 137.5
percent_full: 50
days_to_low: 27.5
...
daily_gallons_last_7_days: 2026-09-15=150 2026-09-21=137.5
```

Missing values are `null`. The job logs to `logs/` (gitignored), and the
address is read at send time, so it stays out of the plist and the repo.

## Add to an MCP client

Claude Desktop (`~/Library/Application Support/Claude/claude_desktop_config.json`).
Merge this into any existing `mcpServers`:

```json
{
  "mcpServers": {
    "smart-oil-gauge": {
      "command": "/path/to/smart-oil-gauge-mcp/.venv/bin/python",
      "args": ["/path/to/smart-oil-gauge-mcp/src/smart_oil_gauge_mcp.py"]
    }
  }
}
```

Claude Code:

```bash
claude mcp add smart-oil-gauge -s user -- \
  /path/to/smart-oil-gauge-mcp/.venv/bin/python /path/to/smart-oil-gauge-mcp/src/smart_oil_gauge_mcp.py
```

If you don't use `~/.env`, pass the two variables in the client's `env`
block instead.

## Development

```bash
.venv/bin/python -m pytest
```

Tests use synthetic responses in `tests/fixtures/` and never touch the real
site. Dependabot opens weekly PRs for Python packages and GitHub Actions.
Once CI passes, patch and minor bumps merge automatically (patch only for
0.x packages); majors wait for review.

## Credits

The login flow, endpoints and estimate rules come from these Home Assistant
integrations (both MIT):

- [kkrankall/smartoil-gauge](https://github.com/kkrankall/smartoil-gauge)
- [andrewtryder/ha-smart-oil-gauge](https://github.com/andrewtryder/ha-smart-oil-gauge)

Also see the [smart-oil-gauge](https://github.com/topics/smart-oil-gauge) GitHub topic.
