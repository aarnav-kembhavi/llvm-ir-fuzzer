/* ============================================================
   LLVM IR Differential Testing — dashboard app (vanilla JS)
   ============================================================ */
"use strict";

const $ = (sel, el = document) => el.querySelector(sel);
const view = $("#view");
const tooltip = $("#tooltip");

/* ---------------- verdict metadata (color = state, always with a text label) */
const VERDICTS = {
  CRASH:        { color: "var(--s-critical)", desc: "opt crashed or returned a fatal error — bug candidate" },
  INVALID:      { color: "var(--s-serious)",  desc: "-O3 output failed re-validation — bug candidate" },
  SEMANTIC_BUG: { color: "var(--s-critical)", desc: "compiled binaries behave differently — critical bug candidate" },
  DIVERGENT:    { color: "var(--c-blue)",     desc: "-O0 and -O3 IR differ textually (expected for optimizers)" },
  EXEC_MATCH:   { color: "var(--s-good)",     desc: "binaries executed with identical stdout + exit code" },
  IDENTICAL:    { color: "var(--baseline)",   desc: "-O0 and -O3 outputs are byte-identical" },
  SKIPPED:      { color: "var(--ink-muted)",  desc: "mutant failed validation and was discarded" },
};
const VERDICT_ORDER = ["CRASH", "INVALID", "SEMANTIC_BUG", "DIVERGENT", "EXEC_MATCH", "IDENTICAL", "SKIPPED"];

/* ---------------- tiny helpers */
const esc = s => String(s ?? "").replace(/[&<>"']/g,
  c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const pct = x => (x == null ? "—" : (x * 100).toFixed(1) + "%");
const fmtRunTime = id => {
  const m = id.match(/(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})(\d{2})/);
  if (!m) return id;
  const d = new Date(+m[1], +m[2] - 1, +m[3], +m[4], +m[5], +m[6]);
  return d.toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
};
async function api(path) {
  const r = await fetch(path);
  if (!r.ok) throw new Error((await r.json().catch(() => ({}))).error || r.statusText);
  return r.json();
}
function badge(v) { return `<span class="badge ${esc(v)}">${esc(v)}</span>`; }

/* ---------------- tooltip */
function bindTooltips(root) {
  root.querySelectorAll("[data-tip]").forEach(el => {
    el.addEventListener("mousemove", e => {
      tooltip.innerHTML = el.dataset.tip;
      tooltip.hidden = false;
      const pad = 14;
      let x = e.clientX + pad, y = e.clientY + pad;
      const r = tooltip.getBoundingClientRect();
      if (x + r.width > innerWidth - 8) x = e.clientX - r.width - pad;
      if (y + r.height > innerHeight - 8) y = e.clientY - r.height - pad;
      tooltip.style.left = x + "px"; tooltip.style.top = y + "px";
    });
    el.addEventListener("mouseleave", () => { tooltip.hidden = true; });
  });
}

/* ---------------- LLVM IR syntax highlighting */
const IR_TOKEN = new RegExp([
  /;[^\n]*/.source,                                   // comment
  /"(?:[^"\\]|\\.)*"/.source,                          // string
  /[%@][-\w.$]+/.source,                               // local / global
  /\b-?\d+\.?\d*(?:e[+-]?\d+)?\b/.source,              // number
  /\b(?:define|declare|ret|br|switch|call|tail|musttail|to|add|sub|mul|sdiv|udiv|srem|urem|fadd|fsub|fmul|fdiv|frem|shl|lshr|ashr|and|or|xor|icmp|fcmp|phi|select|load|store|alloca|getelementptr|inbounds|nsw|nuw|align|label|eq|ne|sgt|sge|slt|sle|ugt|uge|ult|ule|zext|sext|trunc|bitcast|inttoptr|ptrtoint|fptosi|sitofp|unreachable|atomicrmw|cmpxchg|fence|seq_cst|acquire|release|monotonic|extractelement|insertelement|shufflevector|extractvalue|insertvalue|invoke|landingpad|resume|catch|cleanup|personality|unwind|noundef|nonnull|readonly|writeonly|nocapture|internal|external|private|constant|global|volatile|target|datalayout|triple|source_filename|attributes|local_unnamed_addr|unnamed_addr|dso_local)\b/.source,
  /\b(?:i1|i8|i16|i32|i64|i128|half|float|double|fp128|ptr|void|x86_mmx|opaque|type)\b/.source,
].join("|"), "g");

