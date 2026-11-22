"""The login for Pulse Pro Engine's paid outputs (under planner/). The site is static (GitHub Pages): every paid page and
file is encrypted when the site is built (AES-256-GCM), and what is published is a login box and unreadable bytes.

21 Nov 2026 (backend plan, fix 3): the password is checked by the project's Apps Script web app (apps-script/Code.gs),
never in the page. Until then each page carried every user's key wrapped with their password, so anyone could download
a page and guess passwords offline as fast as their computer allowed. Now the page carries only the name of its key
(kid); the login box posts the username and password to the web app, which checks a salted hash, locks a username for
15 minutes after 5 wrong tries, and only then hands back the key. The key is the web app's own, one per UTC day (the
newest 2 kept); the build fetches today's with the COMPASS_LOGIN_KEY secret. Removing a user (`python -m aipulse
compass-user remove NAME`) works at once and drops the keys, so the next build is sealed with one they never get. The web
app unreachable, or the secret unset: the paid pages aren't published at all.
"""
from __future__ import annotations

import base64
import getpass
import json
import logging
import os
import shutil
import secrets
import subprocess
import urllib.parse
import urllib.request
from collections.abc import Callable
from pathlib import Path

from . import config

log = logging.getLogger(__name__)

ROOT = "planner"
# what anyone can read: the product pages and one sample report. Source check went behind the login on 3 Nov 2026: on real AI
# notes it flagged 206 of 306 correct sentences, so it stays there until it is fixed and measured again
# 4 Nov 2026: each Pulse Pro Engine product has its own open page (Compass is planner/ itself)
PRODUCTS = ("risk-monitor", "pulse-watch", "smartfeed", "pulse-store")
FAMILY = "pulse-pro/"  # its own address since 14 Nov 2026 (planner/ is Compass). What Pulse Pro Engine is: the five products, what each is for and what it costs
OPEN = ({"planner/index.html", "planner/sample-report/index.html", "planner/sample-report/sample-report.pdf"}
        | {f"planner/{p}/index.html" for p in PRODUCTS} | {FAMILY + "index.html"})
# each Pulse Pro Engine product's read-only sample (4 Nov 2026, the owner): everything under this folder is open too
OPEN_DIR = "planner/samples/"
# 4 Nov 2026, owner: the login blocked anyone from trying the product, so the first three steps (Explore, Questions, Plan
# your report) are open, with everything under them. The report itself (step 4), its PDF and the Resources stay sealed;
# the report's login box lists what the report holds
STEPS = ("planner/explore/", "planner/questions/", "planner/plan/")
REPORT = "planner/example/"
# 4 Nov 2026, owner: the Pulse Store has no price, so the shop behind its product page is open to everyone, with everything under it
STORE = "planner/store/"


# 6 Nov 2026, owner: everyone can see the demos and use the dashboards; only the finished outputs we sell need the
# password: the report and its PDF (step 4), the full worked risk table, and every download on the dashboards (a script
# on each Pro page, adoption.GATE, sends a download to the login box). Source check is not built (static.SOURCE_CHECK).
# The login page is sealed so that it shows the box. OPEN, STEPS and STORE are kept for the record of what was open when
# SmartFeed's data is the product itself: its query page, files and Python client (planner/api/) are sealed; the list of
# files (names and what a row is) and its sample stay open
SOLD = (REPORT, "planner/api/", "planner/login/", "planner/source-check/")
SOLD_PAGES = {"planner/matrix/index.html"}


def is_open(rel: str) -> bool:
    return not (rel.startswith(SOLD) or rel in SOLD_PAGES)


MIN_PASSWORD = 12
LOCAL_KEY = Path.home() / ".ai-pulse-compass-login-key"  # the owner's copy of COMPASS_LOGIN_KEY (the web app's PRO_KEY)
REPO = config.REPO
# 15 Nov 2026, owner: each client its own username and password (python -m aipulse compass-user add NAME), typed in the
# login box, so removing one client shuts out only that client. The shared "pulse-client" of 6 Nov still works while it
# is in the list, typed as its username


def _b64(raw: bytes) -> str:
    return base64.b64encode(raw).decode()


def login_url() -> str:
    from .subscribers import SIGNUP_URL
    return SIGNUP_URL


