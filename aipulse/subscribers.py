"""Subscriptions to the daily email, kept in the project's Gmail account and nowhere else.

A reader subscribes by sending an email from their own address to the project inbox (the site's "Daily digest"
button writes it for them): the subject is a command and the streams they want.

    SUBSCRIBE releases news research regulation policy     (no streams: all five)
    CHANGE regulation policy                                (same as SUBSCRIBE)
    UNSUBSCRIBE

The inbox is the list: each address's newest command says whether it's subscribed and to what. Nothing is stored
in the repository (it's public), and no address is ever printed (Actions logs are public too): only counts.
Gmail checks that a message really comes from its sender (SPF, DKIM, DMARC); a command that fails those checks is
ignored, so nobody can subscribe someone else. A new subscription gets one reply to confirm it; unsubscribing
deletes every email to and from that address, permanently, and gets no reply.

Read over IMAP with the same app password as sending (DIGEST_EMAIL, DIGEST_APP_PASSWORD).

    python -m aipulse subscribers [--dry-run]
"""

from __future__ import annotations

import imaplib
import re
import ssl
from dataclasses import dataclass
from datetime import datetime
from email import message_from_bytes, policy
from email.utils import parseaddr, parsedate_to_datetime

from . import digest, rss

IMAP_HOST = "imap.gmail.com"
COMMANDS = ("SUBSCRIBE", "CHANGE", "UNSUBSCRIBE")
MAX_SUBSCRIBERS = 400  # Gmail sends to about 500 recipients a day; room for alerts and confirmations
ADDRESS = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+$")
ALIASES = {"industry": "news", "tracker": "regulation", "release": "releases"}  # words a reader may type


@dataclass
class Command:
    uid: bytes
    address: str
    command: str
    streams: list[str]
    when: datetime
    answered: bool


def parse_subject(subject: str) -> tuple[str, list[str]] | None:
    """("SUBSCRIBE", streams) from a command subject, or None if it isn't one. Streams are checked against the
    five; none named (or none valid) means all five."""
    words = re.split(r"[\s,;]+", (subject or "").strip())
    command = words[0].upper() if words else ""
    if command not in COMMANDS:
        return None
    if command == "UNSUBSCRIBE":
        return command, []
    named = [ALIASES.get(w.lower(), w.lower()) for w in words[1:]]
    streams = [n for n in rss.FEEDS if n in named]
    return command, streams or list(rss.FEEDS)


def authenticated(msg, address: str) -> bool:
    """Did Gmail verify that this message comes from `address`'s domain? Only Gmail's own (topmost)
    Authentication-Results header counts; a sender can add others below it."""
    domain = address.rsplit("@", 1)[-1].lower()
    for header in msg.get_all("Authentication-Results") or []:
        header = str(header)
        if not header.strip().lower().startswith("mx.google.com"):
            continue
        low = header.lower()
        if re.search(r"\bdmarc=pass\b", low):
            return True
        aligned = rf"@(?:[a-z0-9-]+\.)*{re.escape(domain)}\b"
        return bool(re.search(rf"\bdkim=pass[^;]*header\.i={aligned}", low)
                    or re.search(rf"\bspf=pass[^;]*smtp\.mailfrom=[^;\s]*{aligned}", low))
    return False


def automatic(msg) -> bool:
    """An auto-reply or a list message: never a reader's command, and never answered (no mail loops)."""
    return (str(msg.get("Auto-Submitted", "no")).lower() != "no"
            or str(msg.get("Precedence", "")).lower() in ("bulk", "junk", "list")
            or bool(msg.get("List-Id")))


