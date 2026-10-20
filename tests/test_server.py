from pathlib import Path

import pytest

import smart_oil_gauge_mcp as server


def test_credentials_prefer_environment(tmp_path):
    dotenv = tmp_path / ".env"
    dotenv.write_text("SMARTOILGAUGE_USERNAME=file-user\nexport SMARTOILGAUGE_PASSWORD='file-pass'\n")
    assert server.load_credentials({}, (dotenv,)) == ("file-user", "file-pass")
    env = {"SMARTOILGAUGE_USERNAME": "env-user", "SMARTOILGAUGE_PASSWORD": "env-pass"}
    assert server.load_credentials(env, (dotenv,)) == ("env-user", "env-pass")


def test_repo_dotenv_is_read_before_home_dotenv(tmp_path):
    repo, home = tmp_path / "repo.env", tmp_path / "home.env"
    repo.write_text("SMARTOILGAUGE_USERNAME=repo-user\nSMARTOILGAUGE_PASSWORD=repo-pass\n")
    home.write_text("SMARTOILGAUGE_USERNAME=home-user\nSMARTOILGAUGE_PASSWORD=home-pass\n")
    assert server.load_credentials({}, (repo, home)) == ("repo-user", "repo-pass")
    assert server.load_credentials({}, (tmp_path / "missing", home)) == ("home-user", "home-pass")


def test_default_search_includes_repo_dotenv():
    assert server.DOTENV_FILES[0] == Path(server.__file__).resolve().parent.parent / ".env"


def test_missing_credentials(tmp_path):
    with pytest.raises(RuntimeError, match="SMARTOILGAUGE_USERNAME"):
        server.load_credentials({}, (tmp_path / "missing",))


def test_select_tank_by_name(tanks_list):
    tanks = tanks_list["tanks"][:2]
    assert server._select(tanks, " basement ") == [tanks[0]]
    assert server._select(tanks, None) == tanks
    with pytest.raises(ValueError, match="Basement, Garage"):
        server._select(tanks, "attic")
