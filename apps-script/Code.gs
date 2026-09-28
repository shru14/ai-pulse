/**
 * AI Pulse daily: sign-ups for the email digest. A Google Apps Script web app in the project's Google account
 * (projectaipulse@gmail.com): free, no billing, and the list never leaves that account.
 *
 *   POST action=subscribe  email, streams   the site's form: stores a pending sign-up, emails a confirm link
 *   GET  action=confirm    t                a page with a "Confirm" button (link scanners can't confirm)
 *   POST action=confirm    t                the button: the reader is subscribed
 *   GET  action=unsubscribe t               a page with an "Unsubscribe" button (the link in every email)
 *   POST action=unsubscribe t               the button, or a mail app's one-click unsubscribe (RFC 8058):
 *                                            the address is deleted and its emails moved to the Trash
 *   GET  action=list       key              the confirmed readers, for the daily send (key = LIST_KEY)
 *
 * Script property LIST_KEY: a long random secret, also saved as the GitHub secret DIGEST_LIST_KEY. It's
 * set in Project Settings > Script properties, never in this file (the repository is public).
 * Deploy: Deploy > New deployment > Web app, "Execute as: Me", "Who has access: Anyone".
 */

const SITE = "https://shru14.github.io/ai-pulse/";
const STREAMS = {releases: "Releases", news: "Industry", research: "Research", regulation: "Regulation tracker",
                 policy: "Policy"};
const MAX_SUBSCRIBERS = 400;        // Gmail sends to about 500 recipients a day
const MAX_CONFIRMATIONS_A_DAY = 80; // Apps Script may send 100 emails a day from a free account
const MAX_PER_ADDRESS_A_DAY = 3;    // nobody can flood an inbox with confirm links
const PENDING_DAYS = 7;             // an unconfirmed sign-up is deleted after a week
const EMAIL = /^[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)+$/;

const store = () => PropertiesService.getScriptProperties();
const today = () => new Date().toISOString().slice(0, 10);
const json = x => ContentService.createTextOutput(JSON.stringify(x)).setMimeType(ContentService.MimeType.JSON);
const esc = s => String(s).replace(/[&<>"']/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"})[c]);
const names = streams => streams.map(s => STREAMS[s]).join(", ");

function doGet(e) {
  const p = e.parameter || {};
  if (p.action === "list") return json(list(p.key));
  if (p.action === "confirm" || p.action === "unsubscribe") return button(p.action, p.t);
  return page("AI Pulse daily", `<p>Sign up for the daily digest on <a href="${SITE}" target="_top">AI Pulse</a>.</p>`);
}

function doPost(e) {
  const p = e.parameter || {};
  if (p["List-Unsubscribe"] === "One-Click") return (unsubscribe(p.t), json({ok: true}));
  if (p.action === "subscribe") return json(subscribe(p));
  if (p.action === "confirm") return confirm(p.t);
  if (p.action === "unsubscribe") return unsubscribe(p.t)
    ? page("You're unsubscribed", "<p>Your address is deleted from AI Pulse daily, and our emails with you are " +
           "deleted within 30 days. You won't hear from us again.</p>")
    : page("Already unsubscribed", "<p>This address isn't on the list.</p>");
  return json({ok: false});
}

function read(email) {
  const raw = store().getProperty("s:" + email);
  return raw ? JSON.parse(raw) : null;
}

function subscribe(p) {
  if (p.website) return {ok: true};  // the hidden field only bots fill in
  const email = String(p.email || "").trim().toLowerCase();
  const streams = String(p.streams || "").split(/[\s,]+/).filter(s => s in STREAMS);
  if (!EMAIL.test(email) || email.length > 254) return {ok: false, error: "email"};
  if (!streams.length) return {ok: false, error: "streams"};
  const lock = LockService.getScriptLock();
  lock.waitLock(20000);
  try {
    const props = store();
    const rec = read(email) || {streams: [], confirmed: false};
    if (!rec.confirmed && count() >= MAX_SUBSCRIBERS) return {ok: false, error: "full"};
    const day = today(), sentToday = Number(props.getProperty("sent:" + day) || 0);
    if (rec.day !== day) { rec.day = day; rec.n = 0; }
    if (rec.n >= MAX_PER_ADDRESS_A_DAY || sentToday >= MAX_CONFIRMATIONS_A_DAY || MailApp.getRemainingDailyQuota() < 5)
      return {ok: false, error: "busy"};
    if (rec.ctoken) props.deleteProperty("t:" + rec.ctoken);
    rec.ctoken = Utilities.getUuid();
    rec.pending = streams;
    rec.asked = Date.now();
    rec.n += 1;
    props.setProperty("t:" + rec.ctoken, email);
    props.setProperty("s:" + email, JSON.stringify(rec));
    props.setProperty("sent:" + day, String(sentToday + 1));
    const link = ScriptApp.getService().getUrl() + "?action=confirm&t=" + rec.ctoken;
    const what = rec.confirmed ? "change your AI Pulse daily streams to" : "get AI Pulse daily, with";
    MailApp.sendEmail({
      to: email, name: "AI Pulse",
      subject: rec.confirmed ? "Confirm your new AI Pulse daily streams" : "Confirm your AI Pulse daily subscription",
      body: `Someone, hopefully you, asked to ${what}: ${names(streams)}.\n\nConfirm: ${link}\n\n` +
            "If it wasn't you, ignore this email: nothing will be sent and the request is deleted within a week.",
      htmlBody: `<div style="font-family:Arial,sans-serif;font-size:15px;line-height:1.55;color:#1a1a1a;max-width:560px">` +
                `<p>Someone, hopefully you, asked to ${what}: <b>${esc(names(streams))}</b>.</p>` +
                `<p><a href="${esc(link)}" style="display:inline-block;background:#2F4FD8;color:#fff;padding:10px 18px;` +
                `border-radius:8px;text-decoration:none;font-weight:bold">Confirm</a></p>` +
                "<p style=\"color:#5f6368;font-size:13px\">If it wasn't you, ignore this email: nothing will be sent " +
                "and the request is deleted within a week.</p></div>"
    });
    return {ok: true, change: !!rec.confirmed};
  } finally {
    lock.releaseLock();
  }
}

