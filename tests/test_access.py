"""The Pulse Compass login (aipulse/access.py): nothing paid is readable in what gets published."""
import base64
import json
import os

import pytest

from aipulse import access

SECRET = "the words only a paying reader may read"


def site(tmp_path, monkeypatch):
    # the login page itself comes from Compass, which a public clone hasn't got
    monkeypatch.setattr(access, "_shell", lambda conn, cards, path, page, table, files: json.dumps(
        {"page": page, "table": table, "files": files}))
    out = tmp_path / "site"
    for rel, text in (("planner/index.html", "the product page"), ("planner/sample-report/index.html", "the sample"),
                      ("planner/plan/index.html", SECRET), ("planner/example/sheet.csv", SECRET)):
        (out / rel).parent.mkdir(parents=True, exist_ok=True)
        (out / rel).write_text(text, encoding="utf-8")
    (out / "about").mkdir()
    (out / "about" / "index.html").write_text("free", encoding="utf-8")
    return out


def everything(out):
    return "".join(p.read_text(encoding="utf-8") for p in out.rglob("*") if p.is_file())


def test_without_users_nothing_paid_is_published(tmp_path, monkeypatch):
    monkeypatch.delenv("COMPASS_USERS", raising=False)
    out = site(tmp_path, monkeypatch)
    access.seal(out, None, [])
    assert SECRET not in everything(out)
    assert not (out / "planner/example/sheet.csv").exists() and not (out / "planner/example/sheet.csv.sealed").exists()
    assert json.loads((out / "planner/plan/index.html").read_text(encoding="utf-8"))["page"] == ""
    # what's open stays open
    assert (out / "planner/index.html").read_text(encoding="utf-8") == "the product page"
    assert (out / "planner/sample-report/index.html").read_text(encoding="utf-8") == "the sample"
    assert (out / "about/index.html").read_text(encoding="utf-8") == "free"


def test_a_broken_secret_counts_as_no_users(monkeypatch):
    for bad in ("not json", "[]", '{"a": {}}', '{"a": {"salt": "", "kek": "AAAA"}}'):
        monkeypatch.setenv("COMPASS_USERS", bad)
        assert access.users() == {}


def test_sealed_pages_open_only_with_the_right_password(tmp_path, monkeypatch):
    aead = pytest.importorskip("cryptography.hazmat.primitives.ciphers.aead")
    out = site(tmp_path, monkeypatch)
    monkeypatch.setenv("COMPASS_USERS", json.dumps({"client one": access.new_user("client one", "long enough password")}))
    assert access.seal(out, None, []) == 2
    published = everything(out)
    assert SECRET not in published and "client one" not in published and "long enough password" not in published
    assert not (out / "planner/example/sheet.csv").exists()
    sealed = json.loads((out / "planner/plan/index.html").read_text(encoding="utf-8"))
    assert sealed["files"] == ["planner/example/sheet.csv"]
    entry = sealed["table"][access.user_id("Client One ")]  # as the browser looks it up: any case, spaces trimmed
    salt, iv, wrapped = (base64.b64decode(entry[k]) for k in ("salt", "iv", "key"))

    def read(password, box):
        key = aead.AESGCM(access.derive("client one", password, salt)).decrypt(iv, wrapped, None)
        raw = base64.b64decode(box)
        return aead.AESGCM(key).decrypt(raw[:12], raw[12:], None).decode()

    assert read("long enough password", sealed["page"]) == SECRET
    assert read("long enough password", (out / "planner/example/sheet.csv.sealed").read_text(encoding="ascii")) == SECRET
    with pytest.raises(Exception):
        read("the wrong password here", sealed["page"])


def test_each_build_has_its_own_key_so_a_removed_user_is_shut_out(tmp_path, monkeypatch):
    pytest.importorskip("cryptography")
    people = {"a": access.new_user("a", "first long password"), "b": access.new_user("b", "second long password")}
    out = site(tmp_path, monkeypatch)
    access.seal(out, None, [], people)
    first = json.loads((out / "planner/plan/index.html").read_text(encoding="utf-8"))
    out2 = site(tmp_path / "again", monkeypatch)
    access.seal(out2, None, [], {"b": people["b"]})
    second = json.loads((out2 / "planner/plan/index.html").read_text(encoding="utf-8"))
    assert access.user_id("a") in first["table"] and access.user_id("a") not in second["table"]
    assert first["table"][access.user_id("b")]["key"] != second["table"][access.user_id("b")]["key"]


def test_short_passwords_are_refused(tmp_path, monkeypatch):
    monkeypatch.setattr(access, "LOCAL", tmp_path / "users.json")
    monkeypatch.setattr(access.getpass, "getpass", lambda *_: "short")
    monkeypatch.setattr(access, "_publish", lambda people: pytest.fail("published"))
    with pytest.raises(SystemExit, match="Too short"):
        access.manage("add", "someone")
    assert not access.LOCAL.exists()


def test_the_secret_holds_no_password(tmp_path, monkeypatch):
    monkeypatch.setattr(access, "LOCAL", tmp_path / "users.json")
    monkeypatch.setattr(access.getpass, "getpass", lambda *_: "a very long password")
    told = []
    monkeypatch.setattr(access, "_publish", told.append)
    access.manage("add", "Someone")
    assert list(told[0]) == ["someone"] and "a very long password" not in json.dumps(told[0])
    access.manage("remove", "someone")
    assert told[-1] == {}