function highlightIR(line) {
  let out = "", last = 0;
  for (const m of line.matchAll(IR_TOKEN)) {
    out += esc(line.slice(last, m.index));
    const t = m[0];
    let cls = "tok-kw";
    if (t[0] === ";") cls = "tok-com";
    else if (t[0] === '"') cls = "tok-str";
    else if (t[0] === "%") cls = "tok-var";
    else if (t[0] === "@") cls = "tok-glob";
    else if (/^-?\d/.test(t)) cls = "tok-num";
    else if (/^(?:i\d+|half|float|double|fp128|ptr|void|x86_mmx|opaque|type)$/.test(t)) cls = "tok-ty";
    out += `<span class="${cls}">${esc(t)}</span>`;
    last = m.index + t.length;
  }
  return out + esc(line.slice(last));
}

function codePane(source, { highlightLine = null, mode = null } = {}) {
  if (!source) return `<div class="empty small">not available</div>`;
  const lines = source.replace(/\n$/, "").split("\n");
  const rows = lines.map((ln, i) => {
    const n = i + 1;
    const cls = n === highlightLine ? (mode === "add" ? " hl-add" : " hl-del") : "";
    return `<div class="ln${cls}"><span class="n">${n}</span><span>${highlightIR(ln) || " "}</span></div>`;
  }).join("");
  return `<div class="code-pane">${rows}</div>`;
}

/* ============================================================
   Charts (hand-rolled SVG, dataviz mark specs)
   ============================================================ */

/* stacked horizontal verdict bar — part-to-whole, 2px surface gaps */
function verdictStackBar(counts, total) {
  if (!total) return `<div class="empty small">no iterations</div>`;
  const segs = VERDICT_ORDER.filter(v => counts[v]).map(v => {
    const n = counts[v];
    const meta = VERDICTS[v] || { color: "var(--ink-muted)", desc: "" };
    return `<div class="seg" style="flex:${n};background:${meta.color}"
      data-tip="<b>${esc(v)}</b> — ${n} of ${total} (${(n / total * 100).toFixed(1)}%)<br>${esc(meta.desc)}"></div>`;
  }).join("");
  const legend = VERDICT_ORDER.filter(v => counts[v]).map(v =>
    `<span class="key"><span class="swatch" style="background:${VERDICTS[v].color}"></span>${esc(v)} · ${counts[v]}</span>`
  ).join("");
  return `<div class="stackbar" style="background:transparent">${segs}</div><div class="legend">${legend}</div>`;
}

/* column chart: per-iteration time, colored by verdict (identity), ≤24px columns,
   4px rounded top / square baseline, hairline gridlines, hover tooltips */
function iterationColumns(iters) {
  if (!iters.length) return "";
  const W = Math.min(1120, Math.max(360, iters.length * 26 + 70));
  const H = 190, padL = 46, padR = 10, padT = 12, padB = 26;
  const plotW = W - padL - padR, plotH = H - padT - padB;
  const maxT = Math.max(...iters.map(i => i.iteration_time_seconds || 0), 0.1);
  const step = niceStep(maxT);
  const top = Math.ceil(maxT / step) * step;
  const slot = plotW / iters.length;
  const bw = Math.min(24, Math.max(6, slot * 0.62));

  let grid = "";
  for (let v = 0; v <= top + 1e-9; v += step) {
    const y = padT + plotH - (v / top) * plotH;
    grid += `<line class="gridline" x1="${padL}" y1="${y}" x2="${W - padR}" y2="${y}"/>` +
            `<text x="${padL - 8}" y="${y + 3}" text-anchor="end">${trimNum(v)}s</text>`;
  }
  const bars = iters.map((it, i) => {
    const t = it.iteration_time_seconds || 0;
    const h = Math.max(2, (t / top) * plotH);
    const x = padL + i * slot + (slot - bw) / 2;
    const y = padT + plotH - h;
    const v = it.verdict || "SKIPPED";
    const color = (VERDICTS[v] || VERDICTS.SKIPPED).color;
    const r = Math.min(4, h / 2, bw / 2);
    const d = `M${x},${y + h} V${y + r} Q${x},${y} ${x + r},${y} H${x + bw - r} Q${x + bw},${y} ${x + bw},${y + r} V${y + h} Z`;
    const seed = (it.seed_path || "").split("/").pop();
    return `<path class="mark" d="${d}" fill="${color}"
      data-tip="<b>Iteration ${it.iteration}</b> — ${esc(v)}<br>${esc(seed)}<br>${t.toFixed(3)}s"/>`;
  }).join("");
  const xlabels = iters.map((it, i) => {
    if (iters.length > 30 && it.iteration % 5 !== 0 && it.iteration !== 1) return "";
    const x = padL + i * slot + slot / 2;
    return `<text x="${x}" y="${H - 8}" text-anchor="middle">${it.iteration}</text>`;
  }).join("");
  const used = [...new Set(iters.map(i => i.verdict || "SKIPPED"))];
  const legend = used.length < 2 ? "" : `<div class="legend">` +
    VERDICT_ORDER.filter(v => used.includes(v)).map(v =>
      `<span class="key"><span class="swatch" style="background:${VERDICTS[v].color}"></span>${esc(v)}</span>`).join("") +
    `</div>`;
  return `<div class="chart-wrap"><svg class="chart" width="${W}" height="${H}" role="img" aria-label="Time per iteration, colored by verdict">
    ${grid}
    <line class="axis-line" x1="${padL}" y1="${padT + plotH}" x2="${W - padR}" y2="${padT + plotH}"/>
    ${bars}${xlabels}
  </svg></div>${legend}`;
}

