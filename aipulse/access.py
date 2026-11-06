"""The login for Pulse Compass, the paid product (planner/). The site is static (GitHub Pages), so nothing can check a
password on a server: instead every paid page is encrypted when the site is built, and opens in the browser only with a
username and password the owner has set. Without one, what is published is a login box and unreadable bytes.

Each build makes a new random key and encrypts the pages with it (AES-256-GCM). For each user that key is encrypted again
with a key made from their username and password (PBKDF2-SHA256), so removing a user and building again shuts them out of
every later build. Passwords are never stored: `python -m aipulse compass-user` keeps only each user's salt and derived
key, on the owner's PC and in the COMPASS_USERS repo secret. There is no server to slow password guessing, so passwords
must be long. No users set, or no secret readable: the paid pages aren't published at all.
"""
from __future__ import annotations

import base64
import getpass
import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

ROOT = "planner"
# what anyone can read: the product pages and one sample report. Source check went behind the login on 3 Nov 2026: on real AI
# notes it flagged 206 of 306 correct sentences, so it stays there until it is fixed and measured again
# 4 Nov 2026: each Pulse Pro product has its own open page (Compass is planner/ itself)
PRODUCTS = ("risk-monitor", "pulse-watch", "smartfeed", "pulse-store", "pulse-pro")  # pulse-pro: the family page
FAMILY = "planner/pulse-pro/"  # What Pulse Pro is: the five products, what each is for and what it costs
OPEN = ({"planner/index.html", "planner/sample-report/index.html", "planner/sample-report/sample-report.pdf"}
        | {f"planner/{p}/index.html" for p in PRODUCTS})
# each Pulse Pro product's read-only sample (4 Nov 2026, the owner): everything under this folder is open too
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


ROUNDS = 600_000  # OWASP's figure for PBKDF2-SHA256; about half a second in a browser
MIN_PASSWORD = 12
LOCAL = Path.home() / ".ai-pulse-compass-users.json"  # the owner's copy of the secret: salts and derived keys, no passwords
REPO = "shru14/ai-pulse"
# 6 Nov 2026, owner: one username for every client, filled in by the page; a visitor types only the password
CLIENT = "pulse-client"


def _b64(raw: bytes) -> str:
    return base64.b64encode(raw).decode()


def user_id(name: str) -> str:
    """How the published table names a user: a hash, so the page doesn't list who the clients are."""
    return hashlib.sha256(f"pulse-compass:{name.strip().lower()}".encode()).hexdigest()


def derive(name: str, password: str, salt: bytes) -> bytes:
    return hashlib.pbkdf2_hmac("sha256", f"{name.strip().lower()}\n{password}".encode(), salt, ROUNDS, 32)


def new_user(name: str, password: str) -> dict:
    salt = os.urandom(16)
    return {"salt": _b64(salt), "kek": _b64(derive(name, password, salt))}


def users() -> dict:
    """The users the build may let in, from the COMPASS_USERS secret; anything unreadable counts as no users."""
    try:
        found = json.loads(os.environ.get("COMPASS_USERS") or "{}")
        return {n: u for n, u in found.items() if len(base64.b64decode(u["kek"])) == 32 and base64.b64decode(u["salt"])}
    except (ValueError, TypeError, KeyError, AttributeError):
        print("COMPASS_USERS can't be read: the paid pages stay unpublished.")
        return {}


