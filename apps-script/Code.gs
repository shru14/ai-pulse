/**
 * AI Pulse daily: sign-ups for the email digest. A Google Apps Script web app in the project's Google account
 * (projectaipulse@gmail.com): free, no billing, and the list never leaves that account.
 *
 * Emails only ever link to the AI Pulse site (a link to script.google.com looks like phishing to spam filters);
 * the site's page then talks to this web app:
 *
 *   POST action=subscribe   email, streams  the site's form: stores a pending sign-up, emails a confirm link
 *                           more, less,     (SITE#confirm=token); with the reader's choices ("Make it yours":
 *                           words           labels separated by |), which start when they confirm
 *   POST action=confirm     t               the site's "Confirm" button: the reader is subscribed
 *   POST action=choices     t               the site's "Change my choices" (SITE#choices=token, in every email):
 *                                            the reader's streams and choices
 *   POST action=save        t, streams,     saves them at once (the link in the reader's own email is the proof
 *                           more, less,     it's them, as for unsubscribing)
 *                           words
 *   POST action=unsubscribe t               the site's "Unsubscribe" button (SITE#unsubscribe=token, in every
 *                                            email), or a mail app's one-click unsubscribe (RFC 8058, the
 *                                            List-Unsubscribe header): the address is deleted and our emails
 *                                            with it moved to the Trash
 *   GET  action=list        key             the confirmed readers, for the daily send (key = LIST_KEY)
 * With format=json the site gets {ok, title, text}; without it (an old link opened here) a small page.
 * The project inbox gets a short note when someone subscribes, changes streams or unsubscribes.
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
// A reader's choices: labels the site shows (the form sends them separated by |), and a few words of their own
const LIMITS = {more: 10, less: 40, words: 5};

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
    : p.action === "choices" ? choices(p.t)
    : p.action === "save" ? save(p)
    : {ok: false};
  return p.action === "subscribe" || p.format === "json" ? json(result) : page(result);
}

function read(email) {
  const raw = store().getProperty("s:" + email);
  return raw ? JSON.parse(raw) : null;
}

// The reader's choices from the form, trimmed and capped: plain labels and words only (letters, digits, spaces
// and a few marks), so nothing odd is ever stored or sent back.
function prefsFrom(p) {
  const clean = (raw, n) => [...new Set(String(raw || "").split("|")
    .map(s => s.replace(/[^\p{L}\p{N} &.,'’()\-]/gu, "").replace(/\s+/g, " ").trim())
    .filter(s => s.length > 1 && s.length <= 60))].slice(0, n);
  const out = {more: clean(p.more, LIMITS.more), less: clean(p.less, LIMITS.less), words: clean(p.words, LIMITS.words)};
  out.more = out.more.filter(s => !out.less.includes(s));  // never both
  return out;
}
const hasPrefs = pr => !!pr && (pr.more.length + pr.less.length + pr.words.length) > 0;
const summary = pr => [pr.more.length && `more of ${pr.more.join(", ")}`, pr.less.length && `leaving out ${pr.less.join(", ")}`,
                       pr.words.length && `your words ${pr.words.map(w => `"${w}"`).join(", ")}`].filter(Boolean).join("; ");

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
    // choices start with the confirm link too; a reader changing only streams keeps the choices they have
    const prefs = prefsFrom(p);
    if (hasPrefs(prefs)) rec.pendingPrefs = prefs; else delete rec.pendingPrefs;
    rec.asked = Date.now();
    rec.n += 1;
    props.setProperty("t:" + rec.ctoken, email);
    props.setProperty("s:" + email, JSON.stringify(rec));
    props.setProperty("sent:" + day, String(sentToday + 1));
    // A short, friendly, plain note with one ordinary link to the site: no button, nothing that reads like a campaign.
    const link = SITE + "#confirm=" + rec.ctoken;
    const change = rec.confirmed;
    const lines = change ? [
      "Hi again,",
      `You asked to change your AI Pulse daily streams to: ${names(streams)}.` +
        (hasPrefs(prefs) ? ` Your choices: ${summary(prefs)}.` : ""),
      "Open this link and press Confirm, and the change starts with the next morning's email:",
      link,
      "Didn't ask for this? No worries, just ignore this email and nothing changes.",
      "Cheers,\nTeam AI Pulse",
    ] : [
      "Hi there,",
      "Thanks for signing up for AI Pulse daily!",
      "AI Pulse is a free, non-commercial briefing on what's happening in AI. Every morning we read company blogs, " +
        "newsrooms, research archives and government sites, and sort the day's stories into clear streams, each " +
        "linked to the original reporting.",
      `You picked: ${names(streams)}.` + (hasPrefs(prefs) ? ` Your choices: ${summary(prefs)}.` : ""),
      "One last step: open this link and press Confirm, and your first digest arrives the next morning:",
      link,
      "Didn't sign up? No worries, just ignore this email: nothing will be sent, and the request disappears within a week.",
      `Tip: ${CONTACTS.charAt(0).toLowerCase()}${CONTACTS.slice(1)}`,
      "Cheers,\nTeam AI Pulse",
    ];
    MailApp.sendEmail({
      to: email, name: "AI Pulse", replyTo: SENDER,
      subject: change ? "Please confirm your new AI Pulse daily streams" : "Welcome to AI Pulse daily: please confirm",
      body: lines.join("\n\n"),
      htmlBody: `<div style="font-family:Arial,sans-serif;font-size:15px;line-height:1.55;color:#1a1a1a">` +
                lines.map(l => l === link ? `<p><a href="${esc(link)}">${esc(link)}</a></p>`
                                          : `<p>${esc(l).replace(/\n/g, "<br>")}</p>`).join("") +
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
    if (rec.pendingPrefs) rec.prefs = rec.pendingPrefs;
    rec.confirmed = true;
    rec.token = rec.token || Utilities.getUuid();  // the reader's own unsubscribe and "Change my choices" link
    delete rec.pending; delete rec.pendingPrefs; delete rec.ctoken;
    props.deleteProperty("t:" + t);
    props.setProperty("u:" + rec.token, email);
    props.setProperty("s:" + email, JSON.stringify(rec));
    notify(changed ? `AI Pulse: a subscriber changed streams (${count()} subscribers)`
                   : `AI Pulse: new subscriber (${count()} subscribers)`,
           `${email} ${changed ? "now gets" : "subscribed to"}: ${names(rec.streams)}.` +
           (hasPrefs(rec.prefs) ? ` Choices: ${summary(rec.prefs)}.` : ""));
    return {ok: true, title: changed ? "Your streams are changed" : "Welcome aboard, you're subscribed!",
            text: `${changed ? "From tomorrow" : "Every morning"} you'll get the day before in AI: ${names(rec.streams)}. ` +
                  "It's sent at about 05:00 UTC (7:00 in Germany in summer), and every email has a one-click " +
                  `unsubscribe link. ${CONTACTS}`};
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
  // Our emails with this reader, and our notes naming them, go to the Trash (Gmail deletes it for good after 30 days).
  let threads;
  while ((threads = GmailApp.search(`to:${email} OR from:${email} OR "${email}"`, 0, 100)).length)
    GmailApp.moveThreadsToTrash(threads);
  notify(`AI Pulse: someone unsubscribed (${count()} subscribers)`,
         "A reader unsubscribed; their address is deleted, so it isn't named here.");
  return {ok: true, title: "You're unsubscribed",
          text: "Your address is deleted from AI Pulse daily, and our emails with you are deleted within 30 days. " +
                "You won't hear from us again."};
}

// "Change my choices": the link in every email (SITE#choices=token) opens the form filled in with what the reader
// has; saving changes it at once, as that link is the reader's own.
function choices(t) {
  const email = t && store().getProperty("u:" + t), rec = email && read(email);
  if (!rec || !rec.confirmed) return {ok: false, title: "This link doesn't work any more",
                                      text: "Subscribe again with the Daily digest button."};
  const pr = rec.prefs || {more: [], less: [], words: []};
  return {ok: true, streams: rec.streams, more: pr.more, less: pr.less, words: pr.words};
}

function save(p) {
  const streams = String(p.streams || "").split(/[\s,]+/).filter(s => s in STREAMS);
  if (!streams.length) return {ok: false, error: "streams"};
  const lock = LockService.getScriptLock();
  lock.waitLock(20000);
  let email, rec;
  try {
    email = p.t && store().getProperty("u:" + p.t);
    rec = email && read(email);
    if (!rec || !rec.confirmed) return {ok: false, error: "link"};
    rec.streams = streams;
    rec.prefs = prefsFrom(p);
    store().setProperty("s:" + email, JSON.stringify(rec));
  } finally {
    lock.releaseLock();
  }
  notify(`AI Pulse: a subscriber changed their choices (${count()} subscribers)`,
         `${email} now gets: ${names(streams)}.` + (hasPrefs(rec.prefs) ? ` Choices: ${summary(rec.prefs)}.` : ""));
  return {ok: true, title: "Saved", text: `From tomorrow's email: ${names(streams)}` +
          (hasPrefs(rec.prefs) ? `; ${summary(rec.prefs)}.` : ".")};
}

// The daily email starts here, on time: GitHub's own scheduler starts runs late or not at all (it never started the
// email on 30 Sep 2026), while Apps Script's timers are punctual. Each morning a timer asks GitHub to run the email
// workflow (digest.yml); that run checks the day, sends it once to every subscriber and marks it sent, so the
// workflow's own schedule and the site's backup starting it too never send twice.
// Setup, once: Project Settings > Script properties > GITHUB_TOKEN = a fine-grained GitHub token for this repository
// only, with the one permission "Actions: Read and write" (never in this file: the repository is public); then run
// setUpDailyTimers from the editor and allow the new permission it asks for.
const REPO = "shru14/ai-pulse";
const START_HOURS_UTC = [5, 6];  // about 05:15 UTC (Google fires within ~15 minutes), and a second chance at 06:15

function setUpDailyTimers() {
  ScriptApp.getProjectTriggers().filter(t => t.getHandlerFunction() === "startDailyEmail")
    .forEach(t => ScriptApp.deleteTrigger(t));
  START_HOURS_UTC.forEach(h => ScriptApp.newTrigger("startDailyEmail").timeBased().atHour(h).nearMinute(15)
    .everyDays(1).inTimezone("Etc/UTC").create());
  startDailyEmail(true);  // checks the token now: an alert comes at once if GitHub refuses it
}

function startDailyEmail(check) {
  const token = store().getProperty("GITHUB_TOKEN");
  const answer = token ? UrlFetchApp.fetch(`https://api.github.com/repos/${REPO}/actions/workflows/digest.yml/dispatches`, {
    method: "post", contentType: "application/json", muteHttpExceptions: true,
    headers: {Authorization: "Bearer " + token, Accept: "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"},
    payload: JSON.stringify({ref: "main", inputs: {dry_run: check === true ? "true" : "false"}}),
  }) : null;
  const code = answer ? answer.getResponseCode() : 0;
  if (code === 204) return console.log(check === true ? "GitHub accepted the token (a dry run started)." : "Daily email started.");
  notify("AI Pulse: the daily email could not be started",
         (token ? `GitHub answered ${code}: ${answer.getContentText().slice(0, 300)}` : "No GITHUB_TOKEN script property.") +
         "\nThe token may have expired or lost its Actions permission: make a new one and save it as GITHUB_TOKEN." +
         " The workflow's own schedule may still send it; to send by hand: GitHub > Actions > Daily digest > Run workflow, dry run unticked.");
}

// A note to the project inbox when someone subscribes, changes streams or unsubscribes. It never stops the
// reader's own step if it fails.
function notify(subject, text) {
  try {
    MailApp.sendEmail({to: SENDER, name: "AI Pulse", subject, body: text});
  } catch (e) {
    console.log("notice not sent: " + e);
  }
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
    if (rec.confirmed) out.push({email, streams: rec.streams, token: rec.token, ...(rec.prefs || {})});
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