function niceStep(max) {
  const raw = max / 4;
  const mag = Math.pow(10, Math.floor(Math.log10(raw)));
  for (const m of [1, 2, 2.5, 5, 10]) if (raw <= m * mag) return m * mag;
  return 10 * mag;
}
const trimNum = v => (Math.round(v * 100) / 100).toString();

/* LLM vs baseline — emphasis form: subject in blue, control in gray */
function baselineCompare(llm, base) {
  const rows = [
    ["Valid mutant rate", "valid_mutant_rate"],
    ["Divergence rate", "divergence_rate"],
    ["Bug candidate rate", "bug_candidate_rate"],
    ["Discard rate", "discard_rate"],
  ];
  const W = 520, barH = 12, group = 46, padL = 130, padR = 60, padT = 8;
  const H = padT + rows.length * group + 4;
  const plotW = W - padL - padR;
  let svg = "";
  rows.forEach(([label, key], i) => {
    const y0 = padT + i * group;
    const vL = llm[key] ?? 0, vB = base[key] ?? 0;
    svg += `<text x="${padL - 10}" y="${y0 + barH + 4}" text-anchor="end" style="fill:var(--ink-2)">${esc(label)}</text>`;
    [[vL, "var(--c-blue)", "LLM-guided"], [vB, "var(--ink-muted)", "Random baseline"]].forEach(([v, color, name], j) => {
      const y = y0 + j * (barH + 3);
      const w = Math.max(2, v * plotW);
      const r = Math.min(4, barH / 2, w);
      const d = `M${padL},${y} H${padL + w - r} Q${padL + w},${y} ${padL + w},${y + r} V${y + barH - r} Q${padL + w},${y + barH} ${padL + w - r},${y + barH} H${padL} Z`;
      svg += `<path class="mark" d="${d}" fill="${color}" data-tip="<b>${name}</b><br>${esc(label)}: ${(v * 100).toFixed(1)}%"/>`;
      svg += `<text x="${padL + w + 6}" y="${y + barH - 2}">${(v * 100).toFixed(1)}%</text>`;
    });
  });
  return `<div class="chart-wrap"><svg class="chart" width="${W}" height="${H}" role="img" aria-label="LLM vs random baseline">${svg}</svg></div>
    <div class="legend">
      <span class="key"><span class="swatch" style="background:var(--c-blue)"></span>LLM-guided</span>
      <span class="key"><span class="swatch" style="background:var(--ink-muted)"></span>Random baseline</span>
    </div>`;
}

/* ============================================================
   Views
   ============================================================ */

