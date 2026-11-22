/**
 * Pulse Daily: sign-ups for the email digest. A Google Apps Script web app in the project's Google account
 * (projectaipulse@gmail.com): free, no billing, and the list never leaves that account.
 *
 * Emails only ever link to the Pulse Central site (a link to script.google.com looks like phishing to spam filters);
 * the site's page then talks to this web app:
 *
 *   POST action=subscribe   email, streams  the site's form: the reader is subscribed at once, no email sent; with
 *                           more, less,     their choices ("Make it yours": labels separated by |). An address
 *                           words           already on the list is left as it is
 *   POST action=confirm     t               the site's "Confirm" button, for confirm links sent before one-click
 *                                            sign-up (31 Oct 2026); they run out within a week
 *   POST action=choices     t               the site's "Change my choices" (SITE#choices=token, in every email):
 *                                            the reader's streams and choices
 *   POST action=save        t, streams,     saves them at once (the link in the reader's own email is the proof
 *                           more, less,     it's them, as for unsubscribing); interests (the weekly dossier: up to
 *                           words,          3 in the reader's own words, separated by |) are kept as they are
 *                           interests,      when the form doesn't send them; often: "daily" (every email, the
 *                           often           week on Sundays too) or "weekly" (Sunday's email only), kept likewise
 *   POST action=unsubscribe t               the site's "Unsubscribe" button (SITE#unsubscribe=token, in every
 *                                            email), or a mail app's one-click unsubscribe (RFC 8058, the
 *                                            List-Unsubscribe header): the address is deleted and our emails
 *                                            with it moved to the Trash
 *   POST action=review      channels, uses, the site's review form (review/, from the daily email): answers only
 *                           useful,         from the lists in REVIEW (|-separated) and a note, emailed to the
 *                           section, opens, project inbox; nothing about the reader is sent or kept
 *                           length, pro,
 *                           proPick,
 *                           improve, other
 *   POST action=contact     name, email,    Pulse Pro Engine's "Start a conversation" form: emailed to the project inbox
 *                           firm, topic,    with Reply-To set to the sender, so a reply goes straight back; nothing
 *                           message         is kept here (owner, 12 Nov 2026)
 *   POST action=comment     post, name,     a reader's comment on a Pulse Pro Engine blog post: a row in the
 *                           comment         "Pulse blog comments" Sheet, shown only once the owner ticks Approved
 *   POST action=comments    post            the approved comments on that post (name, date, text)
 *   POST action=list        key           the confirmed readers, for the daily send (key = LIST_KEY; in the
 *                                            body, never the address, so it stays out of Google's logs)
 *   POST action=interests   key             every interest readers follow, once each and without who follows it,
 *                                            for the site's weekly dossiers (key = LIST_KEY)
 *   POST action=pro-login   name, password, Pulse Pro Engine's login box (aipulse/access.py): the password is checked
 *                           kid             here against a salted hash, so nothing a visitor can download lets them
 *                                            guess it offline; 5 wrong tries lock that username for 15 minutes.
 *                                            Right: the page keys kept now ({kid: key}); kid names the build's key
 *   POST action=pro-key     key             the site's build: today's page key, made on the first build of the UTC
 *                                            day; the newest 2 are kept, so a visit over midnight carries on
 *                                            (key = PRO_KEY)
 *   POST action=pro-user    key, op, name,  the owner's `python -m aipulse compass-user`: op add (with password),
 *                           password        remove or list (key = PRO_KEY). Removing someone also drops the page
 *                                            keys, so even an open visit can't read the next build
 *   POST action=watch-alert email, company, Pulse Watch's Notify me form: a row in the "Pulse Watch alerts" Sheet
 *                           events          (events: model, shutdown, ipo, money, court, government, pages)
 *   POST action=watch-alerts key            the active alert requests, for the daily alert job (key = LIST_KEY)
 *   POST action=watch-stop  t               the Stop link in each alert email: that address's requests stop
 * With format=json the site gets {ok, title, text}; without it (an old link opened here) a small page.
 * The project inbox gets a short note when someone subscribes, changes streams or unsubscribes.
 *
 * Script property LIST_KEY: a long random secret, also saved as the GitHub secret DIGEST_LIST_KEY. PRO_KEY
 * likewise, saved as the GitHub secret COMPASS_LOGIN_KEY (`python -m aipulse compass-user setup` makes it). They're
 * set in Project Settings > Script properties, never in this file (the repository is public).
 * Deploy: Deploy > New deployment > Web app, "Execute as: Me", "Who has access: Anyone". After editing:
 * Deploy > Manage deployments > edit > Version: New version (the address stays the same).
 */