def _ask(fields: dict) -> dict:
    """One POST to the web app (secrets in the body, never the address); Google answers with a redirect to the reply."""
    body = urllib.parse.urlencode(fields).encode()
    with urllib.request.urlopen(urllib.request.Request(login_url(), data=body), timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))


def page_key() -> tuple[str, bytes] | None:
    """Today's page key from the web app, as (kid, key); None (and a warning) when it can't be had."""
    secret = config.compass_login_key()
    if not secret:
        log.warning("COMPASS_LOGIN_KEY isn't set: the paid pages stay unpublished.")
        return None
    try:
        got = _ask({"action": "pro-key", "key": secret})
        if not got.get("ok"):
            raise ValueError("refused")
        kid, key = str(got["kid"]), base64.b64decode(got["key"])
        if len(key) != 32 or not kid:
            raise ValueError("not a key")
        return kid, key
    except Exception as e:  # noqa: BLE001  any failure means no key, and nothing paid published
        log.warning("The login web app gave no page key (%s): the paid pages stay unpublished.", e)
        return None


# Runs on every sealed page: a saved login opens it at once, otherwise the form. The page replaces this one in place, so
# its address, its own scripts and the reader's saved answers all work as usual.
SCRIPT = r"""<script>
(function(){
var KEY='compass-login',S=crypto.subtle,L=JSON.parse(document.getElementById('compass-login-at').textContent),
    F=JSON.parse(document.getElementById('compass-files').textContent),
    P=document.getElementById('compass-page').textContent.trim(),f=document.getElementById('compass-form'),
    root=document.documentElement;
function bytes(s){return Uint8Array.from(atob(s),function(c){return c.charCodeAt(0)})}
function saved(){try{return JSON.parse(sessionStorage.getItem(KEY))}catch(e){return null}}
function forget(){try{sessionStorage.removeItem(KEY)}catch(e){}}
function box(key,s){var a=bytes(s);return S.decrypt({name:'AES-GCM',iv:a.slice(0,12)},key,a.slice(12))}
function show(){root.style.visibility='';if(f)f.hidden=false}
async function opened(keys){  // this build's key, from the keys the web app gave at login
  var k=keys&&keys[L.kid];if(!k||!P)throw 0;
  return S.importKey('raw',bytes(k),'AES-GCM',false,['decrypt'])}
async function enter(key){
  var html=new TextDecoder().decode(await box(key,P));
  if(document.readyState!=='complete')await new Promise(function(r){addEventListener('load',r)});  // over a page still loading, the write would add to it
  window.compassKey=key;window.compassFiles=F;window.compassForget=forget;
  document.open();document.write(html.replace(/<\/body>(?![\s\S]*<\/body>)/i,AFTER+'<\/body>'));document.close()}  // written <\/ so no page edit takes this for the page's own end
var AFTER='<sc'+'ript>('+function(){
  var b=document.querySelector('.cp > .back'),w=document.createElement('div'),me=document.createElement('span'),
      a=document.createElement('a'),who=(function(){try{return JSON.parse(sessionStorage.getItem('compass-login')).name}catch(e){}})();
  w.className='compass-bar';me.className='compass-acct';
  me.appendChild(document.createTextNode('Signed in'));
  a.href='/planner/';a.textContent='Log out';a.onclick=function(){window.compassForget()};me.appendChild(a);
  if(b){b.parentNode.insertBefore(w,b);w.appendChild(b)}else{w.style.justifyContent='flex-end';document.body.insertBefore(w,document.body.firstChild)}
  w.appendChild(me);
  var st=document.createElement('style');
  st.textContent='.compass-bar{display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px 16px;margin-top:24px}'
    +'.cp:has(> .ft) > .compass-bar{width:min(1120px,calc(100vw - 32px));margin-left:calc(50% - min(560px,50vw - 16px))}'
    +'.compass-bar > .back{margin:0!important}'
    +'.compass-acct{display:flex;align-items:center;gap:10px;font:400 14px/1.3 var(--body);color:var(--muted)}'
    +'.compass-acct a{color:var(--ink);text-decoration:none;border:1px solid var(--line);padding:5px 12px}'
    +'.compass-acct a:hover{border-color:var(--ink)}'
    +'@media print{.compass-acct{display:none}}';
  document.head.appendChild(st);
  document.addEventListener('click',async function(e){
    var l=e.target.closest&&e.target.closest('a[href]');if(!l)return;
    var path=l.pathname.replace(/^\//,'');if(window.compassFiles.indexOf(path)<0)return;
    e.preventDefault();
    var r=await fetch('/'+path+'.sealed',{cache:'no-cache'}),t=await r.text(),a2=Uint8Array.from(atob(t),function(c){return c.charCodeAt(0)});
    var plain=await crypto.subtle.decrypt({name:'AES-GCM',iv:a2.slice(0,12)},window.compassKey,a2.slice(12));
    var u=URL.createObjectURL(new Blob([plain])),d=document.createElement('a');
    d.href=u;d.download=path.split('/').pop();document.body.appendChild(d);d.click();d.remove();URL.revokeObjectURL(u)})
}+')()</sc'+'ript>';
var s=saved();
(async function(){
  if(s&&s.keys){try{await enter(await opened(s.keys));return}catch(e){}}
  show()})();
if(f)f.onsubmit=async function(e){
  e.preventDefault();
  var msg=document.getElementById('compass-msg'),b=f.querySelector('button'),name=f.name_.value.trim().toLowerCase(),pw=f.password.value;
  msg.textContent='Checking…';b.disabled=true;
  var r;
  try{r=await (await fetch(L.url,{method:'POST',body:new URLSearchParams({action:'pro-login',name:name,password:pw,kid:L.kid})})).json()}
  catch(x){msg.textContent='The login could not be reached. Please try again.';b.disabled=false;return}
  try{
    if(!r.ok)throw r;
    var key=await opened(r.keys);
    try{sessionStorage.setItem(KEY,JSON.stringify({keys:r.keys,name:name}))}catch(x){}
    await enter(key)
  }catch(x){
    msg.textContent=x&&x.locked?'Too many tries. Please wait 15 minutes and try again.'
      :x&&(x.stale||x.ok)?'The site is being updated. Please try again in a few minutes.'
      :'That username or password is not right.';b.disabled=false}
}})();
</script>"""
HIDE = ("<script>try{if(sessionStorage.getItem('compass-login'))document.documentElement.style.visibility='hidden'}"
        "catch(e){}</script>")