async function viewRuns() {
  const runs = await api("/api/runs");
  if (!runs.length) {
    view.innerHTML = `<div class="empty"><span class="big">🧪</span>No runs yet — start one from the <a href="#/new">New Run</a> tab.</div>`;
    return;
  }
  const totalIters = runs.reduce((s, r) => s + r.iterations, 0);
  const totalBugs = runs.reduce((s, r) => s + r.bug_candidates, 0);
  const rows = runs.map(r => {
    const counts = r.verdicts || {};
    const total = r.iterations || 1;
    const mini = VERDICT_ORDER.filter(v => counts[v]).map(v =>
      `<div class="seg" style="flex:${counts[v]};background:${VERDICTS[v].color}"
        data-tip="<b>${v}</b> — ${counts[v]}/${r.iterations}"></div>`).join("");
    return `<tr data-run="${esc(r.id)}">
      <td style="font-family:var(--mono);font-size:12px">${esc(r.id)}</td>
      <td>${fmtRunTime(r.id)}</td>
      <td class="num">${r.iterations}</td>
      <td style="min-width:160px"><div class="stackbar" style="height:12px;background:transparent">${mini || ""}</div></td>
      <td class="num">${r.bug_candidates ? `<span style="color:var(--s-critical);font-weight:650">${r.bug_candidates}</span>` : "0"}</td>
      <td>${r.has_baseline ? '<span class="chip">baseline</span>' : ""} ${r.has_report ? '<span class="chip">report</span>' : ""}</td>
    </tr>`;
  }).join("");

  view.innerHTML = `
    <div class="page-head"><h1>Runs</h1><span class="crumb">${runs.length} runs · artifacts/</span></div>
    <div class="kpi-row">
      <div class="tile"><div class="label">Total runs</div><div class="value">${runs.length}</div></div>
      <div class="tile"><div class="label">Total iterations</div><div class="value">${totalIters}</div></div>
      <div class="tile"><div class="label">Bug candidates found</div>
        <div class="value ${totalBugs ? "bad" : "good"}">${totalBugs}</div>
        <div class="sub">${totalBugs ? "inspect flagged runs" : "expected for small runs on a mature compiler"}</div></div>
    </div>
    <div class="card">
      <table class="data">
        <thead><tr><th>Run</th><th>Started</th><th class="num">Iters</th><th>Verdicts</th><th class="num">Bug candidates</th><th></th></tr></thead>
        <tbody>${rows}</tbody>
      </table>
    </div>`;
  view.querySelectorAll("tr[data-run]").forEach(tr =>
    tr.addEventListener("click", () => location.hash = `#/run/${tr.dataset.run}`));
  bindTooltips(view);
}

async function viewRunDetail(runId) {
  const data = await api(`/api/runs/${runId}`);
  const iters = data.iterations || [];
  const m = data.report?.llm_metrics;
  const counts = {};
  iters.forEach(it => { const v = it.verdict || "SKIPPED"; counts[v] = (counts[v] || 0) + 1; });
  const bugs = iters.filter(i => i.is_bug_candidate).length;

  const tiles = m ? `
    <div class="kpi-row">
      <div class="tile"><div class="label">Valid mutant rate</div><div class="value">${pct(m.valid_mutant_rate)}</div>
        <div class="sub">${m.valid_mutants}/${m.total} passed llvm-as</div></div>
      <div class="tile"><div class="label">Unique mutants</div><div class="value">${m.unique_mutants}</div>
        <div class="sub">SHA-256 deduplicated</div></div>
      <div class="tile"><div class="label">Bug candidates</div>
        <div class="value ${bugs ? "bad" : "good"}">${bugs}</div>
        <div class="sub">crash / invalid / semantic</div></div>
      <div class="tile"><div class="label">Divergence rate</div><div class="value">${pct(m.divergence_rate)}</div>
        <div class="sub">of valid mutants</div></div>
      <div class="tile"><div class="label">Avg time / iter</div><div class="value">${m.avg_time_per_iteration?.toFixed(2)}s</div>
        <div class="sub">total ${m.total_time_seconds?.toFixed(1)}s</div></div>
    </div>` : `
    <div class="kpi-row">
      <div class="tile"><div class="label">Iterations</div><div class="value">${iters.length}</div></div>
      <div class="tile"><div class="label">Bug candidates</div><div class="value ${bugs ? "bad" : "good"}">${bugs}</div></div>
      <div class="tile"><div class="label">Report</div><div class="value">—</div><div class="sub">run used no --report flag</div></div>
    </div>`;

  const iterRows = iters.map(it => `
    <tr data-iter="${it.iteration}">
      <td class="num">${it.iteration}</td>
      <td style="font-family:var(--mono);font-size:12px">${esc((it.seed_path || "").split("/").pop())}</td>
      <td>${badge(it.verdict || "SKIPPED")}</td>
      <td>${it.valid_mutant ? "✓" : "✗"}</td>
      <td class="num">${it.iteration_time_seconds != null ? it.iteration_time_seconds.toFixed(2) + "s" : "—"}</td>
      <td style="font-family:var(--mono);font-size:11px" class="muted">${esc((it.mutant_hash || "").slice(0, 12) || "—")}</td>
    </tr>`).join("");

  const baseCard = data.report?.baseline_metrics ? `
    <div class="card"><h2>LLM-guided vs random baseline</h2>
      ${baselineCompare(data.report.llm_metrics, data.report.baseline_metrics)}
    </div>` : "";

  view.innerHTML = `
    <div class="page-head">
      <h1>${esc(runId)}</h1>
      <span class="crumb"><a href="#/runs">runs</a> / ${fmtRunTime(runId)}</span>
    </div>
    ${tiles}
    <div class="grid-2">
      <div class="card"><h2>Verdict distribution</h2>${verdictStackBar(counts, iters.length)}</div>
      <div class="card"><h2>Time per iteration</h2>${iterationColumns(iters)}</div>
    </div>
    ${baseCard}
    <div class="card"><h2>Iterations — click a row to inspect the mutation</h2>
      <table class="data">
        <thead><tr><th class="num">#</th><th>Seed</th><th>Verdict</th><th>Valid</th><th class="num">Time</th><th>Hash</th></tr></thead>
        <tbody>${iterRows}</tbody>
      </table>
    </div>`;
  view.querySelectorAll("tr[data-iter]").forEach(tr =>
    tr.addEventListener("click", () => location.hash = `#/run/${runId}/iter/${tr.dataset.iter}`));
  bindTooltips(view);
}