def plan(commands: list[Command]) -> tuple[dict[str, list[str]], list[tuple[Command, str]], list[bytes], set[str]]:
    """From every command in the inbox: (subscribers and their streams, replies to send as (command, kind),
    older commands to delete, addresses to erase). An address's newest command decides; kinds are
    "welcome", "changed" and "full" (the list has no room)."""
    latest: dict[str, list[Command]] = {}
    for c in sorted(commands, key=lambda c: c.when):
        latest.setdefault(c.address, []).append(c)
    subscribers, replies, delete, erase = {}, [], [], set()
    new = []
    for address, mine in latest.items():
        newest = mine[-1]
        delete += [c.uid for c in mine[:-1]]  # superseded: only the newest command is kept
        if newest.command == "UNSUBSCRIBE":
            erase.add(address)
        elif newest.answered:
            subscribers[address] = newest.streams
        else:
            new.append(newest)
    for c in sorted(new, key=lambda c: c.when):  # first come, first served when the list is nearly full
        if len(subscribers) >= MAX_SUBSCRIBERS:
            replies.append((c, "full"))
            delete.append(c.uid)
        else:
            subscribers[c.address] = c.streams
            replies.append((c, "welcome" if c.command == "SUBSCRIBE" else "changed"))
    return subscribers, replies, delete, erase


def reply(kind: str, streams: list[str]) -> tuple[str, str, str]:
    """(subject, text, HTML) of the one email a new or changed subscription gets."""
    names = ", ".join(rss.FEEDS[n][1] for n in streams)
    change, stop = digest._mailto("CHANGE " + " ".join(streams)), digest._mailto("UNSUBSCRIBE")
    if kind == "full":
        subject = "AI Pulse daily is full for now"
        lines = ["Thank you for subscribing to AI Pulse daily. The list is full at the moment, so you weren't added "
                 "and nothing about you is kept. Please try again in a few weeks.",
                 f"Meanwhile, every stream has a free RSS feed: {rss.SITE}"]
    else:
        subject = "You're subscribed to AI Pulse daily" if kind == "welcome" else "Your AI Pulse daily streams are changed"
        lines = [f"{'Welcome to AI Pulse daily!' if kind == 'welcome' else 'Done.'} Every morning you'll get the day "
                 f"before in AI, in one email: {names}.",
                 "It's sent at about 05:00 UTC (7:00 in Germany in summer, 6:00 in winter). Every story is tagged "
                 "with what it is, has a line of summary and links straight to the original.",
                 "We keep only your email address and the streams you chose, in the project's email account, to send "
                 "you the digest. Nothing is shared, tracked or sold.",
                 f"Change your streams: {change}",
                 f"Unsubscribe (this deletes your address and every email between us): {stop}",
                 f"AI Pulse is free and non-commercial: {rss.SITE}"]
    from html import escape
    html = ('<div style="font-family:Arial,sans-serif;max-width:600px;color:#1a1a1a;font-size:15px;line-height:1.55">'
            + "".join(f"<p>{escape(line)}</p>" for line in lines if not line.startswith(("Change your", "Unsubscribe")))
            + (f'<p><a href="{escape(change)}">Change your streams</a> · <a href="{escape(stop)}">Unsubscribe</a> '
               '(this deletes your address and every email between us)</p>' if kind != "full" else "")
            + "</div>")
    return subject, "\n\n".join(lines), html


