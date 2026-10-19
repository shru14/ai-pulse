// The query page (api/v1/): the same filter as api.py's query(), run in the reader's browser on a published file.
(() => {
  const $ = id => document.getElementById(id), form = $("aq"), out = $("aq-out"), meta = $("aq-meta");
  const text = v => typeof v === "boolean" ? String(v) : v == null ? "" : typeof v === "object" ? JSON.stringify(v) : String(v);
  const matches = (v, wanted) => {  // as _matches
    const opts = wanted.split("|").map(w => w.trim().toLowerCase()).filter(Boolean);
    return (Array.isArray(v) ? v : [v]).some(i => opts.some(o =>
      typeof i === "string" || (i && typeof i === "object") ? text(i).toLowerCase().includes(o) : text(i).toLowerCase() === o));
  };
  const within = (d, s, e) => !!d && (!s || d >= s.slice(0, d.length)) && (!e || d <= e.slice(0, d.length));
  const query = (doc, a) => {  // as query
    let rows = doc.rows;
    const f = doc.date_field;
    if ((a.from || a.to) && f) rows = rows.filter(r => within(String(r[f] || "").slice(0, 10), a.from, a.to));
    for (const [k, v] of Object.entries(a.where)) rows = rows.filter(r => matches(r[k], v));
    if (a.q) rows = rows.filter(r => JSON.stringify(r).toLowerCase().includes(a.q.toLowerCase()));
    const shown = a.limit ? rows.slice(0, a.limit) : rows, head = {};
    for (const k of ["name", "title", "page", "row", "updated", "date_field"]) if (k in doc) head[k] = doc[k];
    return {...head, asked: {from: a.from, to: a.to, where: a.where, q: a.q, limit: a.limit}, matched: rows.length,
            count: shown.length, rows: shown};
  };
  const asked = () => {
    const p = new URLSearchParams(location.search), where = {};
    for (const w of p.getAll("where")) {
      const i = w.indexOf(":");
      if (i > 0) where[w.slice(0, i).trim()] = w.slice(i + 1);
    }
    return {name: p.get("name") || "", from: p.get("from") || "", to: p.get("to") || "", where, q: p.get("q") || "",
            limit: parseInt(p.get("limit") || "0", 10) || 0};
  };
  let result = null;
  const run = async () => {
    const a = asked();
    form.name.value = a.name; form.from.value = a.from; form.to.value = a.to; form.q.value = a.q;
    form.limit.value = a.limit || "";
    form.where.value = Object.entries(a.where).map(([k, v]) => `${k}:${v}`).join("\n");
    out.textContent = ""; $("aq-dl").hidden = true; $("aq-fields").textContent = "";
    if (!a.name) { meta.textContent = ""; return; }
    meta.textContent = "Loading…";
    let doc;
    try {
      doc = await (await fetch(`api/v1/${encodeURIComponent(a.name)}.json`)).json();
    } catch (e) {
      meta.textContent = `No data called "${a.name}".`;
      return;
    }
    $("aq-fields").textContent = doc.rows.length ? "Fields: " + Object.keys(doc.rows[0]).join(", ") : "";
    result = query(doc, a);
    meta.textContent = `${result.matched} of ${doc.count} rows match` +
      (result.count < result.matched ? `, showing the first ${result.count}` : "") +
      (doc.date_field ? `. Dates are read from "${doc.date_field}".` : ". These rows have no date of their own.");
    out.textContent = JSON.stringify(result, null, 2);
    $("aq-dl").hidden = false;
  };
  form.addEventListener("submit", e => {
    e.preventDefault();
    const p = new URLSearchParams();
    for (const k of ["name", "from", "to", "q", "limit"]) if (form[k].value.trim()) p.set(k, form[k].value.trim());
    for (const w of form.where.value.split("\n").map(x => x.trim()).filter(Boolean)) p.append("where", w);
    history.pushState(null, "", location.pathname + "?" + p.toString());  // the page's <base> is the site's root
    run();
  });
  $("aq-dl").addEventListener("click", () => {
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([JSON.stringify(result, null, 2)], {type: "application/json"}));
    a.download = `${result.name}.json`;
    a.click();
  });
  addEventListener("popstate", run);
  run();
})();
