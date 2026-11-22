"""The Pulse Pro Engine login (aipulse/access.py): nothing paid is readable in what gets published, and nothing in it
lets a password be guessed offline (21 Nov 2026: the web app checks passwords)."""
import base64
import json

import pytest

from aipulse import access

SECRET = "the words only a paying reader may read"


def site(tmp_path, monkeypatch):
    # the login page itself comes from Compass, which a public clone hasn't got
    monkeypatch.setattr(access, "_shell", lambda conn, cards, path, page, login, files: json.dumps(
        {"page": page, "login": login, "files": files}))
    out = tmp_path / "site"
    for rel, text in (("planner/index.html", "the product page"), ("planner/sample-report/index.html", "the sample"), ("planner/smartfeed/index.html", "the feed page"), ("planner/source-check/index.html", "the tool"),
                      ("planner/example/index.html", SECRET), ("planner/example/sheet.csv", SECRET),
                      ("planner/explore/index.html", "step one"), ("planner/questions/index.html", "step two"),
                      ("planner/plan/index.html", "step three"), ("planner/plan/rules/index.html", "its rules"),
                      ("planner/rules/index.html", "the rule book"), ("planner/store/index.html", "the shop")):
        (out / rel).parent.mkdir(parents=True, exist_ok=True)
        (out / rel).write_text(text, encoding="utf-8")
    (out / "about").mkdir()
    (out / "about" / "index.html").write_text("free", encoding="utf-8")
    return out


def everything(out):
    return "".join(p.read_text(encoding="utf-8") for p in out.rglob("*") if p.is_file())


def test_without_a_page_key_nothing_paid_is_published(tmp_path, monkeypatch):
    monkeypatch.delenv("COMPASS_LOGIN_KEY", raising=False)
    monkeypatch.setattr(access, "_ask", lambda fields: pytest.fail("asked the web app with no secret"))
    out = site(tmp_path, monkeypatch)
    access.seal(out, None, [])
    assert SECRET not in everything(out)
    assert not (out / "planner/example/sheet.csv").exists() and not (out / "planner/example/sheet.csv.sealed").exists()
    assert json.loads((out / "planner/example/index.html").read_text(encoding="utf-8"))["page"] == ""
    # what's open stays open
    assert (out / "planner/index.html").read_text(encoding="utf-8") == "the product page"
    assert (out / "planner/sample-report/index.html").read_text(encoding="utf-8") == "the sample"
    assert (out / "planner/smartfeed/index.html").read_text(encoding="utf-8") == "the feed page"  # each product's page
    assert "the tool" not in everything(out)  # Source check is behind the login too
    # 6 Nov 2026, owner: the dashboards stay open (the steps, the Resources, the shop); only what we sell is sealed
    for rel, text in (("explore", "step one"), ("questions", "step two"), ("plan", "step three"), ("plan/rules", "its rules"),
                      ("rules", "the rule book"), ("store", "the shop")):
        assert (out / f"planner/{rel}/index.html").read_text(encoding="utf-8") == text
    assert (out / "about/index.html").read_text(encoding="utf-8") == "free"


def test_a_refused_or_broken_answer_counts_as_no_key(monkeypatch):
    monkeypatch.setenv("COMPASS_LOGIN_KEY", "k" * 30)
    for answer in ({"ok": False}, {"ok": True, "kid": "", "key": base64.b64encode(b"x" * 32).decode()},
                   {"ok": True, "kid": "2026-11-21-ab", "key": base64.b64encode(b"short").decode()}, {"ok": True}):
        monkeypatch.setattr(access, "_ask", lambda fields, a=answer: a)
        assert access.page_key() is None

    def down(fields):
        raise OSError("no network")
    monkeypatch.setattr(access, "_ask", down)
    assert access.page_key() is None
    seen = []
    monkeypatch.setattr(access, "_ask", lambda fields: seen.append(fields) or {"ok": True, "kid": "2026-11-21-ab",
                                                                              "key": base64.b64encode(b"k" * 32).decode()})
    assert access.page_key() == ("2026-11-21-ab", b"k" * 32)
    assert seen == [{"action": "pro-key", "key": "k" * 30}]  # the secret goes in the body, never the address


