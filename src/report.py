"""Plain-text summary email of the polled tank data.

The body is `key: value` lines, one block per tank, so a person can skim it
and a bot can parse it: split each line on the first ": ", "[tank <name>]"
starts a block, values are numbers, true/false, null or text. Keys match the
MCP tool fields, so units are in the key names.
"""
from __future__ import annotations

import subprocess
from datetime import UTC, datetime, timedelta
from email.message import EmailMessage
from typing import Any

FORMAT = "smart-oil-gauge-summary/v1"
LEVEL_DAYS = 7
SENDMAIL = "/usr/sbin/sendmail"


def _value(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def _recent_levels(levels: list[dict], now: float) -> str:
    since = (datetime.fromtimestamp(now, UTC) - timedelta(days=LEVEL_DAYS)).date().isoformat()
    recent = [f"{d['date']}={_value(d['gallons'])}" for d in levels if d["date"] >= since]
    return " ".join(recent) or "null"


def _headline(status: dict) -> str:
    if status.get("gallons") is None:
        return f"{status.get('tank_name')} no reading"
    days = status.get("days_to_low")
    tail = "" if days is None else f", {_value(days)}d to low"
    return f"{status.get('tank_name')} {_value(status.get('percent_full'))}% ({_value(status['gallons'])} gal{tail})"


def build(statuses: list[dict], histories: list[dict], now: float) -> tuple[str, str]:
    """Subject and body from get_tank_status and get_usage_history results.

    histories must have been fetched with include_daily_levels=True.
    """
    by_id = {h["tank_id"]: h for h in histories}
    generated = datetime.fromtimestamp(now, UTC).replace(microsecond=0)
    lines = [f"format: {FORMAT}", f"generated: {generated.isoformat()}", f"tanks: {len(statuses)}"]
    for status in statuses:
        history = dict(by_id.get(status["tank_id"], {}))
        levels = history.pop("daily_levels", [])
        lines += ["", f"[tank {status.get('tank_name')}]"]
        for key, value in {**status, **history}.items():
            lines.append(f"{key}: {_value(value)}")
        lines.append(f"daily_gallons_last_{LEVEL_DAYS}_days: {_recent_levels(levels, now)}")
    subject = f"Oil tank summary {generated.date().isoformat()}: " + "; ".join(map(_headline, statuses))
    return subject, "\n".join(lines) + "\n"


def send(to_addr: str, subject: str, body: str, sendmail: str = SENDMAIL) -> None:
    """Hand the message to the local MTA (Postfix relays it). Raises on failure."""
    message = EmailMessage()
    message["To"] = to_addr
    message["Subject"] = subject
    message.set_content(body)
    subprocess.run([sendmail, "-t", "-i"], input=message.as_bytes(), timeout=60, check=True)