STYLE = ("<style>.compass-login{max-width:420px;margin:56px auto 64px;padding:32px 30px 26px;box-sizing:border-box;"
         "border:1px solid color-mix(in srgb,var(--ink) 18%,transparent);border-top:4px solid #F0E442;border-radius:10px;"
         "background:var(--bg)}"
         ".compass-login h1{display:block;width:auto;max-width:none;margin:0 0 6px;font:800 26px/1.2 var(--body);"
         "text-align:center}"
         ".compass-login .cl-lead{margin:0 0 24px;font:400 15px/1.45 var(--body);color:var(--muted);text-align:center}"
         ".compass-login label{display:block;margin:0 0 16px;font:600 14px/1.4 var(--body)}"
         ".compass-login input{display:block;width:100%;box-sizing:border-box;margin-top:6px;padding:11px 12px;"
         "font:400 16px var(--body);color:var(--ink);background:var(--bg);border:1px solid color-mix(in srgb,var(--ink) 35%,transparent);"
         "border-radius:6px}"
         ".compass-login input:focus{outline:2px solid #56B4E9;outline-offset:1px;border-color:#56B4E9}"
         ".compass-login button{display:block;width:100%;margin-top:6px;padding:12px;font:600 15px var(--body);color:var(--bg);"
         "background:var(--ink);border:1px solid var(--ink);border-radius:999px;cursor:pointer}"
         ".compass-login button:hover{filter:brightness(.95)}.compass-login button[disabled]{opacity:.6}"
         "#compass-msg{min-height:20px;margin:12px 0 0;font-size:14px;text-align:center}"
         ".compass-more{margin:18px 0 0;padding-top:16px;border-top:1px solid color-mix(in srgb,var(--ink) 14%,transparent);"
         "font-size:13.5px;"
         "line-height:1.6;text-align:center;color:var(--muted)}"
         ".cl-toc{margin:0 0 24px;padding:14px 16px;border:1px solid color-mix(in srgb,var(--ink) 14%,transparent);"
         "border-left:3px solid #56B4E9;border-radius:6px;font:400 14px/1.55 var(--body)}"
         ".cl-toc-h{margin:0 0 6px;font-weight:600}.cl-toc ol{margin:0;padding-left:22px}.cl-toc li{margin:0;padding:1px 0;border:0}.cl-toc li::before,.cl-toc li::after{content:none}"
         ".cl-toc small{color:var(--muted);font-size:12.5px}"
         ".compass-get{margin:22px 0 0;padding-top:18px;border-top:1px solid color-mix(in srgb,var(--ink) 14%,transparent)}"
         ".compass-get h2{margin:0 0 6px;font:700 17px/1.3 var(--body);text-align:center}"
         ".compass-get p{margin:0 0 12px;font:400 14px/1.5 var(--body);color:var(--muted)}"
         ".compass-get table{width:100%;border-collapse:collapse;margin:0 0 14px;font:400 14px/1.4 var(--body)}"
         ".compass-get th,.compass-get td{padding:7px 0;text-align:left;vertical-align:top;"
         "border-bottom:1px solid color-mix(in srgb,var(--ink) 12%,transparent)}"
         ".compass-get th{font-weight:600;font-size:12.5px;color:var(--muted)}"
         ".compass-get td+td,.compass-get th+th{text-align:right;white-space:nowrap;padding-left:12px}"
         ".compass-get .cg-mail{display:block;padding:11px;text-align:center;font:600 15px var(--body);color:var(--ink);"
         "text-decoration:none;border:1px solid var(--ink);border-radius:999px}"
         ".compass-get .cg-mail:hover{background:color-mix(in srgb,var(--ink) 6%,transparent)}"
         ".compass-get .cg-note{margin:10px 0 0;font-size:13px}"
         ".compass-get td small{display:block;font-size:12.5px;color:var(--muted)}"
         # 6 Nov 2026, owner: What Pulse Pro Engine is as a pill button, not a link
         ".compass-more .cg-more{display:inline-block;padding:9px 20px;font:600 14px var(--body);color:var(--ink);"
         "text-decoration:none;border:1px solid color-mix(in srgb,var(--ink) 30%,transparent);border-radius:999px}"
         ".compass-more .cg-more:hover{background:color-mix(in srgb,var(--ink) 6%,transparent)}"
         "@media (max-width:560px){.compass-login{margin:28px auto 40px;padding:24px 18px 20px}}</style>")

