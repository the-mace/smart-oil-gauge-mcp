import email
import stat

import parse
import report
import smart_oil_gauge_mcp as server

NOW = 1790000000 + 3600


def _summary(tanks_list, graph_data):
    tanks = tanks_list["tanks"][:2]
    statuses = [parse.tank_status(t, NOW) for t in tanks]
    histories = [parse.usage_history(t, graph_data, include_daily_levels=True) for t in tanks]
    return report.build(statuses, histories, NOW)


def _blocks(body):
    blocks, current = {}, None
    for line in body.splitlines():
        if line.startswith("[tank "):
            current = blocks.setdefault(line[6:-1], {})
        elif line:
            key, _, value = line.partition(": ")
            (current if current is not None else blocks.setdefault(None, {}))[key] = value
    return blocks


def test_body_is_key_value_per_tank(tanks_list, graph_data):
    subject, body = _summary(tanks_list, graph_data)
    blocks = _blocks(body)
    assert blocks[None] == {"format": "smart-oil-gauge-summary/v1",
                            "generated": "2026-09-21T15:13:20+00:00", "tanks": "2"}
    basement = blocks["Basement"]
    assert basement["gallons"] == "137.5"
    assert basement["is_low"] == "false"
    assert basement["days_to_low"] == "27.5"
    assert basement["gallons_used_7_days"] == "17.5"
    assert basement["last_fill_gallons"] == "185"
    assert basement["daily_gallons_last_7_days"] == "2026-09-15=150 2026-09-21=137.5"
    assert blocks["Garage"]["days_to_low"] == "null"
    assert subject == ("Oil tank summary 2026-09-21: Basement 50% (137.5 gal, 27.5d to low); "
                       "Garage 18.2% (50 gal)")


def test_every_tool_field_is_in_the_body(tanks_list, graph_data):
    _, body = _summary(tanks_list, graph_data)
    status = parse.tank_status(tanks_list["tanks"][0], NOW)
    history = parse.usage_history(tanks_list["tanks"][0], graph_data, include_daily_levels=False)
    assert set(status) | set(history) <= set(_blocks(body)["Basement"])


def test_send_pipes_message_to_sendmail(tmp_path):
    captured = tmp_path / "message.eml"
    fake = tmp_path / "sendmail"
    fake.write_text(f"#!/bin/sh\ncat > {captured}\n")
    fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
    report.send("bot@example.com", "Subject line", "format: x\n", sendmail=str(fake))
    message = email.message_from_bytes(captured.read_bytes())
    assert message["To"] == "bot@example.com"
    assert message["Subject"] == "Subject line"
    assert message.get_payload() == "format: x\n"


def test_send_summary_needs_an_address(monkeypatch, capsys):
    monkeypatch.setattr(server, "config_value", lambda name: None)
    assert server.main(["--send-summary"]) == 2
    assert "WEEKLY_SUMMARY_EMAIL" in capsys.readouterr().err


def test_summary_address_from_dotenv(tmp_path):
    dotenv = tmp_path / ".env"
    dotenv.write_text("WEEKLY_SUMMARY_EMAIL=bot@example.com\n")
    assert server.config_value("WEEKLY_SUMMARY_EMAIL", {}, (dotenv,)) == "bot@example.com"
