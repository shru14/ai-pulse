/**
 * AI Pulse daily: sign-ups for the email digest. A Google Apps Script web app in the project's Google account
 * (projectaipulse@gmail.com): free, no billing, and the list never leaves that account.
 *
 * Emails only ever link to the AI Pulse site (a link to script.google.com looks like phishing to spam filters);
 * the site's page then talks to this web app:
 *
 *   POST action=subscribe   email, streams  the site's form: stores a pending sign-up, emails a confirm link
 *                                            (SITE#confirm=token)
 *   POST action=confirm     t               the site's "Confirm" button: the reader is subscribed
 *   POST action=unsubscribe t               the site's "Unsubscribe" button (SITE#unsubscribe=token, in every
 *                                            email), or a mail app's one-click unsubscribe (RFC 8058, the
 *                                            List-Unsubscribe header): the address is deleted and our emails
 *                                            with it moved to the Trash
 *   GET  action=list        key             the confirmed readers, for the daily send (key = LIST_KEY)
 * With format=json the site gets {ok, title, text}; without it (an old link opened here) a small page.
 *
 * Script property LIST_KEY: a long random secret, also saved as the GitHub secret DIGEST_LIST_KEY. It's
 * set in Project Settings > Script properties, never in this file (the repository is public).
 * Deploy: Deploy > New deployment > Web app, "Execute as: Me", "Who has access: Anyone". After editing:
 * Deploy > Manage deployments > edit > Version: New version (the address stays the same).
 */

const SITE = "https://shru14.github.io/ai-pulse/";
const SENDER = "projectaipulse@gmail.com";
const STREAMS = {releases: "Releases", news: "Industry", research: "Research", regulation: "Regulation tracker",
                 policy: "Policy"};
const MAX_SUBSCRIBERS = 400;        // Gmail sends to about 500 recipients a day
const MAX_CONFIRMATIONS_A_DAY = 80; // Apps Script may send 100 emails a day from a free account
const MAX_PER_ADDRESS_A_DAY = 3;    // nobody can flood an inbox with confirm links
const PENDING_DAYS = 7;             // an unconfirmed sign-up is deleted after a week
const EMAIL = /^[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)+$/;
const CONTACTS = `Add ${SENDER} to your contacts so the daily email lands in your inbox, not in spam.`;

const store = () => PropertiesService.getScriptProperties();
const today = () => new Date().toISOString().slice(0, 10);
const json = x => ContentService.createTextOutput(JSON.stringify(x)).setMimeType(ContentService.MimeType.JSON);
const esc = s => String(s).replace(/[&<>"']/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"})[c]);
const names = streams => streams.map(s => STREAMS[s]).join(", ");

function doGet(e) {
  const p = e.parameter || {};
  if (p.action === "list") return json(list(p.key));
  if (p.action === "confirm" || p.action === "unsubscribe") return button(p.action, p.t);  // links sent before the site handled them
  return page({title: "AI Pulse daily", text: "Sign up for the daily digest on the AI Pulse site."});
}

function doPost(e) {
  const p = e.parameter || {};
  if (p["List-Unsubscribe"] === "One-Click") return (unsubscribe(p.t), json({ok: true}));
  const result = p.action === "subscribe" ? subscribe(p)
    : p.action === "confirm" ? confirm(p.t)
    : p.action === "unsubscribe" ? unsubscribe(p.t)
    : {ok: false};
  return p.action === "subscribe" || p.format === "json" ? json(result) : page(result);
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
    // A short, plain note with one ordinary link to the site: no button, nothing that reads like a campaign.
    const link = SITE + "#confirm=" + rec.ctoken;
    const change = rec.confirmed;
    const lines = [
      "Hello,",
      change ? `You asked to change your AI Pulse daily streams to: ${names(streams)}.`
             : `You signed up for AI Pulse daily on ${SITE} with this address, for: ${names(streams)}.`,
      `To ${change ? "make the change" : "start getting it"}, open this link and press Confirm:`,
      link,
      `If this wasn't you, ignore this email: nothing will be sent, and the request is deleted within a week.`,
      CONTACTS,
      "AI Pulse",
    ];
    MailApp.sendEmail({
      to: email, name: "AI Pulse", replyTo: SENDER,
      subject: change ? "Please confirm your new AI Pulse daily streams" : "Please confirm your AI Pulse daily sign-up",
      body: lines.join("\n\n"),
      htmlBody: `<div style="font-family:Arial,sans-serif;font-size:15px;line-height:1.55;color:#1a1a1a">` +
                lines.map(l => l === link ? `<p><a href="${esc(link)}">${esc(link)}</a></p>` : `<p>${esc(l)}</p>`).join("") +
                "</div>"
    });
    return {ok: true, change};
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
      return {ok: false, title: "This link has expired", text: "Please sign up again with the Daily digest button."};
    if (!rec.confirmed && count() >= MAX_SUBSCRIBERS)
      return {ok: false, title: "AI Pulse daily is full for now", text: "Please try again in a few weeks."};
    const changed = rec.confirmed;
    rec.streams = rec.pending;
    rec.confirmed = true;
    rec.token = rec.token || Utilities.getUuid();  // the reader's own unsubscribe link
    delete rec.pending; delete rec.ctoken;
    props.deleteProperty("t:" + t);
    props.setProperty("u:" + rec.token, email);
    props.setProperty("s:" + email, JSON.stringify(rec));
    return {ok: true, title: changed ? "Your streams are changed" : "You're subscribed",
            text: `Every morning you'll get the day before in AI: ${names(rec.streams)}. It's sent at about 05:00 UTC ` +
                  `(7:00 in Germany in summer), and every email has a one-click unsubscribe link. ${CONTACTS}`};
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
    if (!email) return {ok: false, title: "Already unsubscribed", text: "This address isn't on the list."};
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
  return {ok: true, title: "You're unsubscribed",
          text: "Your address is deleted from AI Pulse daily, and our emails with you are deleted within 30 days. " +
                "You won't hear from us again."};
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
  return page({title: action === "confirm" ? "One more click" : "Unsubscribe from AI Pulse daily", text: ""},
    `<form method="post" action="${esc(ScriptApp.getService().getUrl())}" target="_top">` +
    `<input type="hidden" name="action" value="${esc(action)}"><input type="hidden" name="t" value="${esc(t || "")}">` +
    `<button style="background:#2F4FD8;color:#fff;border:0;border-radius:8px;padding:11px 20px;font-size:15px;` +
    `font-weight:bold;cursor:pointer">${label}</button></form>`);
}

function page(result, extra) {
  return HtmlService.createHtmlOutput(
    `<div style="font-family:Arial,sans-serif;max-width:520px;margin:48px auto;padding:0 16px;color:#1a1a1a;` +
    `font-size:16px;line-height:1.55"><h2 style="margin:0 0 12px">${esc(result.title)}</h2>` +
    (result.text ? `<p>${esc(result.text)}</p>` : "") + (extra || "") +
    `<p><a href="${SITE}" target="_top">AI Pulse</a></p></div>`)
    .setTitle("AI Pulse daily");
}