class Mailbox:
    """The project's Gmail over IMAP: reads commands from All Mail and deletes for good (via the Trash)."""

    def __init__(self, address: str, password: str):
        self.me = address.lower()
        self.imap = imaplib.IMAP4_SSL(IMAP_HOST, 993, ssl_context=ssl.create_default_context(), timeout=60)
        self.imap.login(address, password)
        folders = {}
        for line in self.imap.list()[1]:
            m = re.match(rb'\((?P<flags>[^)]*)\) "[^"]*" (?P<name>.+)$', line or b"")
            for flag in (b"\\All", b"\\Trash"):
                if m and flag in m["flags"]:
                    folders[flag] = m["name"].decode()
        self.all, self.trash = folders[b"\\All"], folders[b"\\Trash"]

    def commands(self) -> list[Command]:
        self.imap.select(self.all)
        _, data = self.imap.uid("SEARCH", None, "OR", "OR", "SUBJECT", '"SUBSCRIBE"', "SUBJECT", '"CHANGE"',
                                "SUBJECT", '"UNSUBSCRIBE"')
        out = []
        for uid in (data[0] or b"").split():
            _, parts = self.imap.uid("FETCH", uid, "(FLAGS INTERNALDATE BODY.PEEK[HEADER])")
            header = parts[0][1]
            meta = parts[0][0] + b" " + b" ".join(p for p in parts[1:] if isinstance(p, bytes))  # flags may come last
            msg = message_from_bytes(header, policy=policy.default)
            address = parseaddr(str(msg.get("From", "")))[1].lower()
            parsed = parse_subject(str(msg.get("Subject", "")))
            if not parsed or address == self.me or not ADDRESS.match(address) or automatic(msg) \
                    or not authenticated(msg, address):
                continue
            when = imaplib.Internaldate2tuple(meta)
            out.append(Command(uid, address, parsed[0], parsed[1],
                               datetime(*when[:6]) if when else parsedate_to_datetime(str(msg["Date"])),
                               b"\\Answered" in meta))
        return out

    def answered(self, uid: bytes) -> None:
        self.imap.select(self.all)
        self.imap.uid("STORE", uid, "+FLAGS", "(\\Answered)")

    def delete(self, uids: list[bytes]) -> None:
        """Deletes messages for good: copied into the Trash (Gmail's way to delete), then expunged from it, found
        there by Gmail's own message id, which stays the same in every folder."""
        if not uids:
            return
        self.imap.select(self.all)
        _, data = self.imap.uid("FETCH", b",".join(uids), "(X-GM-MSGID)")
        ids = [m.decode() for part in data for m in re.findall(rb"X-GM-MSGID (\d+)", part if isinstance(part, bytes) else part[0])]
        self.imap.uid("COPY", b",".join(uids), self.trash)
        self.imap.select(self.trash)
        found = []
        for gm_id in ids:
            _, data = self.imap.uid("SEARCH", None, "X-GM-MSGID", gm_id)
            found += (data[0] or b"").split()
        if found:
            self.imap.uid("STORE", b",".join(found), "+FLAGS", "(\\Deleted)")
            self.imap.expunge()

    def erase(self, address: str) -> int:
        """Every email to or from `address`, deleted for good. Returns how many."""
        if not ADDRESS.match(address):
            return 0
        self.imap.select(self.all)
        _, data = self.imap.uid("SEARCH", None, "OR", "FROM", f'"{address}"', "TO", f'"{address}"')
        uids = (data[0] or b"").split()
        self.delete(uids)
        return len(uids)

    def close(self) -> None:
        try:
            self.imap.logout()
        except (imaplib.IMAP4.error, OSError):
            pass


def sync(address: str, password: str, dry_run: bool = False) -> dict[str, list[str]]:
    """Reads the inbox, answers new subscriptions, deletes superseded commands and erases unsubscribed readers.
    Returns the subscribers. A dry run only reads and reports counts."""
    box = Mailbox(address, password)
    try:
        subscribers, replies, delete, erase = plan(box.commands())
        kinds = {k: sum(1 for _, x in replies if x == k) for k in ("welcome", "changed", "full")}
        print(f"Subscribers: {len(subscribers)}. New: {kinds['welcome']}, changed: {kinds['changed']}, "
              f"list full: {kinds['full']}; unsubscribed: {len(erase)}; superseded commands: {len(delete)}"
              + (" (dry run: nothing sent or deleted)" if dry_run else ""))
        if dry_run:
            return subscribers
        for c, kind in replies:
            digest.send(c.address, *reply(kind, c.streams))
            if kind != "full":
                box.answered(c.uid)
        box.delete(delete)
        for gone in erase:
            box.erase(gone)
        return subscribers
    finally:
        box.close()


def confirmed(commands: list[Command]) -> dict[str, list[str]]:
    """Subscribers whose newest command was answered (the confirmation went out); nobody who unsubscribed."""
    subscribers, replies, _, _ = plan(commands)
    waiting = {c.address for c, _ in replies}
    return {a: s for a, s in subscribers.items() if a not in waiting}


def current(address: str, password: str) -> dict[str, list[str]]:
    """The confirmed subscribers, read only (for the daily send)."""
    box = Mailbox(address, password)
    try:
        return confirmed(box.commands())
    finally:
        box.close()
