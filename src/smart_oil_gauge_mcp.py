"""MCP server that reads Smart Oil Gauge tank data on demand.

Each tool call fetches live from app.smartoilgauge.com using your account
login. Nothing is stored on disk; the session cookie lives in memory for
the life of the server process.

Run with --check to print every tool's output once and exit.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

from mcp.server.mcpserver import MCPServer

import parse
from client import SmartOilClient

USERNAME_VAR = "SMARTOILGAUGE_USERNAME"
PASSWORD_VAR = "SMARTOILGAUGE_PASSWORD"
DOTENV = Path.home() / ".env"

mcp = MCPServer("smart-oil-gauge")
_client: SmartOilClient | None = None


def _read_dotenv(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    try:
        lines = path.read_text().splitlines()
    except OSError:
        return values
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.removeprefix("export ").partition("=")
        values[key.strip()] = value.strip().strip("'\"")
    return values


def load_credentials(env: dict[str, str] = os.environ, dotenv: Path = DOTENV) -> tuple[str, str]:
    """Credentials from the environment, falling back to ~/.env."""
    file_values = _read_dotenv(dotenv)
    username = env.get(USERNAME_VAR) or file_values.get(USERNAME_VAR)
    password = env.get(PASSWORD_VAR) or file_values.get(PASSWORD_VAR)
    if not username or not password:
        raise RuntimeError(f"Set {USERNAME_VAR} and {PASSWORD_VAR} in the environment or {dotenv}")
    return username, password


def _get_client() -> SmartOilClient:
    global _client
    if _client is None:
        _client = SmartOilClient(*load_credentials())
    return _client


def _select(tanks: list[dict], tank_name: str | None) -> list[dict]:
    if not tank_name:
        return tanks
    wanted = tank_name.strip().lower()
    matches = [t for t in tanks if str(t.get("tank_name") or "").strip().lower() == wanted]
    if not matches:
        names = ", ".join(str(t.get("tank_name")) for t in tanks)
        raise ValueError(f"No tank named {tank_name!r}. Tanks on this account: {names}")
    return matches


@mcp.tool()
def get_tank_status(tank_name: str | None = None) -> list[dict]:
    """Get the current oil level and estimates for each tank on the account.

    Returns gallons, percent full, capacity, gallons to fill, usage in
    gallons/day, days until low / one-eighth / empty, battery, sensor status
    and the time of the last reading (UTC). "Days to" values are null when
    usage is zero or the sensor has been offline over 96 hours.

    Args:
        tank_name: only this tank (case-insensitive); default all tanks
    """
    tanks = _select(_get_client().get_tanks(), tank_name)
    now = time.time()
    return [parse.tank_status(t, now) for t in tanks]


@mcp.tool()
def get_usage_history(tank_name: str | None = None, include_daily_levels: bool = False) -> list[dict]:
    """Get oil usage totals, tank temperature and the last delivery for each tank.

    Returns gallons used and average gallons/day for today, 7, 30 and 365
    days, the latest tank temperature (°F), and the date and size of the
    most recent fill detected in the past year.

    Args:
        tank_name: only this tank (case-insensitive); default all tanks
        include_daily_levels: also return the tank level for each day of the
            past year as [{date, gallons}]
    """
    client = _get_client()
    tanks = _select(client.get_tanks(), tank_name)
    return [parse.usage_history(t, client.get_graph_data(t), include_daily_levels) for t in tanks]


def main(argv: list[str]) -> None:
    if "--check" in argv:
        print(json.dumps({"get_tank_status": get_tank_status(),
                          "get_usage_history": get_usage_history()}, indent=2))
        return
    mcp.run()


if __name__ == "__main__":
    main(sys.argv[1:])