function confirm(t) {
  const lock = LockService.getScriptLock();
  lock.waitLock(20000);
  try {
    const props = store(), email = t && props.getProperty("t:" + t), rec = email && read(email);
    if (!rec || rec.ctoken !== t || Date.now() - rec.asked > PENDING_DAYS * 864e5)
      return page("This link has expired", `<p>Please sign up again on <a href="${SITE}" target="_top">AI Pulse</a>.</p>`);
    if (!rec.confirmed && count() >= MAX_SUBSCRIBERS)
      return page("AI Pulse daily is full for now", "<p>Please try again in a few weeks.</p>");
    const changed = rec.confirmed;
    rec.streams = rec.pending;
    rec.confirmed = true;
    rec.token = rec.token || Utilities.getUuid();  // the reader's own unsubscribe link
    delete rec.pending; delete rec.ctoken;
    props.deleteProperty("t:" + t);
    props.setProperty("u:" + rec.token, email);
    props.setProperty("s:" + email, JSON.stringify(rec));
    return page(changed ? "Your streams are changed" : "You're subscribed",
      `<p>Every morning you'll get the day before in AI: <b>${esc(names(rec.streams))}</b>. It's sent at about ` +
      "05:00 UTC (7:00 in Germany in summer). Every email has a one-click unsubscribe link.</p>" +
      `<p><a href="${SITE}" target="_top">Back to AI Pulse</a></p>`);
  } finally {
    lock.releaseLock();
  }
}

function unsubscribe(t) {
  const lock = LockService.getScriptLock();
  lock.waitLock(20000);
  let email;
  try {
    const props = store();
    email = t && props.getProperty("u:" + t);
    if (!email) return false;
    const rec = read(email);
    if (rec && rec.ctoken) props.deleteProperty("t:" + rec.ctoken);
    props.deleteProperty("u:" + t);
    props.deleteProperty("s:" + email);
  } finally {
    lock.releaseLock();
  }
  // Our emails with this reader go to the Trash (Gmail deletes it for good after 30 days).
  let threads;
  while ((threads = GmailApp.search(`to:${email} OR from:${email}`, 0, 100)).length) GmailApp.moveThreadsToTrash(threads);
  return true;
}

function count() {
  return Object.entries(store().getProperties())
    .filter(([k, v]) => k.startsWith("s:") && JSON.parse(v).confirmed).length;
}

function list(key) {
  const secret = store().getProperty("LIST_KEY");
  if (!secret || secret.length < 24 || key !== secret) return {ok: false};
  const props = store(), out = [], cutoff = Date.now() - PENDING_DAYS * 864e5;
  for (const [k, v] of Object.entries(props.getProperties())) {
    if (k.startsWith("sent:") && k < "sent:" + today()) props.deleteProperty(k);
    if (!k.startsWith("s:")) continue;
    const rec = JSON.parse(v), email = k.slice(2);
    if (rec.confirmed) out.push({email, streams: rec.streams, token: rec.token});
    else if (rec.asked < cutoff) {  // never confirmed: forgotten
      if (rec.ctoken) props.deleteProperty("t:" + rec.ctoken);
      props.deleteProperty(k);
    }
  }
  return {ok: true, unsubscribe: ScriptApp.getService().getUrl() + "?action=unsubscribe&t=", subscribers: out};
}

function button(action, t) {
  const label = action === "confirm" ? "Confirm my subscription" : "Unsubscribe";
  return page(action === "confirm" ? "One more click" : "Unsubscribe from AI Pulse daily",
    `<form method="post" action="${esc(ScriptApp.getService().getUrl())}" target="_top">` +
    `<input type="hidden" name="action" value="${esc(action)}"><input type="hidden" name="t" value="${esc(t || "")}">` +
    `<button style="background:#2F4FD8;color:#fff;border:0;border-radius:8px;padding:11px 20px;font-size:15px;` +
    `font-weight:bold;cursor:pointer">${label}</button></form>`);
}

function page(title, body) {
  return HtmlService.createHtmlOutput(
    `<div style="font-family:Arial,sans-serif;max-width:520px;margin:48px auto;padding:0 16px;color:#1a1a1a;` +
    `font-size:16px;line-height:1.55"><h2 style="margin:0 0 12px">${esc(title)}</h2>${body}</div>`)
    .setTitle("AI Pulse daily");
}