MAIL = "projectaipulse@gmail.com"
CONTACT = "pulse-pro/contact/"  # Pulse Pro Engine's Start a conversation form (private repo, pro_company.py)
# what each Pulse Pro Engine product costs (owner, 4 Nov 2026): set by hand here, paid on an invoice; the login is added once
# it is paid. (name, how it is billed, price, yearly price). The report is bought once; the three services run on,
# monthly. No yearly price anywhere (owner, 6 Nov 2026), so that column stays empty; the Store is free and needs no login.
# No amount shown until the owner sets them (6 Nov 2026); readers ask through Start a conversation (owner, 12 Nov 2026)
PRICES = (("Pulse Compass evidence report", "Bought once", "Price on request", ""),
          ("Pulse Risk Monitor", "Subscription", "Price on request", ""),
          ("Pulse Watch", "Subscription", "Price on request", ""),
          ("Pulse SmartFeed", "Subscription", "Price on request", ""),
          ("Pulse Store", "Free", "No login needed", ""))
# the Store's paid add-ons (owner, 4 Nov 2026): browsing stays free; the bundle check is bought once, the other two run
# on. Same columns as PRICES; the login box and What Pulse Pro Engine is list them under Pulse Store
STORE_ADDONS = (("Pulse Store Bundles", "Bought once", "Price on request", ""),
                ("Pulse Store Plus", "Subscription", "Price on request", ""),
                ("Pulse Store for Firms", "Subscription", "Price on request", ""))
PAID = [p for p in PRICES + STORE_ADDONS if p[1] != "Free"]
REQUEST = ("Hello Pulse Central,\n\nI would like a Pulse Pro Engine login.\n\n"
           "Name:\nFirm:\nRole:\nProduct (" + " / ".join(p[0] for p in PAID) + "):\n"
           "How I would like to pay (for example bank transfer or a card payment link):\n\n"
           "Please send the invoice. I understand the username and password follow once it is paid.\n\nThanks,\n")