# Runs on every sealed page: a saved login opens it at once, otherwise the form. The page replaces this one in place, so
# its address, its own scripts and the reader's saved answers all work as usual.
SCRIPT = r"""<script>
(function(){
var KEY='compass-login',S=crypto.subtle,T=JSON.parse(document.getElementById('compass-table').textContent),
    F=JSON.parse(document.getElementById('compass-files').textContent),
    P=document.getElementById('compass-page').textContent.trim(),f=document.getElementById('compass-form'),
    root=document.documentElement,enc=new TextEncoder();
function bytes(s){return Uint8Array.from(atob(s),function(c){return c.charCodeAt(0)})}
function b64(a){return btoa(String.fromCharCode.apply(null,new Uint8Array(a)))}
function saved(){try{return JSON.parse(sessionStorage.getItem(KEY))}catch(e){return null}}
function forget(){try{sessionStorage.removeItem(KEY)}catch(e){}}
function box(key,s){var a=bytes(s);return S.decrypt({name:'AES-GCM',iv:a.slice(0,12)},key,a.slice(12))}
function aes(raw,use){return S.importKey('raw',raw,'AES-GCM',false,[use])}
function show(){root.style.visibility='';if(f)f.hidden=false}
async function opened(id,kek){
  var e=T[id];if(!e||!P)throw 0;
  return aes(await S.decrypt({name:'AES-GCM',iv:bytes(e.iv)},await aes(kek,'decrypt'),bytes(e.key)),'decrypt')}
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
  if(s&&s.id&&s.kek){try{await enter(await opened(s.id,bytes(s.kek)));return}catch(e){forget()}}
  show()})();
if(f)f.onsubmit=async function(e){
  e.preventDefault();
  var msg=document.getElementById('compass-msg'),b=f.querySelector('button'),name=f.name_.value.trim().toLowerCase(),pw=f.password.value;
  msg.textContent='Checking…';b.disabled=true;
  try{
    var id=Array.from(new Uint8Array(await S.digest('SHA-256',enc.encode('pulse-compass:'+name)))).map(function(x){return x.toString(16).padStart(2,'0')}).join(''),
        e0=T[id];
    if(!e0)throw 0;
    var raw=await S.importKey('raw',enc.encode(name+'\n'+pw),'PBKDF2',false,['deriveBits']),
        kek=await S.deriveBits({name:'PBKDF2',hash:'SHA-256',salt:bytes(e0.salt),iterations:T._rounds},raw,256),
        key=await opened(id,kek);
    try{sessionStorage.setItem(KEY,JSON.stringify({id:id,kek:b64(kek),name:name}))}catch(x){}
    await enter(key)
  }catch(x){msg.textContent='That password is not right.';b.disabled=false}
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
         ".compass-login button{display:block;width:100%;margin-top:6px;padding:12px;font:600 15px var(--body);color:#000;"
         "background:#F0E442;border:1px solid #F0E442;border-radius:999px;cursor:pointer}"
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
         # 6 Nov 2026, owner: What Pulse Pro is as a pill button, not a link
         ".compass-more .cg-more{display:inline-block;padding:9px 20px;font:600 14px var(--body);color:var(--ink);"
         "text-decoration:none;border:1px solid color-mix(in srgb,var(--ink) 30%,transparent);border-radius:999px}"
         ".compass-more .cg-more:hover{background:color-mix(in srgb,var(--ink) 6%,transparent)}"
         "@media (max-width:560px){.compass-login{margin:28px auto 40px;padding:24px 18px 20px}}</style>")

MAIL = "projectaipulse@gmail.com"
# what each Pulse Pro product costs (owner, 4 Nov 2026): set by hand here, paid on an invoice; the login is added once
# it is paid. (name, how it is billed, price, yearly price). The report is bought once; the three services run on, so
# they are monthly, or yearly at ten months' price; the Store is free and needs no login
PRICES = (("Pulse Compass evidence report", "Bought once", "$499 a report", ""),
          ("Pulse Risk Monitor", "Subscription", "$199 a month", "$1,990 a year"),
          ("Pulse Watch", "Subscription", "$149 a month", "$1,490 a year"),
          ("Pulse SmartFeed", "Subscription", "$249 a month", "$2,490 a year"),
          ("Pulse Store", "Free", "No login needed", ""))
# the Store's paid add-ons (owner, 4 Nov 2026): browsing stays free; the bundle check is bought once, the other two run
# on. Same columns as PRICES; the login box and What Pulse Pro is list them under Pulse Store
STORE_ADDONS = (("Pulse Store Bundles", "Bought once", "$149 a pack", ""),
                ("Pulse Store Plus", "Subscription", "$49 a month", "$490 a year"),
                ("Pulse Store for Firms", "Subscription", "$299 a month", "$2,990 a year"))
PAID = [p for p in PRICES + STORE_ADDONS if p[1] != "Free"]
REQUEST = ("Hello AI Pulse,\n\nI would like a Pulse Pro login.\n\n"
           "Name:\nFirm:\nRole:\nProduct (" + " / ".join(p[0] for p in PAID) + "):\n"
           "For a subscription, monthly or yearly:\n"
           "How I would like to pay (for example bank transfer or a card payment link):\n\n"
           "Please send the invoice. I understand the username and password follow once it is paid.\n\nThanks,\n")


def _get_login() -> str:
    """Under the form: one email address for buying a login and for any other question (owner, 6 Nov 2026: no prices)."""
    from urllib.parse import quote
    href = f"mailto:{MAIL}?subject={quote('Pulse Pro')}"
    return ('<div class="compass-get"><h2>Buying, or a question?</h2>'
            '<p>Write to us to buy Pulse Pro or to ask anything about it.</p>'
            f'<a class="cg-mail" href="{href}">Email {MAIL}</a></div>')


def _contents() -> str:
    """The report's sections, as its contents page names them: all a visitor sees of the report without a login."""
    from .planner_example import APPENDIX, DOC
    models = {"models", "method"}  # only when the report compares models

    def item(key, name):
        return f"<li>{name}{' <small>(when models are compared)</small>' if key in models else ''}</li>"
    return ('<div class="cl-toc"><p class="cl-toc-h">In your report</p><ol>'
            + "".join(item(k, n) for k, n in DOC if k not in APPENDIX)
            + '<li>Appendix<ol type="A">' + "".join(item(k, n) for k, n in DOC if k in APPENDIX) + "</ol></li></ol></div>")