async function viewIteration(runId, n) {
  const it = await api(`/api/runs/${runId}/iterations/${n}`);
  const plan = it.plan;
  const validText = it.validation || "";
  const isValid = /Valid:\s*True/i.test(validText);

  view.innerHTML = `
    <div class="page-head">
      <h1>Iteration ${n}</h1>
      <span class="crumb"><a href="#/runs">runs</a> / <a href="#/run/${esc(runId)}">${esc(runId)}</a> / iter_${String(n).padStart(3, "0")}</span>
      ${it.oracle ? badge(it.oracle.verdict) : badge(isValid ? "IDENTICAL" : "SKIPPED")}
    </div>
    ${plan ? `<div class="mutation-desc">
        <b>LLM mutation plan</b> — line ${plan.line_number}<br>${esc(plan.description || "")}
      </div>` : ""}
    <div class="grid-2">
      <div class="card">
        <div class="pane-head"><span>seed.ll — original</span><span class="chip">input</span></div>
        ${codePane(it.seed, { highlightLine: plan?.line_number, mode: "del" })}
      </div>
      <div class="card">
        <div class="pane-head"><span>mutant.ll — after mutation</span>
          <span class="chip" style="${isValid ? "color:var(--good-text)" : "color:var(--s-critical)"}">${isValid ? "valid IR" : "invalid IR"}</span></div>
        ${codePane(it.mutant, { highlightLine: plan?.line_number, mode: "add" })}
      </div>
    </div>
    ${it.oracle ? `<div class="card"><h2>Oracle result</h2>
      <table class="data"><tbody>
        <tr class="static"><td class="muted" style="width:180px">Verdict</td><td>${badge(it.oracle.verdict)} <span class="muted small">${esc((VERDICTS[it.oracle.verdict] || {}).desc || "")}</span></td></tr>
        <tr class="static"><td class="muted">Bug candidate</td><td>${it.oracle.is_bug_candidate ? '<b style="color:var(--s-critical)">YES</b>' : "no"}</td></tr>
        <tr class="static"><td class="muted">Diff summary</td><td>${esc(it.oracle.diff_summary || "—")}</td></tr>
        ${Object.entries(it.oracle).filter(([k]) => !["verdict", "is_bug_candidate", "diff_summary"].includes(k))
          .map(([k, v]) => `<tr class="static"><td class="muted">${esc(k)}</td><td style="font-family:var(--mono);font-size:12px">${esc(typeof v === "object" ? JSON.stringify(v) : v)}</td></tr>`).join("")}
      </tbody></table></div>` : ""}
    ${validText && !isValid ? `<div class="card"><h2>Validation log (llvm-as)</h2>
      <div class="code-pane" style="padding:10px 14px;white-space:pre-wrap">${esc(validText)}</div></div>` : ""}
    ${it.prompt ? `<div class="card"><h2>LLM prompt <button class="btn secondary small" id="toggle-prompt" style="padding:3px 10px;margin-left:8px">show</button></h2>
      <div class="code-pane" id="prompt-body" style="padding:10px 14px;white-space:pre-wrap;display:none">${esc(it.prompt)}</div></div>` : ""}`;
  const tp = $("#toggle-prompt");
  if (tp) tp.addEventListener("click", () => {
    const b = $("#prompt-body");
    const open = b.style.display !== "none";
    b.style.display = open ? "none" : "block";
    tp.textContent = open ? "show" : "hide";
  });
  bindTooltips(view);
}

