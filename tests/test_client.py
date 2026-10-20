import httpx
import pytest

from client import SmartOilAuthError, SmartOilClient, SmartOilError

LOGIN_PAGE = '<form><input type="hidden" name="ccf_nonce" value="abc123"></form>'
DENIED = {"result": "error", "message": "Access Denied", "Status": 401}


class FakeSite:
    def __init__(self, password="right", login_page=LOGIN_PAGE, tanks=None):
        self.password = password
        self.login_page = login_page
        self.tanks = tanks
        self.logins = 0
        self.ajax_actions = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        if request.url.path == "/login.php" and request.method == "GET":
            return httpx.Response(200, text=self.login_page)
        if request.url.path == "/login.php":
            form = dict(httpx.QueryParams(request.content.decode()))
            assert form["ccf_nonce"] == "abc123"
            if form["user_pass"] != self.password:
                return httpx.Response(200, text='<p class="app_error">Invalid password</p>')
            self.logins += 1
            return httpx.Response(200, text="ok", headers={"set-cookie": "PHPSESSID=good; Path=/"})
        form = dict(httpx.QueryParams(request.content.decode()))
        self.ajax_actions.append(form["action"])
        if request.headers.get("cookie") != "PHPSESSID=good":
            return httpx.Response(200, json=DENIED)
        if form["action"] == "get_tanks_list":
            return httpx.Response(200, json={"result": "ok", "tanks": self.tanks or []})
        return httpx.Response(200, json={"result": "ok", "datasets": {}, "tank": form["tank_id"]})


def make_client(site, password="right"):
    return SmartOilClient("me@example.com", password, base_url="https://site.test",
                          transport=httpx.MockTransport(site))


def test_logs_in_on_first_call_then_reuses_session(tanks_list):
    site = FakeSite(tanks=tanks_list["tanks"])
    client = make_client(site)
    tanks = client.get_tanks()
    client.get_tanks()
    assert [t["tank_id"] for t in tanks] == ["1001", "1002"]
    assert site.logins == 1


def test_graph_data_sends_tank_id(tanks_list):
    site = FakeSite(tanks=tanks_list["tanks"])
    assert make_client(site).get_graph_data(tanks_list["tanks"][0])["tank"] == "1001"


def test_relogs_in_when_session_expires():
    site = FakeSite()
    client = make_client(site)
    client.get_tanks()
    client._http.cookies.set("PHPSESSID", "expired", domain="site.test")
    client.get_tanks()
    assert site.logins == 2


def test_wrong_password_reports_site_message():
    with pytest.raises(SmartOilAuthError, match="Invalid password"):
        make_client(FakeSite(), password="wrong").get_tanks()


def test_missing_nonce_is_a_clear_error():
    with pytest.raises(SmartOilError, match="ccf_nonce"):
        make_client(FakeSite(login_page="<html>redesigned</html>")).get_tanks()


def test_http_error_is_wrapped():
    client = SmartOilClient("u", "p", base_url="https://site.test",
                            transport=httpx.MockTransport(lambda r: httpx.Response(500)))
    with pytest.raises(SmartOilError):
        client.get_tanks()