def _shell(conn, cards: list[dict], path: str, page: str, table: dict, files: list[str]) -> str:
    """The published page: the login box, with the real page beside it as unreadable bytes."""
    from . import adoption, pages, rss
    head, lead, extra = "Log in to Pulse Pro", "Enter the password you were given.", ""
    if path == REPORT:
        head, lead, extra = ("Log in to see your report",
                             "Your answers are kept for this visit. Enter the password to read the report and download it as a PDF.",
                             _contents())
    body = (STYLE + '<form class="compass-login" id="compass-form" hidden autocomplete="on">'
              f'<h1>{head}</h1><p class="cl-lead">{lead}</p>{extra}'
              f'<input type="hidden" name="name_" autocomplete="username" value="{CLIENT}">'
              '<label>Password<input name="password" type="password" autocomplete="current-password" required></label>'
              '<button type="submit">Log in</button><p id="compass-msg" role="status"></p>'
              f'{_get_login()}'
              f'<p class="compass-more"><a class="cg-more" href="/{FAMILY}">What Pulse Pro is</a></p></form>'
              '<noscript><p>Logging in needs JavaScript switched on.</p></noscript>'
              f'<script type="application/json" id="compass-table">{json.dumps(table)}</script>'
              f'<script type="application/json" id="compass-files">{json.dumps(files)}</script>'
              f'<script type="text/plain" id="compass-page">{page}</script>' + SCRIPT)
    html = pages.page("Log in · Pulse Pro", "Log in to Pulse Pro.", path,
                      f'<div class="ft jb ap">{body}</div>',
                      {"@context": "https://schema.org", "@type": "WebPage", "name": "Pulse Compass", "url": f"{rss.SITE}{path}"},
                      pages.frame(conn, len(cards)), ("/planner/", "About Pulse Compass"))
    # the Pulse Pro top bar, as on the product page, in place of the news masthead; its Pro pill is the way back
    html = adoption.product_header(html).replace('<a class="back" href="/planner/">← About Pulse Compass</a>\n', "", 1)
    return html.replace('<meta charset="utf-8">', f'<meta charset="utf-8">\n<meta name="robots" content="noindex">\n{HIDE}', 1)


def seal(out: Path, conn, cards: list[dict], people: dict | None = None) -> int:
    """Replace every paid file under planner/ with its sealed form. Runs last in the build; returns the files sealed."""
    root = out / ROOT
    if not root.is_dir():
        return 0
    people = users() if people is None else people
    box = None
    table: dict = {"_rounds": ROUNDS}
    if people:  # only then is the library needed: with no users nothing gets encrypted
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        key = os.urandom(32)
        sealer = AESGCM(key)

        def box(raw: bytes) -> str:
            iv = os.urandom(12)
            return _b64(iv + sealer.encrypt(iv, raw, None))

        for name, u in people.items():
            iv = os.urandom(12)
            table[user_id(name)] = {"salt": u["salt"], "iv": _b64(iv),
                                    "key": _b64(AESGCM(base64.b64decode(u["kek"])).encrypt(iv, key, None))}
    paid = [p for p in sorted(root.rglob("*")) if p.is_file() and not is_open(p.relative_to(out).as_posix())]
    files = [p.relative_to(out).as_posix() for p in paid if p.name != "index.html"]
    for p in paid:
        rel = p.relative_to(out).as_posix()
        raw = p.read_bytes()
        if p.name == "index.html":
            p.write_text(_shell(conn, cards, rel[:-len("index.html")], box(raw) if box else "", table, files), encoding="utf-8")
        else:
            if box:
                p.with_name(p.name + ".sealed").write_text(box(raw), encoding="ascii")
            p.unlink()
    print(f"Pulse Compass: {len(paid)} paid files sealed for {len(people)} users.")
    return len(paid)


# ---------------------------------------------------------------- the owner's command: python -m aipulse compass-user


def _gh() -> str:
    return shutil.which("gh") or r"C:\Program Files\GitHub CLI\gh.exe"


def _publish(people: dict) -> None:
    """Put the list in the repo secret and rebuild the site, so the change is live in a few minutes."""
    subprocess.run([_gh(), "secret", "set", "COMPASS_USERS", "--repo", REPO], input=json.dumps(people).encode(), check=True)
    subprocess.run([_gh(), "workflow", "run", "pages.yml", "--repo", REPO, "--ref", "main", "-f", "run=quick"], check=True)
    print("Saved. The site is rebuilding: the change is live in about 5 minutes.")


def manage(action: str, name: str | None) -> None:
    people = json.loads(LOCAL.read_text(encoding="utf-8")) if LOCAL.exists() else {}
    if action == "list":
        print("\n".join(sorted(people)) or "No users yet.")
        return
    if not name:
        raise SystemExit(f"Say which user: python -m aipulse compass-user {action} NAME")
    name = name.strip().lower()
    if action == "remove":
        if name not in people:
            raise SystemExit(f"No user called {name}.")
        del people[name]
    else:
        password = getpass.getpass(f"Password for {name} (at least {MIN_PASSWORD} characters; nothing shows as you type): ")
        if len(password) < MIN_PASSWORD:
            raise SystemExit(f"Too short: at least {MIN_PASSWORD} characters. With no server to stop repeated guesses, length is the protection.")
        if password != getpass.getpass("The same password again: "):
            raise SystemExit("The two didn't match; nothing changed.")
        people[name] = new_user(name, password)
    LOCAL.write_text(json.dumps(people, indent=1), encoding="utf-8")
    _publish(people)