const EXAMPLE_SEED = `define i32 @my_function(i32 %a, i32 %b) {
entry:
  %sum = add i32 %a, %b
  ret i32 %sum
}`;

async function viewSeeds() {
  const seeds = await api("/api/seeds");
  const items = seeds.map((s, i) => `
    <div class="seed-item ${i === 0 ? "active" : ""}" data-i="${i}">
      <div><div>${esc(s.name)}</div><div class="pattern">${esc(s.pattern)}</div></div>
      <div style="display:flex;align-items:center;gap:6px">
        ${s.has_main ? '<span class="chip main" title="executable — usable by the execution oracle">main()</span>' : ""}
        ${s.custom ? '<span class="chip">custom</span>' : ""}
      </div>
    </div>`).join("");
  view.innerHTML = `
    <div class="page-head"><h1>Seed Corpus</h1>
      <span class="crumb">${seeds.length} LLVM IR patterns · seeds/ · every seed here is used by future runs</span>
      <button class="btn secondary" id="add-seed-btn" style="margin-left:auto;padding:6px 14px">＋ Add custom seed</button>
    </div>
    <div class="card seed-editor" id="seed-editor" ${new URLSearchParams(location.search).has("editor") ? "" : "hidden"}>
      <h2>Add your own LLVM IR seed</h2>
      <div class="editor-grid">
        <div class="form-row" style="margin-bottom:10px"><label for="cs-name">Name</label>
          <input id="cs-name" type="text" placeholder="my_custom_seed" spellcheck="false"></div>
        <div class="form-row" style="margin-bottom:10px"><label for="cs-pattern">Pattern label</label>
          <input id="cs-pattern" type="text" placeholder="custom" spellcheck="false"></div>
      </div>
      <div class="form-row" style="max-width:none">
        <label for="cs-code">LLVM IR code <span class="muted" style="font-weight:400">— must parse with llvm-as; include a <code>@main()</code> to enable the execution oracle</span></label>
        <textarea id="cs-code" class="ir-input" rows="12" spellcheck="false" placeholder="${esc(EXAMPLE_SEED)}"></textarea>
      </div>
      <div style="display:flex;gap:10px;align-items:center;margin-top:12px;flex-wrap:wrap">
        <button class="btn secondary" id="cs-validate">Validate with llvm-as</button>
        <button class="btn" id="cs-save">Add to corpus</button>
        <button class="btn secondary" id="cs-example" style="margin-left:auto">Insert example</button>
      </div>
      <div id="cs-result" style="margin-top:12px"></div>
    </div>
    <div class="seed-grid">
      <div class="card seed-list" id="seed-list">${items}</div>
      <div class="card">
        <div class="pane-head"><span id="seed-name"></span>
          <span style="display:flex;align-items:center;gap:10px">
            <span class="muted small" id="seed-meta"></span>
            <button class="btn secondary small" id="seed-delete" style="padding:3px 10px;color:var(--s-critical)" hidden>delete</button>
          </span></div>
        <div id="seed-code"></div>
      </div>
    </div>`;

  let current = 0;
  const show = i => {
    current = i;
    const s = seeds[i];
    $("#seed-name").textContent = s.name;
    $("#seed-meta").textContent = `pattern: ${s.pattern} · ${s.lines} lines${s.has_main ? " · executable" : ""}`;
    $("#seed-code").innerHTML = codePane(s.content);
    $("#seed-delete").hidden = !s.custom;
    view.querySelectorAll(".seed-item").forEach(el => el.classList.toggle("active", +el.dataset.i === i));
  };
  view.querySelectorAll(".seed-item").forEach(el =>
    el.addEventListener("click", () => show(+el.dataset.i)));
  if (seeds.length) show(0);

  /* --- editor wiring --- */
  $("#add-seed-btn").addEventListener("click", () => {
    const ed = $("#seed-editor");
    ed.hidden = !ed.hidden;
    if (!ed.hidden) $("#cs-code").focus();
  });
  $("#cs-example").addEventListener("click", () => { $("#cs-code").value = EXAMPLE_SEED; });

  const resultBox = (ok, title, detail) => {
    $("#cs-result").innerHTML = `
      <div class="validate-box ${ok ? "ok" : "bad"}">
        <b>${ok ? "✓" : "✗"} ${esc(title)}</b>${detail ? `<pre>${esc(detail)}</pre>` : ""}
      </div>`;
  };

  $("#cs-validate").addEventListener("click", async () => {
    const content = $("#cs-code").value;
    if (!content.trim()) { resultBox(false, "Nothing to validate — paste some IR first."); return; }
    $("#cs-result").innerHTML = `<span class="muted small">running llvm-as…</span>`;
    const r = await fetch("/api/seeds/validate", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ content }),
    }).then(r => r.json());
    r.valid ? resultBox(true, "Valid LLVM IR — ready to add.")
            : resultBox(false, "llvm-as rejected this IR:", r.error);
  });

  $("#cs-save").addEventListener("click", async () => {
    const body = {
      name: $("#cs-name").value.trim(),
      pattern: $("#cs-pattern").value.trim() || "custom",
      content: $("#cs-code").value,
    };
    if (!body.name) { resultBox(false, "Give the seed a name first."); return; }
    $("#cs-result").innerHTML = `<span class="muted small">validating &amp; saving…</span>`;
    const r = await fetch("/api/seeds", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const d = await r.json();
    if (!r.ok) { resultBox(false, d.error || "failed", d.detail); return; }
    location.reload(); // simplest way to refresh the corpus list
  });

  $("#seed-delete").addEventListener("click", async () => {
    const s = seeds[current];
    if (!confirm(`Delete custom seed ${s.name}? Future runs will no longer use it.`)) return;
    const r = await fetch(`/api/seeds/${encodeURIComponent(s.name)}`, { method: "DELETE" });
    if (r.ok) location.reload();
    else alert((await r.json()).error || "delete failed");
  });
}