const SITE = "https://projectaipulse.com/";
const SENDER = "projectaipulse@gmail.com";
const STREAMS = {releases: "Releases", news: "Industry", research: "Research", regulation: "Regulation tracker",
                 policy: "Policy", infra: "Infra"};
const MAX_SUBSCRIBERS = 400;        // Gmail sends to about 500 recipients a day
const MAX_SIGNUPS_A_DAY = 80;       // a bot can't fill the list in one go
const PENDING_DAYS = 7;             // an unconfirmed sign-up from before one-click is deleted after a week
const EMAIL = /^[A-Za-z0-9._%+-]+@([A-Za-z0-9-]+\.)+[A-Za-z]{2,}$/;  // no confirm step now: catches typos like name@site.x
const CONTACTS = `Add ${SENDER} to your contacts so the daily email lands in your inbox, not in spam.`;
// A reader's choices: labels the site shows (the form sends them separated by |), and a few words of their own
const LIMITS = {more: 10, less: 40, words: 5, interests: 3};
const INTEREST_MAX = 150;  // characters in one interest (aipulse/weekly.py INTEREST_MAX)

const store = () => PropertiesService.getScriptProperties();
const today = () => new Date().toISOString().slice(0, 10);
const json = x => ContentService.createTextOutput(JSON.stringify(x)).setMimeType(ContentService.MimeType.JSON);
const esc = s => String(s).replace(/[&<>"']/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"})[c]);
const names = streams => streams.map(s => STREAMS[s]).join(", ");

function doGet(e) {
  const p = e.parameter || {};
  if (p.action === "confirm" || p.action === "unsubscribe") return button(p.action, p.t);  // links sent before the site handled them
  return page({title: "Pulse Daily", text: "Sign up for the daily digest on the Pulse Central site."});
}

function doPost(e) {
  const p = e.parameter || {};
  if (p["List-Unsubscribe"] === "One-Click") return (unsubscribe(p.t), json({ok: true}));
  if (p.action === "list") return json(list(p.key));
  if (p.action === "interests") return json(interests(p.key));
  if (p.action === "comments") return json(comments(p));
  if (p.action === "comment") return json(comment(p));
  if (p.action === "pro-login") return json(proLogin(p));
  if (p.action === "pro-key") return json(proKey(p.key));
  if (p.action === "pro-user") return json(proUser(p));
  if (p.action === "watch-alert") return json(watchAlert(p));
  if (p.action === "watch-alerts") return json(watchAlerts(p.key));
  if (p.action === "watch-stop") return json(watchStop(p.t));
  const result = p.action === "subscribe" ? subscribe(p)
    : p.action === "confirm" ? confirm(p.t)
    : p.action === "unsubscribe" ? unsubscribe(p.t)
    : p.action === "choices" ? choices(p.t)
    : p.action === "save" ? save(p)
    : p.action === "review" ? review(p)
    : p.action === "contact" ? contact(p)
    : {ok: false};
  return p.action === "subscribe" || p.format === "json" ? json(result) : page(result);
}

function read(email) {
  const raw = store().getProperty("s:" + email);
  return raw ? JSON.parse(raw) : null;
}

