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
OPEN = {"planner/index.html", "planner/sample-report/index.html"}  # what anyone can read: the product page, one sample report
ROUNDS = 600_000  # OWASP's figure for PBKDF2-SHA256; about half a second in a browser
MIN_PASSWORD = 12
LOCAL = Path.home() / ".ai-pulse-compass-users.json"  # the owner's copy of the secret: salts and derived keys, no passwords
REPO = "shru14/ai-pulse"


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
function saved(){try{return JSON.parse(localStorage.getItem(KEY))}catch(e){return null}}
function forget(){try{localStorage.removeItem(KEY)}catch(e){}}
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
  document.open();document.write(html.replace(/<\/body>(?![\s\S]*<\/body>)/i,AFTER+'</body>'));document.close()}
var AFTER='<sc'+'ript>('+function(){
  var n=document.querySelector('.ap-res-nav'),a=document.createElement('a');
  a.href='/planner/';a.textContent='Log out';a.id='compass-out';a.style.cssText='font:400 14px/1.3 var(--body);color:inherit';
  a.onclick=function(){window.compassForget()};
  var w=document.createElement('p');w.style.cssText='margin:8px 0;text-align:right';w.className='compass-out';w.appendChild(a);
  if(n)n.parentNode.insertBefore(w,n.nextSibling);else{w.style.cssText='position:fixed;right:12px;bottom:8px;margin:0';document.body.appendChild(w)}
  var st=document.createElement('style');st.textContent='@media print{.compass-out{display:none}}';document.head.appendChild(st);
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
    try{localStorage.setItem(KEY,JSON.stringify({id:id,kek:b64(kek)}))}catch(x){}
    await enter(key)
  }catch(x){msg.textContent='That username or password is not right.';b.disabled=false}
}})();
</script>"""
HIDE = ("<script>try{if(localStorage.getItem('compass-login'))document.documentElement.style.visibility='hidden'}"
        "catch(e){}</script>")
STYLE = ("<style>.compass-login{max-width:380px;margin:26px 0 30px}.compass-login label{display:block;margin:0 0 14px;"
         "font:400 14px/1.4 var(--body)}.compass-login input{display:block;width:100%;box-sizing:border-box;margin-top:4px;"
         "padding:10px;font:400 16px var(--body);color:var(--ink);background:var(--bg);border:1px solid var(--ink)}"
         ".compass-login button{padding:10px 22px;font:600 15px var(--body);color:#000;background:#F0E442;"
         "border:1px solid #000;cursor:pointer}.compass-login button[disabled]{opacity:.6}"
         "#compass-msg{min-height:22px;margin:10px 0 0;font-size:14px}.compass-more{font-size:14px}</style>")


def _shell(conn, cards: list[dict], path: str, page: str, table: dict, files: list[str]) -> str:
    """The published page: the login box, with the real page beside it as unreadable bytes."""
    from . import adoption, pages, rss
    body = (STYLE + adoption.band(adoption.TITLE, "Log in to Pulse Compass.",
                                  "Pulse Compass is a paid service. Log in with the username and password you were given.")
            + '<form class="compass-login" id="compass-form" hidden autocomplete="on">'
              '<label>Username<input name="name_" autocomplete="username" autocapitalize="none" required></label>'
              '<label>Password<input name="password" type="password" autocomplete="current-password" required></label>'
              '<button type="submit">Log in</button><p id="compass-msg" role="status"></p></form>'
              '<noscript><p>Logging in needs JavaScript switched on.</p></noscript>'
              '<p class="compass-more"><a href="/planner/">What Pulse Compass is</a> · '
              '<a href="/planner/sample-report/">See a sample report</a> · No login yet? Write to '
              '<a href="mailto:projectaipulse@gmail.com">projectaipulse@gmail.com</a></p>'
              f'<script type="application/json" id="compass-table">{json.dumps(table)}</script>'
              f'<script type="application/json" id="compass-files">{json.dumps(files)}</script>'
              f'<script type="text/plain" id="compass-page">{page}</script>' + SCRIPT)
    html = pages.page("Log in · Pulse Compass", "Log in to Pulse Compass.", path,
                      f'<div class="ft jb ap">{body}</div>',
                      {"@context": "https://schema.org", "@type": "WebPage", "name": "Pulse Compass", "url": f"{rss.SITE}{path}"},
                      pages.frame(conn, len(cards)), ("/planner/", "About Pulse Compass"))
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
    paid = [p for p in sorted(root.rglob("*")) if p.is_file() and p.relative_to(out).as_posix() not in OPEN]
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