/* ---------------- new run + live log */
let logTimer = null;
async function viewNewRun() {
  clearInterval(logTimer);
  const status = await api("/api/pipeline/status");
  view.innerHTML = `
    <div class="page-head"><h1>New Run</h1><span class="crumb">launches main.py in the project root</span></div>
    <div class="grid-2">
      <div class="card">
        <h2>Configuration</h2>
        <div class="form-row"><label for="f-iters">Iterations</label>
          <input id="f-iters" type="number" min="1" max="500" value="10"></div>
        <div class="form-row"><label for="f-strategy">Seed selection strategy</label>
          <select id="f-strategy">
            <option value="">config default</option>
            <option value="round_robin">round_robin</option>
            <option value="random">random</option>
            <option value="least_mutated">least_mutated</option>
          </select></div>
        <div class="check-row"><input id="f-baseline" type="checkbox">
          <label for="f-baseline">Random baseline</label><span class="hint">control group for comparison</span></div>
        <div class="check-row"><input id="f-execution" type="checkbox">
          <label for="f-execution">Execution oracle (Mode B)</label><span class="hint">compiles &amp; runs binaries — slower</span></div>
        <br>
        <button class="btn" id="f-start" ${status.running ? "disabled" : ""}>${status.running ? "Run in progress…" : "▶ Start pipeline"}</button>
      </div>
      <div class="card">
        <h2>Live output</h2>
        <div class="terminal" id="term">${status.lines?.length ? colorize(status.lines) : '<span class="muted">— idle —</span>'}</div>
      </div>
    </div>`;
  $("#f-start").addEventListener("click", startRun);
  if (status.running) followLog(status.total_lines ? 0 : 0);
}