// The reader's choices from the form, trimmed and capped: plain labels and words only (letters, digits, spaces
// and a few marks), so nothing odd is ever stored or sent back. Interests (sentences in the reader's own words)
// allow a few more marks; when the form doesn't send them, the reader keeps the ones they had (`had`).
function prefsFrom(p, had) {
  const clean = (raw, n) => [...new Set(String(raw || "").split("|")
    .map(s => s.replace(/[^\p{L}\p{N} &.,'’()\-]/gu, "").replace(/\s+/g, " ").trim())
    .filter(s => s.length > 1 && s.length <= 60))].slice(0, n);
  const out = {more: clean(p.more, LIMITS.more), less: clean(p.less, LIMITS.less), words: clean(p.words, LIMITS.words)};
  out.more = out.more.filter(s => !out.less.includes(s));  // never both
  out.interests = p.interests === undefined ? ((had && had.interests) || []) : cleanInterests(String(p.interests).split("|"));
  out.often = p.often === "weekly" || p.often === "daily" ? p.often : (had && had.often) || "daily";
  return out;
}
function cleanInterests(list) {
  const seen = new Set(), out = [];
  for (const raw of list) {
    const t = String(raw || "").replace(/[^\p{L}\p{N} &.,'’"“”()\-?!:;\/%$+#@]/gu, "").replace(/\s+/g, " ").trim().slice(0, INTEREST_MAX).trim();
    if (!/[\p{L}\p{N}]{2}/u.test(t) || seen.has(t.toLowerCase())) continue;
    seen.add(t.toLowerCase());
    out.push(t);
  }
  return out.slice(0, LIMITS.interests);
}
const hasChoices = pr => !!pr && pr.more.length + pr.less.length + pr.words.length + (pr.interests || []).length > 0;
const hasPrefs = pr => hasChoices(pr) || (!!pr && pr.often === "weekly");
const weeklyOnly = pr => !!pr && pr.often === "weekly";
const summary = pr => [weeklyOnly(pr) && "the weekly email only, on Sundays",
                       pr.more.length && `more of ${pr.more.join(", ")}`, pr.less.length && `leaving out ${pr.less.join(", ")}`,
                       pr.words.length && `your words ${pr.words.map(w => `"${w}"`).join(", ")}`,
                       (pr.interests || []).length && `a weekly dossier on ${pr.interests.map(w => `"${w}"`).join(", ")}`]
                      .filter(Boolean).join("; ");

function subscribe(p) {
  if (p.website) return {ok: true};  // the hidden field only bots fill in
  const email = String(p.email || "").trim().toLowerCase();
  const streams = String(p.streams || "").split(/[\s,]+/).filter(s => s in STREAMS);
  if (!EMAIL.test(email) || email.length > 254) return {ok: false, error: "email"};
  if (!streams.length) return {ok: false, error: "streams"};
  const lock = LockService.getScriptLock();
  lock.waitLock(20000);
  try {
    const props = store(), rec = read(email);
    // Anyone can type any address here, so a reader's streams change only from the link in their own email; and
    // the answer is the same as for a new reader, so the form never tells who is on the list.
    if (rec && rec.confirmed) return {ok: true};
    if (count() >= MAX_SUBSCRIBERS) return {ok: false, error: "full"};
    const day = today(), signups = Number(props.getProperty("sent:" + day) || 0);
    if (signups >= MAX_SIGNUPS_A_DAY) return {ok: false, error: "busy"};
    props.setProperty("sent:" + day, String(signups + 1));
    const prefs = prefsFrom(p);
    enroll(email, rec, streams, hasPrefs(prefs) ? prefs : undefined);
    notify(`Pulse Central: new subscriber (${count()} subscribers)`, `${email} subscribed to: ${names(streams)}.` +
           (hasPrefs(prefs) ? ` Choices: ${summary(prefs)}.` : ""));
    return {ok: true};
  } finally {
    lock.releaseLock();
  }
}

// Puts an address on the list: its own private token for the unsubscribe and "Change my choices" links in every email.
function enroll(email, rec, streams, prefs) {
  const props = store(), had = rec || {};
  if (had.ctoken) props.deleteProperty("t:" + had.ctoken);  // a confirm link from before is done with
  const token = Utilities.getUuid(), out = {streams, confirmed: true, token, asked: Date.now()};
  if (prefs) out.prefs = prefs;
  props.setProperty("u:" + token, email);
  props.setProperty("s:" + email, JSON.stringify(out));
}

// Run once by hand from the editor, for people who signed up when a confirm email was still asked for. Addresses go
// in the script property ADD_READERS, separated by spaces, commas or new lines, never in this file (the repository
// is public). No email is sent; each gets the next morning's digest. Readers already on the list are left as they
// are, a sign-up still waiting keeps the streams and choices it asked for, anyone else gets every stream, daily.
function addReaders() {
  const props = store(), raw = props.getProperty("ADD_READERS") || "";
  const emails = [...new Set(raw.split(/[\s,;]+/).map(s => s.trim().toLowerCase()).filter(Boolean))];
  const done = {added: 0, alreadyOn: 0, invalid: 0, noRoom: 0};
  let n = count();
  for (const email of emails) {
    const rec = read(email);
    if (!EMAIL.test(email) || email.length > 254) done.invalid++;
    else if (rec && rec.confirmed) done.alreadyOn++;
    else if (n >= MAX_SUBSCRIBERS) done.noRoom++;
    else {
      enroll(email, rec, (rec && rec.pending) || Object.keys(STREAMS), rec && rec.pendingPrefs);
      done.added++; n++;
    }
  }
  props.deleteProperty("ADD_READERS");
  const line = `Added ${done.added}; already on the list ${done.alreadyOn}; not valid ${done.invalid}; no room ${done.noRoom}. Now ${n} subscribers.`;
  console.log(line);
  notify("Pulse Central: readers added by hand", line);
}

function confirm(t) {
  const lock = LockService.getScriptLock();
  lock.waitLock(20000);
  try {
    const props = store(), email = t && props.getProperty("t:" + t), rec = email && read(email);
    if (!rec || rec.ctoken !== t || Date.now() - rec.asked > PENDING_DAYS * 864e5)
      return {ok: false, title: "This link has expired", text: "Please sign up again with the Daily digest button."};
    if (!rec.confirmed && count() >= MAX_SUBSCRIBERS)
      return {ok: false, title: "Pulse Daily is full for now", text: "Please try again in a few weeks."};
    const changed = rec.confirmed;
    rec.streams = rec.pending;
    if (rec.pendingPrefs) rec.prefs = rec.pendingPrefs;
    rec.confirmed = true;
    rec.token = rec.token || Utilities.getUuid();  // the reader's own unsubscribe and "Change my choices" link
    delete rec.pending; delete rec.pendingPrefs; delete rec.ctoken;
    props.deleteProperty("t:" + t);
    props.setProperty("u:" + rec.token, email);
    props.setProperty("s:" + email, JSON.stringify(rec));
    if (!changed)  // new subscribers only: the project inbox isn't told about changed streams or choices
      notify(`Pulse Central: new subscriber (${count()} subscribers)`, `${email} subscribed to: ${names(rec.streams)}.` +
             (hasPrefs(rec.prefs) ? ` Choices: ${summary(rec.prefs)}.` : ""));
    return {ok: true, title: changed ? "Your streams are changed" : "Welcome aboard, you're subscribed!",
            text: (weeklyOnly(rec.prefs) ? `${changed ? "From Sunday" : "Every Sunday"} you'll get the week in AI: ${names(rec.streams)}. `
                   : `${changed ? "From tomorrow" : "Every morning"} you'll get the day before in AI: ${names(rec.streams)}. `) +
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
  notify(`Pulse Central: someone unsubscribed (${count()} subscribers)`,
         "A reader unsubscribed; their address is deleted, so it isn't named here.");
  return {ok: true, title: "You're unsubscribed",
          text: "Your address is deleted from Pulse Daily, and our emails with you are deleted within 30 days. " +
                "You won't hear from us again."};
}

// "Change my choices": the link in every email (SITE#choices=token) opens the form filled in with what the reader
// has; saving changes it at once, as that link is the reader's own.
function choices(t) {
  const email = t && store().getProperty("u:" + t), rec = email && read(email);
  if (!rec || !rec.confirmed) return {ok: false, title: "This link doesn't work any more",
                                      text: "Subscribe again with the Daily digest button."};
  const pr = rec.prefs || {more: [], less: [], words: []};
  return {ok: true, streams: rec.streams, more: pr.more, less: pr.less, words: pr.words, interests: pr.interests || [],
          often: pr.often || "daily"};
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
    rec.prefs = prefsFrom(p, rec.prefs);
    store().setProperty("s:" + email, JSON.stringify(rec));
  } finally {
    lock.releaseLock();
  }
  return {ok: true, title: "Saved", text: `From ${weeklyOnly(rec.prefs) ? "Sunday's" : "tomorrow's"} email: ${names(streams)}` +
          (hasPrefs(rec.prefs) ? `; ${summary(rec.prefs)}.` : ".")};
}

// The site's review form (templates/review.html Q): only these answers are passed on, and at most
// REVIEWS_A_DAY a day, so the emails sign-ups need always have room in the daily quota.
const REVIEW = {
  channels: ["Website", "On my phone", "Daily email", "Sunday email", "Monthly issue", "RSS"],
  uses: ["Keeping up with AI", "My job", "Research or study", "Teaching", "Writing or reporting", "Policy or legal work",
         "Investing or business decisions", "Building with AI"],
  useful: ["1", "2", "3", "4", "5"],
  section: ["Industry", "Releases", "Policy", "Regulation", "Research", "Infra"],
  opens: ["Every day", "Most days", "Now and then", "I don't get it"],
  length: ["Too long", "About right", "Too short"],
  pro: ["Yes", "Not yet", "First I've heard of it"],
  proPick: ["Compass", "Risk Monitor", "Watch", "SmartFeed", "Pulse Store", "None yet"],
  improve: ["Easier to find things", "Clearer charts and numbers", "Shorter emails", "More sources", "Better on phones",
            "Nothing, it's good"],
};
const REVIEW_NAMES = {channels: "Reads Pulse Central via", uses: "Uses it for", useful: "How useful (1-5)", section: "Uses most",
                      opens: "Opens the daily email", length: "Daily email is", pro: "Looked at Pulse Pro Engine",
                      proPick: "Pro product of interest", improve: "Improve first"};
const REVIEWS_A_DAY = 15;
const OTHER_MAX = 1000;  // characters in "Anything else?"

function review(p) {
  if (p.website) return {ok: true};  // the hidden field only bots fill in
  const answers = {};
  for (const k in REVIEW) {
    const picked = [...new Set(String(p[k] || "").split("|").filter(v => REVIEW[k].includes(v)))];
    if (picked.length) answers[k] = k === "channels" || k === "uses" ? picked : picked.slice(0, 1);
  }
  const other = String(p.other || "").replace(/[\u0000-\u0008\u000B-\u001F]/g, "").trim().slice(0, OTHER_MAX);
  if (!Object.keys(answers).length && !other) return {ok: false, error: "empty"};
  const lock = LockService.getScriptLock();
  lock.waitLock(20000);
  try {
    const props = store(), key = "review:" + today(), n = Number(props.getProperty(key) || 0);
    if (n >= REVIEWS_A_DAY || MailApp.getRemainingDailyQuota() < 20) return {ok: false, error: "busy"};
    props.setProperty(key, String(n + 1));
  } finally {
    lock.releaseLock();
  }
  const lines = Object.entries(REVIEW_NAMES).map(([k, name]) => `${name}: ${answers[k] ? answers[k].join(", ") : "-"}`);
  notify(`Pulse Central review: ${answers.useful ? answers.useful[0] + "/5" : "no score"}` +
         (answers.improve ? `, improve first: ${answers.improve[0]}` : ""),
         [...lines, "", "Anything else:", other || "-"].join("\n"));
  return {ok: true};
}

// Pulse Pro Engine's "Start a conversation" form (owner, 12 Nov 2026): one email to the project inbox, Reply-To the sender.
// Capped like the review form so a bot can't use up the day's mail quota.
const CONTACTS_A_DAY = 25;
const CONTACT_TOPICS = ["Pulse Compass", "Pulse Risk Monitor", "Pulse Watch", "Pulse SmartFeed", "Pulse Store",
                        "Prices", "A demo for my team", "Something else"];
const plain = (s, n) => String(s || "").replace(/[\u0000-\u0008\u000B-\u001F]/g, "").trim().slice(0, n);
const oneLine = (s, n) => plain(s, n).replace(/\s+/g, " ");

function contact(p) {
  if (p.website) return {ok: true};  // the hidden field only bots fill in
  const email = oneLine(p.email, 200), name = oneLine(p.name, 120), firm = oneLine(p.firm, 160);
  const topic = CONTACT_TOPICS.includes(p.topic) ? p.topic : "Something else";
  const message = plain(p.message, 3000);
  if (!EMAIL.test(email) || !name || !message) return {ok: false, error: "missing"};
  const lock = LockService.getScriptLock();
  lock.waitLock(20000);
  try {
    const props = store(), key = "contact:" + today(), n = Number(props.getProperty(key) || 0);
    if (n >= CONTACTS_A_DAY || MailApp.getRemainingDailyQuota() < 20) return {ok: false, error: "busy"};
    props.setProperty(key, String(n + 1));
  } finally {
    lock.releaseLock();
  }
  try {
    MailApp.sendEmail({to: SENDER, replyTo: email, name: "Pulse Pro Engine",
                       subject: `Pulse Pro Engine conversation: ${topic}, ${name}` + (firm ? ` (${firm})` : ""),
                       body: [`Name: ${name}`, `Email: ${email}`, `Firm: ${firm || "-"}`, `About: ${topic}`, "", message].join("\n")});
  } catch (e) {
    return {ok: false, error: "busy"};
  }
  return {ok: true};
}

// Blog comments (owner, 18 Nov 2026): readers post a name and a comment under a Pulse Pro Engine blog post. Each lands
// as a row in the "Pulse blog comments" Google Sheet in this account, unticked; only rows the owner ticks in the
// Approved column are shown on the site. The project inbox gets a short note for each new comment.
// Setup, once: run setUpComments from the editor and allow the Sheets permission it asks for, then deploy a new version.
const COMMENTS_A_DAY = 50;
const COMMENT_HEAD = ["Date", "Post", "Name", "Comment", "Approved"];

function commentSheet() {
  const id = store().getProperty("COMMENTS_SHEET");
  if (id) return SpreadsheetApp.openById(id).getSheets()[0];
  const book = SpreadsheetApp.create("Pulse blog comments"), sheet = book.getSheets()[0];
  sheet.appendRow(COMMENT_HEAD);
  sheet.setFrozenRows(1);
  sheet.getRange("E2:E").insertCheckboxes();
  store().setProperty("COMMENTS_SHEET", book.getId());
  return sheet;
}

function setUpComments() {
  Logger.log("Comments Sheet: " + commentSheet().getParent().getUrl());
}

function comment(p) {
  if (p.website) return {ok: true};  // the hidden field only bots fill in
  const post = String(p.post || "").replace(/[^a-z0-9-]/g, "").slice(0, 120);
  const name = oneLine(p.name, 60), text = plain(p.comment, 1500);
  if (!post || !name || !text) return {ok: false, error: "missing"};
  const lock = LockService.getScriptLock();
  lock.waitLock(20000);
  try {
    const props = store(), key = "comment:" + today(), n = Number(props.getProperty(key) || 0);
    if (n >= COMMENTS_A_DAY) return {ok: false, error: "busy"};
    props.setProperty(key, String(n + 1));
    const sheet = commentSheet();
    sheet.appendRow([today(), post, name, text, false]);
    sheet.getRange(sheet.getLastRow(), 5).insertCheckboxes();
  } finally {
    lock.releaseLock();
  }
  if (MailApp.getRemainingDailyQuota() >= 20)
    notify(`New blog comment on ${post}, from ${name}`,
           [text, "", "Tick Approved to show it on the site: " + commentSheet().getParent().getUrl()].join("\n"));
  return {ok: true};
}

// The approved comments on one post, oldest first: name, date and text only.
function comments(p) {
  const post = String(p.post || "").replace(/[^a-z0-9-]/g, "");
  if (!post || !store().getProperty("COMMENTS_SHEET")) return {ok: true, comments: []};
  const rows = commentSheet().getDataRange().getValues().slice(1);
  return {ok: true, comments: rows.filter(r => r[1] === post && r[4] === true)
    .map(r => ({date: r[0] instanceof Date ? r[0].toISOString().slice(0, 10) : String(r[0]), name: String(r[2]), text: String(r[3])}))};
}

// Pulse Watch alerts (owner, 22 Nov 2026): on the Watch page's Any company tab a client names a company or lab and
// the events it wants to hear about; each request is a row in the "Pulse Watch alerts" Sheet in this account. The
// daily alert job (compass aipulse/watch_alerts.py) reads the active rows with LIST_KEY and sends one email a day per
// address; the Stop link in it (SITE planner/vendor-watch/#stop=token) turns that address's rows off.
// Setup, once: run setUpWatchAlerts from the editor and allow the Sheets permission it asks for, then deploy.
const WATCH_A_DAY = 60, WATCH_PER_EMAIL = 20;
const WATCH_EVENTS = ["model", "shutdown", "ipo", "money", "court", "government", "pages"];
const WATCH_HEAD = ["Date", "Email", "Company", "Events", "Token", "Active"];

function watchSheet() {
  const id = store().getProperty("WATCH_SHEET");
  if (id) return SpreadsheetApp.openById(id).getSheets()[0];
  const book = SpreadsheetApp.create("Pulse Watch alerts"), sheet = book.getSheets()[0];
  sheet.appendRow(WATCH_HEAD);
  sheet.setFrozenRows(1);
  store().setProperty("WATCH_SHEET", book.getId());
  return sheet;
}

function setUpWatchAlerts() {
  Logger.log("Watch alerts Sheet: " + watchSheet().getParent().getUrl());
}

function watchAlert(p) {
  if (p.website) return {ok: true};  // the hidden field only bots fill in
  const email = oneLine(p.email, 200).toLowerCase(), company = oneLine(p.company, 80);
  const events = String(p.events || "").split(",").filter(e => WATCH_EVENTS.includes(e));
  if (!EMAIL.test(email) || !company || !events.length) return {ok: false, error: "missing"};
  const lock = LockService.getScriptLock();
  lock.waitLock(20000);
  try {
    const props = store(), key = "watch:" + today(), n = Number(props.getProperty(key) || 0);
    if (n >= WATCH_A_DAY) return {ok: false, error: "busy"};
    const sheet = watchSheet(), rows = sheet.getDataRange().getValues().slice(1);
    const mine = rows.filter(r => r[1] === email && r[5] === true);
    if (mine.length >= WATCH_PER_EMAIL) return {ok: false, error: "busy"};
    // one token per address, so the Stop link in its email stops all of its requests
    const token = (mine[0] && mine[0][4]) || Utilities.getUuid().replace(/-/g, "");
    const same = rows.findIndex(r => r[1] === email && String(r[2]).toLowerCase() === company.toLowerCase() && r[5] === true);
    if (same >= 0) sheet.getRange(same + 2, 4).setValue(events.join(","));  // the same company again: new picks
    else sheet.appendRow([today(), email, company, events.join(","), token, true]);
    props.setProperty(key, String(n + 1));
  } finally {
    lock.releaseLock();
  }
  return {ok: true};
}

function watchAlerts(key) {
  const secret = store().getProperty("LIST_KEY");
  if (!secret || secret.length < 24 || key !== secret) return {ok: false};
  for (const k of Object.keys(store().getProperties()))
    if (k.startsWith("watch:") && k < "watch:" + today()) store().deleteProperty(k);
  if (!store().getProperty("WATCH_SHEET")) return {ok: true, requests: []};
  const rows = watchSheet().getDataRange().getValues().slice(1).filter(r => r[5] === true);
  return {ok: true, requests: rows.map(r => ({email: String(r[1]), company: String(r[2]),
                                               events: String(r[3]).split(","), token: String(r[4])}))};
}

function watchStop(t) {
  t = String(t || "").replace(/[^A-Za-z0-9]/g, "");
  if (!t || !store().getProperty("WATCH_SHEET")) return {ok: false};
  const sheet = watchSheet(), rows = sheet.getDataRange().getValues();
  let n = 0;
  rows.forEach((r, i) => { if (i && r[4] === t && r[5] === true) { sheet.getRange(i + 1, 6).setValue(false); n++; } });
  return {ok: n > 0};
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
  notify("Pulse Central: the daily email could not be started",
         (token ? `GitHub answered ${code}: ${answer.getContentText().slice(0, 300)}` : "No GITHUB_TOKEN script property.") +
         "\nThe token may have expired or lost its Actions permission: make a new one and save it as GITHUB_TOKEN." +
         " The workflow's own schedule may still send it; to send by hand: GitHub > Actions > Daily digest > Run workflow, dry run unticked.");
}

// ------------------------------------------------------------------ Pulse Pro Engine's login (fixed 21 Nov 2026)
// Users are kept as "pro:u:<name>" = {salt, hash, added}; hash = HMAC-SHA256 of salt, name and password with
// PRO_PEPPER, a secret made here on first use that never leaves this account. Page keys: "pro:keys" =
// [{kid, key}] newest first. Wrong tries are counted in the script cache, per username.
const PRO_TRIES = 5, PRO_LOCK_SECONDS = 15 * 60, PRO_MIN_PASSWORD = 12, PRO_KEYS_KEPT = 2;
const b64 = bytes => Utilities.base64Encode(bytes);
const proName = n => String(n || "").trim().toLowerCase();
const proOwner = key => { const s = store().getProperty("PRO_KEY"); return !!(s && s.length >= 24 && key === s); };
const proKeys = () => JSON.parse(store().getProperty("pro:keys") || "[]");
const random = n => { let s = ""; while (s.length < n) s += Utilities.getUuid().replace(/-/g, ""); return s.slice(0, n); };

function proHash(salt, name, password) {
  let pepper = store().getProperty("PRO_PEPPER");
  if (!pepper) { pepper = random(64); store().setProperty("PRO_PEPPER", pepper); }
  return b64(Utilities.computeHmacSha256Signature(`${salt}\n${name}\n${password}`, pepper));
}

function same(a, b) {  // the same time for any mismatch, so the answer's speed says nothing
  let d = a.length ^ b.length;
  for (let i = 0; i < Math.max(a.length, b.length); i++) d |= (a.charCodeAt(i) || 0) ^ (b.charCodeAt(i) || 0);
  return d === 0;
}

function proLogin(p) {
  const name = proName(p.name), cache = CacheService.getScriptCache(), tries = "pro:f:" + name;
  const failed = Number(cache.get(tries) || 0);
  if (!name || failed >= PRO_TRIES) return {ok: false, locked: failed >= PRO_TRIES};
  const rec = JSON.parse(store().getProperty("pro:u:" + name) || "null");
  const right = rec ? same(proHash(rec.salt, name, String(p.password || "")), rec.hash) : (proHash("-", name, "-"), false);
  if (!right) {  // an unknown name counts too, so trying names tells nothing
    cache.put(tries, String(failed + 1), PRO_LOCK_SECONDS);
    return {ok: false, locked: failed + 1 >= PRO_TRIES};
  }
  cache.remove(tries);
  const keys = proKeys();
  if (p.kid && !keys.some(k => k.kid === p.kid)) return {ok: false, stale: true};  // a page from before a reset
  return {ok: true, keys: Object.fromEntries(keys.map(k => [k.kid, k.key]))};
}

function proKey(key) {
  if (!proOwner(key)) return {ok: false};
  const lock = LockService.getScriptLock();
  lock.waitLock(20000);
  try {
    let keys = proKeys();
    if (!keys.length || keys[0].kid.slice(0, 10) !== today()) {  // the first build of the day makes the day's key
      const raw = Utilities.computeDigest(Utilities.DigestAlgorithm.SHA_256, random(64) + Date.now());
      keys = [{kid: `${today()}-${random(8)}`, key: b64(raw)}, ...keys].slice(0, PRO_KEYS_KEPT);
      store().setProperty("pro:keys", JSON.stringify(keys));
    }
    return {ok: true, kid: keys[0].kid, key: keys[0].key};
  } finally {
    lock.releaseLock();
  }
}

function proUser(p) {
  if (!proOwner(p.key)) return {ok: false, text: "PRO_KEY doesn't match."};
  const name = proName(p.name), props = store();
  if (p.op === "list")
    return {ok: true, names: Object.keys(props.getProperties()).filter(k => k.startsWith("pro:u:")).map(k => k.slice(6)).sort()};
  if (!name || name.length > 80) return {ok: false, text: "Say which user."};
  if (p.op === "remove") {
    if (!props.getProperty("pro:u:" + name)) return {ok: false, text: `No user called ${name}.`};
    props.deleteProperty("pro:u:" + name);
    props.deleteProperty("pro:keys");  // the next build makes a new key, which this user never gets
    return {ok: true};
  }
  if (p.op === "add") {
    const password = String(p.password || "");
    if (password.length < PRO_MIN_PASSWORD) return {ok: false, text: `At least ${PRO_MIN_PASSWORD} characters.`};
    const salt = random(32);
    props.setProperty("pro:u:" + name, JSON.stringify({salt, hash: proHash(salt, name, password), added: today()}));
    CacheService.getScriptCache().remove("pro:f:" + name);
    return {ok: true};
  }
  return {ok: false, text: "op is add, remove or list."};
}

// A note to the project inbox when someone subscribes, changes streams or unsubscribes. It never stops the
// reader's own step if it fails.
function notify(subject, text) {
  try {
    MailApp.sendEmail({to: SENDER, name: "Pulse Central", subject, body: text});
  } catch (e) {
    console.log("notice not sent: " + e);
  }
}

function count() {
  return Object.entries(store().getProperties())
    .filter(([k, v]) => k.startsWith("s:") && JSON.parse(v).confirmed).length;
}

// Every interest the confirmed readers follow, once each (however capitalised), with nothing about who follows it.
function interests(key) {
  const secret = store().getProperty("LIST_KEY");
  if (!secret || secret.length < 24 || key !== secret) return {ok: false};
  const seen = new Map();
  for (const [k, v] of Object.entries(store().getProperties())) {
    if (!k.startsWith("s:")) continue;
    const rec = JSON.parse(v);
    if (rec.confirmed) ((rec.prefs && rec.prefs.interests) || []).forEach(t => seen.set(t.toLowerCase(), t));
  }
  return {ok: true, interests: [...seen.values()]};
}

function list(key) {
  const secret = store().getProperty("LIST_KEY");
  if (!secret || secret.length < 24 || key !== secret) return {ok: false};
  const props = store(), out = [], cutoff = Date.now() - PENDING_DAYS * 864e5;
  for (const [k, v] of Object.entries(props.getProperties())) {
    if ((k.startsWith("sent:") && k < "sent:" + today()) || (k.startsWith("review:") && k < "review:" + today()))
      props.deleteProperty(k);
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
  return page({title: action === "confirm" ? "One more click" : "Unsubscribe from Pulse Daily", text: ""},
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
    `<p><a href="${SITE}" target="_top">Pulse Central</a></p></div>`)
    .setTitle("Pulse Daily");
}