def _get_login() -> str:
    """Under the form: how to get a login. 20 Nov 2026, owner: no price table while every price is on request; a
    list of names with no prices added nothing."""
    from urllib.parse import quote
    # 12 Nov 2026, owner: "Start a conversation" (the Pulse Pro Engine contact form) instead of an email link
    href = f"/{CONTACT}?about={quote('Prices')}"
    return ('<div class="compass-get"><h2>No login yet?</h2>'
            '<p>Logins are paid. Tell us which product you need and we reply with the price and an invoice.</p>'
            f'<a class="cg-mail" href="{href}">Start a conversation</a>'
            '<p class="cg-note">Your username and password follow once the invoice is paid. Please don\'t send card numbers.</p></div>')


def _contents() -> str:
    """The report's sections, as its contents page names them: all a visitor sees of the report without a login."""
    from .planner_example import APPENDIX, DOC, LETTERED
    models = {"models", "method"}  # only when the report compares models

    def item(key, name, attr=""):
        return f"<li{attr}>{name}{' <small>(when models are compared)</small>' if key in models else ''}</li>"
    # letters as the report gives them: an unlettered part (the model method) keeps no letter here either
    letter, rows = 0, []
    for k, n in DOC:
        if k in APPENDIX:
            letter += k in LETTERED
            rows.append(item(k, n, f' value="{letter}"' if k in LETTERED else ' style="list-style:none"'))
    return ('<div class="cl-toc"><p class="cl-toc-h">In your report</p><ol>'
            + "".join(item(k, n) for k, n in DOC if k not in APPENDIX)
            + '<li>Appendix<ol type="A">' + "".join(rows) + "</ol></li></ol></div>")


def _shell(conn, cards: list[dict], path: str, page: str, login: dict, files: list[str]) -> str:
    """The published page: the login box, with the real page beside it as unreadable bytes."""
    from . import adoption  # type: ignore[attr-defined]  # private repo, joined to the package at run time
    from . import pages, rss
    head, lead, extra = "Log in to Pulse Pro Engine", "Enter the username and password you were given.", ""
    if path == REPORT:
        head, lead, extra = ("Log in to see your report",
                             "Your answers are kept for this visit. Enter your username and password to read the report as a booklet and download it as a PDF.",
                             _contents())
    body = (STYLE + '<form class="compass-login" id="compass-form" hidden autocomplete="on">'
              f'<h1>{head}</h1><p class="cl-lead">{lead}</p>{extra}'
              '<label>Username<input name="name_" autocomplete="username" autocapitalize="none" spellcheck="false" required></label>'
              '<label>Password<input name="password" type="password" autocomplete="current-password" required></label>'
              '<button type="submit">Log in</button><p id="compass-msg" role="status"></p>'
              f'{_get_login()}'
              f'<p class="compass-more"><a class="cg-more" href="/{FAMILY}">What Pulse Pro Engine is</a></p></form>'
              '<noscript><p>Logging in needs JavaScript switched on.</p></noscript>'
              f'<script type="application/json" id="compass-login-at">{json.dumps(login)}</script>'
              f'<script type="application/json" id="compass-files">{json.dumps(files)}</script>'
              f'<script type="text/plain" id="compass-page">{page}</script>' + SCRIPT)
    html = pages.page("Log in · Pulse Pro Engine", "Log in to Pulse Pro Engine.", path,
                      f'<div class="ft jb ap">{body}</div>',
                      {"@context": "https://schema.org", "@type": "WebPage", "name": "Pulse Compass", "url": f"{rss.SITE}{path}"},
                      pages.frame(conn, len(cards)), ("/planner/", "About Pulse Compass"))
    # the Pulse Pro Engine top bar, as on the product page, in place of the news masthead; its Pro pill is the way back
    html = adoption.product_header(html).replace('<a class="back" href="/planner/">← About Pulse Compass</a>\n', "", 1)
    return html.replace('<meta charset="utf-8">', f'<meta charset="utf-8">\n<meta name="robots" content="noindex">\n{HIDE}', 1)