function colorize(lines) {
  return lines.map(l => {
    const e = esc(l);
    if (/error|invalid ir|fatal|CRASH|SEMANTIC/i.test(l)) return `<span class="t-bad">${e}</span>`;
    if (/IR is valid|Verdict|Saved/i.test(l)) return `<span class="t-ok">${e}</span>`;
    if (/Starting|Seed:/i.test(l)) return `<span class="t-info">${e}</span>`;
    return e;
  }).join("\n");
}

async function startRun() {
  const body = {
    iterations: +$("#f-iters").value || 10,
    strategy: $("#f-strategy").value || undefined,
    baseline: $("#f-baseline").checked,
    execution: $("#f-execution").checked,
  };
  const r = await fetch("/api/pipeline/start", {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
  });
  if (!r.ok) { alert((await r.json()).error || "failed to start"); return; }
  $("#f-start").disabled = true;
  $("#f-start").textContent = "Run in progress…";
  $("#term").innerHTML = "";
  followLog(0);
}

function followLog(offset) {
  clearInterval(logTimer);
  let seen = offset;
  const term = $("#term");
  const tick = async () => {
    const s = await api(`/api/pipeline/status?offset=${seen}`).catch(() => null);
    if (!s) return;
    if (s.lines.length) {
      term.innerHTML += (term.innerHTML && seen ? "\n" : "") + colorize(s.lines);
      seen = s.total_lines;
      term.scrollTop = term.scrollHeight;
    }
    updateDot(s.running);
    if (!s.running) {
      clearInterval(logTimer);
      const btn = $("#f-start");
      if (btn) { btn.disabled = false; btn.textContent = "▶ Start pipeline"; }
      term.innerHTML += `\n<span class="${s.returncode === 0 ? "t-ok" : "t-bad"}">— finished (exit ${s.returncode}) — <a href="#/runs" style="color:#6db3f2">view runs</a></span>`;
      term.scrollTop = term.scrollHeight;
    }
  };
  tick();
  logTimer = setInterval(tick, 1000);
}

/* ---------------- pipeline dot (topbar) */
function updateDot(running) {
  const dot = $("#pipeline-dot");
  dot.classList.toggle("running", !!running);
  dot.title = running ? "pipeline running" : "pipeline idle";
}
setInterval(async () => {
  const s = await api("/api/pipeline/status?offset=999999").catch(() => null);
  if (s) updateDot(s.running);
}, 5000);

/* ---------------- theme toggle */
$("#theme-toggle").addEventListener("click", () => {
  const cur = document.documentElement.dataset.theme ||
    (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
  const next = cur === "dark" ? "light" : "dark";
  document.documentElement.dataset.theme = next;
  localStorage.setItem("theme", next);
});
if (localStorage.getItem("theme")) document.documentElement.dataset.theme = localStorage.getItem("theme");
const themeParam = new URLSearchParams(location.search).get("theme");
if (themeParam === "light" || themeParam === "dark") document.documentElement.dataset.theme = themeParam;

/* ---------------- config line */
api("/api/config").then(c => {
  $("#config-line").textContent =
    `${c.backend} · ${c.model} · -${c.compare_levels.map(l => l).join(" vs -")}`;
}).catch(() => { $("#config-line").textContent = "config unavailable"; });

/* ---------------- router */
async function route() {
  clearInterval(logTimer);
  const hash = location.hash || "#/runs";
  const parts = hash.slice(2).split("/");
  document.querySelectorAll("#nav a").forEach(a =>
    a.classList.toggle("active", a.dataset.tab === (["runs", "run"].includes(parts[0]) ? "runs" : parts[0])));
  view.innerHTML = `<div class="empty">loading…</div>`;
  try {
    if (parts[0] === "runs" || parts[0] === "") await viewRuns();
    else if (parts[0] === "run" && parts[2] === "iter") await viewIteration(parts[1], +parts[3]);
    else if (parts[0] === "run") await viewRunDetail(parts[1]);
    else if (parts[0] === "seeds") await viewSeeds();
    else if (parts[0] === "new") await viewNewRun();
    else await viewRuns();
  } catch (e) {
    view.innerHTML = `<div class="empty"><span class="big">⚠️</span>${esc(e.message)}</div>`;
  }
}
addEventListener("hashchange", route);
route();