def test_sealed_pages_open_only_with_the_build_key_and_carry_nothing_to_guess_from(tmp_path, monkeypatch):
    aead = pytest.importorskip("cryptography.hazmat.primitives.ciphers.aead")
    from cryptography.exceptions import InvalidTag
    out = site(tmp_path, monkeypatch)
    key = bytes(range(32))
    assert access.seal(out, None, [], ("2026-11-21-ab", key), "https://script.example/exec") == 3  # the report, its sheet and Source check
    published = everything(out)
    assert SECRET not in published and base64.b64encode(key).decode() not in published
    assert not (out / "planner/example/sheet.csv").exists()
    sealed = json.loads((out / "planner/example/index.html").read_text(encoding="utf-8"))
    assert sealed["files"] == ["planner/example/sheet.csv"]
    # the page names its key and where to log in, and nothing more: no salts, no wrapped keys, no user list
    assert sealed["login"] == {"url": "https://script.example/exec", "kid": "2026-11-21-ab"}

    def read(k, box):
        raw = base64.b64decode(box)
        return aead.AESGCM(k).decrypt(raw[:12], raw[12:], None).decode()

    assert read(key, sealed["page"]) == SECRET
    assert read(key, (out / "planner/example/sheet.csv.sealed").read_text(encoding="ascii")) == SECRET
    with pytest.raises(InvalidTag):  # the wrong key fails the AES-GCM check
        read(bytes(32), sealed["page"])


def test_the_login_box_asks_the_web_app_and_never_hashes_a_password_itself():
    js = access.SCRIPT
    assert "action:'pro-login'" in js and "kid:L.kid" in js and "compass-login-at" in js
    assert "PBKDF2" not in js and "deriveBits" not in js and "compass-table" not in js
    assert "Too many tries" in js  # the web app's lock, told plainly


def _owner(tmp_path, monkeypatch, password="a very long password"):
    monkeypatch.setattr(access, "LOCAL_KEY", tmp_path / "key")
    monkeypatch.delenv("COMPASS_LOGIN_KEY", raising=False)
    (tmp_path / "key").write_text("owner-secret-" + "x" * 20, encoding="utf-8")
    monkeypatch.setattr(access.getpass, "getpass", lambda *_: password)
    sent, built = [], []
    monkeypatch.setattr(access, "_ask", lambda fields: sent.append(fields) or {"ok": True})
    monkeypatch.setattr(access, "_rebuild", lambda: built.append(1))
    return sent, built


def test_short_passwords_are_refused(tmp_path, monkeypatch):
    sent, _ = _owner(tmp_path, monkeypatch, "short")
    with pytest.raises(SystemExit, match="Too short"):
        access.manage("add", "someone")
    assert sent == []


def test_users_are_kept_by_the_web_app_and_removing_one_rebuilds(tmp_path, monkeypatch):
    sent, built = _owner(tmp_path, monkeypatch)
    access.manage("add", "Someone ")
    assert sent[-1] == {"action": "pro-user", "op": "add", "name": "someone", "key": "owner-secret-" + "x" * 20,
                        "password": "a very long password"} and not built  # a new user needs no rebuild
    access.manage("remove", "someone")
    assert sent[-1]["op"] == "remove" and "password" not in sent[-1] and built == [1]  # a new key, which they never get
    assert not list(tmp_path.glob("*.json"))  # nothing about users is kept on the PC


def test_no_owner_key_means_no_change(tmp_path, monkeypatch):
    monkeypatch.setattr(access, "LOCAL_KEY", tmp_path / "missing")
    monkeypatch.delenv("COMPASS_LOGIN_KEY", raising=False)
    with pytest.raises(SystemExit, match="compass-user setup"):
        access.manage("remove", "someone")


def test_login_box_asks_each_clients_own_username_and_gives_one_email():
    # 15 Nov 2026, owner: each client its own username and password, typed in the box (6 Nov: one shared username);
    # under it Start a conversation (12 Nov 2026); no price table while every price is on request (owner, 20 Nov 2026)
    box = access._get_login()
    assert len(access.PRICES) == 5 and "<table" not in box and "Price on request" not in box
    assert "Start a conversation" in box and "mailto:" not in box
    assert "Or write to" not in box and "Pulse Store /" not in access.REQUEST and "Pulse Store)" not in access.REQUEST
    # the Store's paid add-ons (4 Nov 2026): named in the email; browsing the Store stays free
    assert "$xx" not in box and "Price (USD)" not in box
    # 6 Nov 2026, owner: no amount until set; readers email to ask
    assert all(p[2] == "Price on request" for p in access.PAID)
    assert all(n in access.REQUEST for n, *_ in access.STORE_ADDONS)
    # 6 Nov 2026, owner: no yearly price anywhere
    assert "a year" not in box and "yearly" not in access.REQUEST.lower()
    assert not hasattr(access, "CLIENT") and "That username or password is not right." in access.SCRIPT
    assert "sessionStorage" in access.SCRIPT and "localStorage" not in access.SCRIPT + access.HIDE  # the login lasts the visit
    # the Pro top bar adds its script before the first </body> it meets: one inside the login script broke the box
    assert "</body>" not in access.SCRIPT
    assert access.FAMILY + "index.html" in access.OPEN