def seal(out: Path, conn, cards: list[dict], key: tuple[str, bytes] | None = None, url: str | None = None) -> int:
    """Replace every paid file under planner/ with its sealed form. Runs last in the build; returns the files sealed.
    key is (kid, key), today's from the web app when not given; url is where the login box posts."""
    root = out / ROOT
    if not root.is_dir():
        return 0
    key = page_key() if key is None else key
    box: Callable[[bytes], str] | None = None  # seals a page; None when no key could be had
    login = {"url": url or login_url(), "kid": key[0] if key else ""}
    if key:  # only then is the library needed: with no key nothing gets encrypted
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        sealer = AESGCM(key[1])

        def seal(raw: bytes) -> str:
            iv = os.urandom(12)
            return _b64(iv + sealer.encrypt(iv, raw, None))
        box = seal
    paid = [p for p in sorted(root.rglob("*")) if p.is_file() and not is_open(p.relative_to(out).as_posix())]
    files = [p.relative_to(out).as_posix() for p in paid if p.name != "index.html"]
    for p in paid:
        rel = p.relative_to(out).as_posix()
        raw = p.read_bytes()
        if p.name == "index.html":
            p.write_text(_shell(conn, cards, rel[:-len("index.html")], box(raw) if box else "", login, files), encoding="utf-8")
        else:
            if box:
                p.with_name(p.name + ".sealed").write_text(box(raw), encoding="ascii")
            p.unlink()
    log.info("Pulse Pro Engine: %d paid files %s.", len(paid), "sealed" if box else "left out (no page key)")
    return len(paid)


# ---------------------------------------------------------------- the owner's command: python -m aipulse compass-user


def _gh() -> str:
    return shutil.which("gh") or r"C:\Program Files\GitHub CLI\gh.exe"


def _rebuild() -> None:
    subprocess.run([_gh(), "workflow", "run", "pages.yml", "--repo", REPO, "--ref", "main", "-f", "run=quick"], check=True)


def _owner_key() -> str:
    key = config.compass_login_key() or (LOCAL_KEY.read_text(encoding="utf-8").strip() if LOCAL_KEY.exists() else "")
    if not key:
        raise SystemExit("No login key on this PC yet: run python -m aipulse compass-user setup first.")
    return key


def manage(action: str, name: str | None) -> None:
    """The owner's command. Users live in the login web app; the password goes to it over HTTPS and is kept there
    only as a salted hash."""
    if action == "setup":  # once: the secret the build and this command use to talk to the web app
        key = secrets.token_urlsafe(36)
        subprocess.run([_gh(), "secret", "set", "COMPASS_LOGIN_KEY", "--repo", REPO], input=key.encode(), check=True)
        LOCAL_KEY.write_text(key, encoding="utf-8")
        print("Saved as the GitHub secret COMPASS_LOGIN_KEY and on this PC. Now, in the sign-up script at\n"
              "script.google.com: Project Settings > Script properties > add PRO_KEY with this value, then save:\n\n"
              f"{key}\n\nThen add each user again: python -m aipulse compass-user add NAME")
        return
    if action == "list":
        got = _ask({"action": "pro-user", "op": "list", "key": _owner_key()})
        print("\n".join(got.get("names") or []) or ("No users yet." if got.get("ok") else got.get("text", "Refused.")))
        return
    if not name:
        raise SystemExit(f"Say which user: python -m aipulse compass-user {action} NAME")
    name = name.strip().lower()
    fields = {"action": "pro-user", "op": action, "name": name, "key": _owner_key()}
    if action == "add":
        password = getpass.getpass(f"Password for {name} (at least {MIN_PASSWORD} characters; nothing shows as you type): ")
        if len(password) < MIN_PASSWORD:
            raise SystemExit(f"Too short: at least {MIN_PASSWORD} characters.")
        if password != getpass.getpass("The same password again: "):
            raise SystemExit("The two didn't match; nothing changed.")
        fields["password"] = password
    got = _ask(fields)
    if not got.get("ok"):
        raise SystemExit(got.get("text") or "The web app refused it.")
    if action == "remove":
        _rebuild()  # the web app dropped the page keys: the rebuild seals everything with a new one
        print(f"Removed {name}: they can't log in from now. The site is rebuilding with a new key (about 5 minutes).")
    else:
        print(f"Saved {name}. They can log in now; nothing needs rebuilding.")
