"""Client for the Smart Oil Gauge web app (app.smartoilgauge.com).

Smart Oil Gauge has no owner API. This makes the same calls as the web app:

    1. GET  /login.php           -> PHPSESSID cookie + ccf_nonce form token
    2. POST /login.php           username, user_pass, remember, ccf_nonce
    3. POST /ajax/main_ajax.php  action=get_tanks_list  (level, usage, battery)
    4. POST /ajax/main_ajax.php  action=get_graph_data  (history, temperature)

Flow taken from the MIT-licensed Home Assistant integrations
kkrankall/smartoil-gauge and andrewtryder/ha-smart-oil-gauge.
"""
from __future__ import annotations

import re
from typing import Any

import httpx

BASE_URL = "https://app.smartoilgauge.com"
TIMEOUT = 30.0
# Same browser agent string andrewtryder's client sends.
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
NONCE_RE = re.compile(r"""name=['"]ccf_nonce['"][^>]*value=['"]([^'"]+)['"]""")
APP_ERROR_RE = re.compile(r"""class=['"]app_error['"][^>]*>(.*?)</""", re.S)


class SmartOilError(Exception):
    """The site could not be reached or answered with something unexpected."""


class SmartOilAuthError(SmartOilError):
    """The site did not accept the username and password."""


class _AccessDenied(SmartOilError):
    """The session cookie is missing or has expired."""


class SmartOilClient:
    def __init__(self, username: str, password: str, base_url: str = BASE_URL,
                 transport: httpx.BaseTransport | None = None) -> None:
        self._username = username
        self._password = password
        self._http = httpx.Client(base_url=base_url, timeout=TIMEOUT, transport=transport,
                                  headers={"User-Agent": USER_AGENT}, follow_redirects=True)

    def close(self) -> None:
        self._http.close()

    def login(self) -> None:
        self._http.cookies.clear()
        try:
            resp = self._http.get("/login.php")
            resp.raise_for_status()
            match = NONCE_RE.search(resp.text)
            if not match:
                raise SmartOilError("Login page has no ccf_nonce field; the site may have changed")
            resp = self._http.post("/login.php", data={
                "username": self._username,
                "user_pass": self._password,
                "remember": "on",
                "ccf_nonce": match.group(1),
            })
            resp.raise_for_status()
        except httpx.HTTPError as err:
            raise SmartOilError(f"Login request failed: {err}") from err
        # login.php answers 200 whether or not the password was right, so
        # prove the new session can read data.
        try:
            self._ajax("get_tanks_list", tank_id=0)
        except _AccessDenied:
            match = APP_ERROR_RE.search(resp.text)
            reason = re.sub(r"<[^>]+>", "", match.group(1)).strip() if match else ""
            raise SmartOilAuthError(reason or "Username or password not accepted") from None

    def _ajax(self, action: str, **params: Any) -> dict[str, Any]:
        try:
            resp = self._http.post("/ajax/main_ajax.php", data={"action": action, **params},
                                   headers={"X-Requested-With": "XMLHttpRequest",
                                            "Referer": f"{self._http.base_url}app.php"})
            if resp.status_code in (401, 403):
                raise _AccessDenied(action)
            resp.raise_for_status()
            body = resp.json()
        except httpx.HTTPError as err:
            raise SmartOilError(f"{action} failed: {err}") from err
        except ValueError as err:
            raise SmartOilError(f"{action}: response is not JSON") from err
        if not isinstance(body, dict):
            raise SmartOilError(f"{action}: unexpected response")
        if body.get("result") == "ok":
            return body
        if str(body.get("Status")) == "401" or "Access Denied" in str(body.get("message")):
            raise _AccessDenied(action)
        raise SmartOilError(f"{action}: {body.get('message') or body}")

    def _call(self, action: str, **params: Any) -> dict[str, Any]:
        """Run an ajax call, logging in first if there is no live session."""
        try:
            return self._ajax(action, **params)
        except _AccessDenied:
            pass
        self.login()
        try:
            return self._ajax(action, **params)
        except _AccessDenied as err:
            raise SmartOilError(f"{action}: access denied right after login") from err

    def get_tanks(self) -> list[dict[str, Any]]:
        tanks = self._call("get_tanks_list", tank_id=0).get("tanks") or []
        return [t for t in tanks if isinstance(t, dict) and str(t.get("tank_id") or "").strip()]

    def get_graph_data(self, tank: dict[str, Any]) -> dict[str, Any]:
        return self._call("get_graph_data", tank_id=tank["tank_id"],
                          data_servers=tank.get("data_servers") or "")
