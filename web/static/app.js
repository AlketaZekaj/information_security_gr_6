/* JWT Lab: the repository is the source of truth; all displayed measurements are real CSV rows. */
const $ = (selector) => document.querySelector(selector);
const esc = (value) => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let state, result, selectedRun = '', page = 'overview', activeCase = 'CTRL-01';
let selectedTargets = new Set(), launcher = 'native', query = '', category = 'all';
let resultMode = 'default', resultTarget = 'all', resultVerdict = 'all', resultView = 'matrix';
let pollTimer, toastTimer, busy = false;
const names = {overview:'Overview', tokens:'Token studio', evaluate:'Evaluation', results:'Results explorer'};
const ecosystem = (c) => c.target_dir.includes('python') ? 'Python' : c.target_dir.includes('dotnet') ? '.NET' : c.target_dir.includes('java') ? 'Java' : c.target_dir.includes('/go-') ? 'Go' : 'Node.js';
const icon = (c) => { const [style, label] = {'.NET':['dotnet','.N'],Python:['python','Py'],Java:['java','Jv'],Go:['go','Go']}[ecosystem(c)] || ['','JS']; return `<span class="target-icon ${style}">${label}</span>`; };
const badge = (label, type='neutral') => `<span class="badge ${type}">${esc(label)}</span>`;
const when = (value) => value ? new Date(value).toLocaleString(undefined, {dateStyle:'medium',timeStyle:'short'}) : 'Not generated yet';
function toast(message) { $('#toast').textContent = message; $('#toast').classList.add('show'); clearTimeout(toastTimer); toastTimer = setTimeout(() => $('#toast').classList.remove('show'), 5000); }
async function api(path, body) {
  const response = await fetch(path, body === undefined ? {} : {method:'POST', headers:{'Content-Type':'application/json','X-Lab-Token':state.csrf}, body:JSON.stringify(body)});
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || `Request failed (${response.status})`);
  return data;
}
function heading(kicker, title, subtitle, actions='') {
  return `<div class="heading"><div><span class="eyebrow">${kicker}</span><h1>${title}</h1><p>${subtitle}</p></div><div class="actions">${actions}</div></div>`;
}
function stats(items) { return `<div class="stats">${items.map(([label, value, note]) => `<div class="stat"><span class="stat-label">${label}</span><strong>${value}</strong><small>${note}</small></div>`).join('')}</div>`; }
function overview() {
  return heading('THE RESEARCH WORKSPACE', 'Security by default?', 'An interactive look at how JWT libraries decide what to trust.', '<a class="button" href="#results">Explore results <span>↗</span></a>') +
    `<section class="hero"><div class="hero-copy"><span class="eyebrow">JWT VALIDATION · A COMPARATIVE STUDY</span><h2>Same token.<br>Different defaults.<br><em>How much do they trust?</em></h2><p>We put JWT libraries and middleware to the same test — then compare their default behavior with a common, hardened policy.</p><div class="actions"><a href="#evaluate" class="button lime">Run an evaluation <span>↗</span></a><a href="#tokens" class="button ghost">Inspect the tokens</a></div></div><div class="token-visual" aria-label="A JWT has a header, payload, and signature"><div class="visual-label">ANATOMY OF A TRUST DECISION</div><div class="token-block"><span class="brace">{ }</span><div><strong>HEADER</strong><code>"alg": "RS256", "typ": "JWT"</code></div><span class="index">01</span></div><div class="token-block"><span class="brace">{ }</span><div><strong>PAYLOAD</strong><code>iss · aud · exp · nbf</code></div><span class="index">02</span></div><div class="token-block"><span class="brace">#</span><div><strong>SIGNATURE</strong><code>verified ≠ fully validated</code></div><span class="index">03</span></div><div class="visual-footer">ONE CHANGE AT A TIME. EVERY RESPONSE RECORDED.</div></div></section>` +
    stats([['Targets under test', state.components.length, 'Across Python, Node.js, .NET, Java & Go'],['Token test cases',state.matrix.length,'One property changed per variant'],['Configurations','02','Default vs. hardened'],['Shared policy','01','The same expectations for everyone']]) +
    `<div class="section-title"><h2>From an idea to evidence</h2><span>THE EXPERIMENT / 3 STEPS</span></div><section class="steps"><a class="step" href="#tokens"><span class="number">01</span><span class="step-arrow">↗</span><h3>Generate controlled tokens</h3><p>Start with a valid JWT. Change one claim, algorithm, or signature property to isolate each validation check.</p></a><a class="step" href="#evaluate"><span class="number">02</span><span class="step-arrow">↗</span><h3>Send them to every target</h3><p>Run the same cases in default and hardened modes. A valid control token must pass before testing begins.</p></a><a class="step" href="#results"><span class="number">03</span><span class="step-arrow">↗</span><h3>Make the differences visible</h3><p>Compare expected and observed outcomes. Separate policy mismatches from request errors and setup failures.</p></a></section>
    <div class="two-col"><section><div class="section-title"><h2>Meet the targets</h2><span>${state.components.length} IMPLEMENTATIONS</span></div><div class="panel"><div class="targets-mini">${state.components.map(c => `<div class="target-mini">${icon(c)}<div><strong>${esc(c.name)}</strong><small>${esc(ecosystem(c))} · ${esc(c.type)}</small></div></div>`).join('')}</div></div></section><section><div class="section-title"><h2>The shared policy</h2><span>policy.json</span></div><div class="panel policy-lines"><div><span>Signing algorithm</span><code>${esc(state.policy.allowed_algorithms.join(', '))}</code></div><div><span>Required claims</span><code>${esc(state.policy.required_claims.join(' · '))}</code></div><div><span>Clock tolerance</span><code>${esc(state.policy.clock_skew_seconds)} seconds</code></div><div><span>Not before (nbf)</span><code>Optional, checked if present</code></div></div></section></div>
    <div class="section-title"><h2>Two questions guide the study</h2><span>RESEARCH FOCUS</span></div><section class="panel research"><div><strong>RQ1 / What is accepted out of the box?</strong><p>Which targets accept tokens with missing or invalid registered claims, or unexpected signing algorithms, under their default configuration?</p></div><div><strong>RQ2 / What changes after hardening?</strong><p>How does enforcing the common policy change validation behavior, and which settings need to be configured?</p></div></section>
    <div class="callout"><strong>Ready to present.</strong> ${state.runs.length ? `${state.runs.length} saved result sets are available to explore. Historical measurements are labeled with their source and date; new evaluations are saved separately.` : 'Generate tokens and run your first evaluation to build a result set.'} Use presentation mode for a focused, wider view.</div>`;
}
function caseList() {
  const cases = state.matrix.filter(c => (category==='all' || c.category===category) && `${c.id} ${c.description}`.toLowerCase().includes(query.toLowerCase()));
  return cases.length ? cases.map(c => `<button class="case-button ${c.id===activeCase?'active':''}" data-case="${esc(c.id)}" aria-pressed="${c.id===activeCase}">${badge(c.expected, c.expected==='accept'?'pass':'neutral')}<strong>${esc(c.id)}</strong><small>${esc(c.changed_property)}</small></button>`).join('') : '<div class="empty">No matching test cases.</div>';
}
function tokenDetail() {
  const c = state.matrix.find(c => c.id===activeCase), t = state.tokens.tokens.find(t => t.id===activeCase);
  const control = state.tokens.tokens.find(t => t.id==='CTRL-01');
  const changes = t && control ? ['header','payload'].flatMap(part => [...new Set([...Object.keys(control[part]), ...Object.keys(t[part])])].filter(key => JSON.stringify(control[part][key])!==JSON.stringify(t[part][key])).map(key => `${part}.${key}: ${JSON.stringify(control[part][key])} → ${JSON.stringify(t[part][key]) ?? '(removed)'}`)) : [];
  return `<div class="token-heading"><h2>${esc(c.id)}</h2>${badge(`Expected: ${c.expected}`, c.expected==='accept'?'pass':'neutral')}</div><p class="description">${esc(c.description)}</p><div class="changed">Δ ${esc(c.changed_property)}</div>${t ? `<div class="token-panels"><div><div class="code-title">01 / HEADER</div><pre>${esc(JSON.stringify(t.header,null,2))}</pre></div><div><div class="code-title">02 / PAYLOAD</div><pre>${esc(JSON.stringify(t.payload,null,2))}</pre></div></div><div class="code-title">03 / ENCODED TOKEN<button class="plain" data-action="copy-token">Copy token ↗</button></div><pre class="encoded">${esc(t.raw)}</pre>${changes.length?`<div class="code-title">DIFFERENCE FROM CONTROL</div><pre>${esc(changes.join('\n'))}</pre>`:''}<p class="description">Decoded for inspection; decoding alone does not verify the signature. The generator's verifier runs after generation.</p>` : '<div class="empty"><h3>This token has not been generated.</h3><p>Generate the test set to inspect its header, payload, and encoded JWT.</p></div>'}<div class="callout"><strong>What this tests</strong><br>${esc(c.requirement)}</div>`;
}
function tokens() {
  const generated = state.tokens.generated_at;
  const stale = generated && Date.now()-new Date(generated).getTime()>3600000;
  return heading('01 / CONTROLLED INPUTS', 'Token studio', 'One valid control. One deliberate change in every variant.', `<button class="button primary" data-action="generate" ${busy?'disabled':''}>${busy?'Operation running…':'↻ Generate fresh tokens'}</button>`) +
    `<div class="source">${state.tokens.tokens.length} / ${state.matrix.length} tokens available · Generated ${esc(when(generated))}</div>${stale?'<div class="callout"><strong>This token set is over an hour old.</strong> The control token may have expired. Generate a fresh set for inspection; the evaluation harness refreshes tokens before every target and mode.</div>':''}<div class="toolbar"><input id="case-search" type="search" placeholder="Search test cases…" aria-label="Search test cases" value="${esc(query)}"><select id="case-category" aria-label="Filter by category"><option value="all">All categories</option>${[...new Set(state.matrix.map(c=>c.category))].map(c=>`<option ${category===c?'selected':''}>${c}</option>`).join('')}</select><span class="spacer"></span><span class="source">Synthetic tokens · local test keys</span></div><div class="studio"><div class="case-list" id="case-list">${caseList()}</div><section class="panel" id="token-detail">${tokenDetail()}</section></div>${state.job.kind==='generate'?`<div class="section-title"><h2>Generation log</h2><span id="job-status">${esc(state.job.status)}</span></div><pre class="log" id="job-log">${esc(state.job.logs.join('\n') || 'Preparing tokens…')}</pre>`:''}`;
}
function progress() {
  const job = state.job, modes = Object.values(job.targets).flatMap(v=>Object.values(v));
  const finished = modes.filter(v=>v!=='pending').length;
  return `<div class="section-title"><h2>${job.status==='running'?'Evaluation in progress':'Evaluation activity'}</h2>${badge(job.status, job.status==='failed'?'fail':job.status==='completed'?'pass':'neutral')}</div><div class="panel"><div class="source">${finished} / ${modes.length} target configurations resolved. Progress updates after each configuration completes.</div><div class="progress-track"><div style="width:${modes.length ? finished/modes.length*100 : 0}%"></div></div>${Object.entries(job.targets).map(([name,modes])=>`<div class="progress-target"><strong>${esc(name)}</strong><div>${Object.entries(modes).map(([mode,status])=>badge(`${mode}: ${status}`,status==='measured'?'pass':status==='setup failed'?'fail':'neutral')).join('')}</div></div>`).join('')}${job.result?`<div class="callout">${job.status==='completed'?'Measurements saved.':'The run finished with issues; review setup failures and errors before interpreting the data.'} <a href="#results"><strong>Explore these results ↗</strong></a></div>`:''}<div class="code-title">RUNNER OUTPUT</div><pre class="log" id="job-log">${esc(job.logs.join('\n') || 'Preparing keys and starting the harness…')}</pre></div>`;
}
function evaluate() {
  return heading('02 / THE EXPERIMENT', 'Run an evaluation', 'Send the full token matrix to the targets you choose, in both configurations.', '<a href="#tokens" class="button">Inspect tokens ↗</a>') +
    `<div class="callout"><strong>Built on your existing harness.</strong> Each target is started, given fresh verified tokens, and checked with the valid control before measurement. Default and hardened configurations use the same policy expectations.</div><div class="section-title"><h2>Choose your targets</h2><button class="plain" data-action="select-all" ${busy?'disabled':''}>${selectedTargets.size===state.components.length?'Clear selection':'Select all'}</button></div><div class="target-grid">${state.components.map(c=>`<label class="target-card"><div class="card-top">${icon(c)}<input type="checkbox" name="target" value="${esc(c.name)}" aria-label="Select ${esc(c.name)}" ${selectedTargets.has(c.name)?'checked':''} ${busy?'disabled':''}></div><h3>${esc(c.name)}</h3><p>${esc(ecosystem(c))} · ${esc(c.type)} · v${esc(c.version)}</p></label>`).join('')}</div><div class="evaluation-controls"><label>Run with <select id="launcher" ${busy?'disabled':''}><option value="native" ${launcher==='native'?'selected':''}>Local processes (native)</option><option value="docker" ${launcher==='docker'?'selected':''}>Docker Compose</option></select></label><div class="actions"><span class="source" id="request-count">${selectedTargets.size * state.matrix.length * 2} planned measurements</span><button class="button primary" id="run-button" data-action="run" ${busy || !selectedTargets.size?'disabled':''}>${busy?'Evaluation running…':'▷ Start evaluation'}</button></div></div><p class="description">Native mode requires the selected targets' installed dependencies and runtimes. Docker mode requires a running Docker engine. Results are saved in a new timestamped folder. Keep the server running until the evaluation finishes.</p><div id="progress">${state.job.kind==='run'?progress():`<div class="panel empty"><h3>Your experiment is ready.</h3><p>Select targets and start the run. Their progress and runner output will appear here.</p></div>`}</div>`;
}
function summary(rows) {
  const valid = rows.filter(r=>r.outcome!=='error');
  const invalid = valid.filter(r=>r.expected==='reject');
  return {matches:valid.filter(r=>r.verdict==='pass').length, mismatches:valid.filter(r=>r.verdict==='fail').length,
    errors:rows.length-valid.length, invalid:invalid.length, falseAccepts:invalid.filter(r=>r.outcome==='accept').length};
}
function rate(rows) { const s=summary(rows); return s.invalid ? `${Math.round(s.falseAccepts/s.invalid*100)}%` : '—'; }
function chart(c) {
  return `<section class="panel compare-card"><h3>${esc(c.name)}</h3>${['default','hardened'].map(mode=>{
    const rows=result.rows.filter(r=>r.component===c.name && r.config===mode), s=summary(rows);
    const value=s.invalid?s.falseAccepts/s.invalid*100:0;
    return `<div class="bar-row"><span>${mode}</span><div class="bar-track"><div class="bar ${mode}" style="width:${value}%"></div></div><strong>${rate(rows)}</strong></div>`;
  }).join('')}<p class="chart-footnote">${['default','hardened'].map(mode=>{const s=summary(result.rows.filter(r=>r.component===c.name&&r.config===mode));return `${mode}: ${s.falseAccepts}/${s.invalid} false accepts`;}).join(' · ')}</p></section>`;
}
function filteredRows() {
  return result.rows.filter(r=>r.config===resultMode && (resultTarget==='all'||r.component===resultTarget) && (resultVerdict==='all'||r.verdict===resultVerdict) && (category==='all'||r.category===category));
}
function resultTable() {
  const rows=filteredRows();
  if (!rows.length) return '<div class="panel empty"><h3>No measurements match these filters.</h3><p>Choose another configuration, target, or outcome.</p></div>';
  if (resultView==='requests') return `<div class="table-wrap"><table><thead><tr><th>Test case</th><th>Target</th><th>Expected</th><th>Observed</th><th>HTTP</th><th>Latency</th><th>Policy</th></tr></thead><tbody>${rows.map(r=>`<tr><td><button class="plain" data-row="${result.rows.indexOf(r)}">${esc(r.test_id)} ↗</button></td><td>${esc(r.component)}</td><td>${esc(r.expected)}</td><td>${esc(r.outcome)}</td><td>${esc(r.actual_status||'—')}</td><td>${Number.isFinite(Number(r.latency_ms))&&r.latency_ms!==''?Number(r.latency_ms).toFixed(1)+' ms':'—'}</td><td>${badge(r.verdict==='pass'?'Match':r.verdict==='fail'?'Mismatch':'Error',r.verdict)}</td></tr>`).join('')}</tbody></table></div>`;
  const targets=state.components.filter(c=>resultTarget==='all'||c.name===resultTarget);
  const cases=state.matrix.filter(c=>(category==='all'||c.category===category) && (resultVerdict==='all'||rows.some(r=>r.test_id===c.id)));
  return `<div class="table-wrap"><table><thead><tr><th>Test case / expected</th>${targets.map(c=>`<th class="matrix-name">${esc(c.name)}</th>`).join('')}</tr></thead><tbody>${cases.map(c=>`<tr><td>${esc(c.id)} <small class="muted">/ ${esc(c.expected)}</small></td>${targets.map(target=>{
    const row=rows.find(r=>r.test_id===c.id&&r.component===target.name);
    if (!row) return '<td><span class="muted" title="Not measured in this result set, or excluded by the outcome filter">—</span></td>';
    return `<td><button class="cell-button" data-row="${result.rows.indexOf(row)}" aria-label="${esc(c.id)} on ${esc(target.name)}: ${esc(row.outcome)}, ${row.verdict}">${badge(row.outcome==='error'?'! Error':`${row.verdict==='pass'?'✓':'!'} ${row.outcome==='accept'?'Accepted':'Rejected'}`,row.verdict)}</button></td>`;
  }).join('')}</tr>`).join('')}</tbody></table></div>`;
}
function results() {
  if (!result) return heading('03 / THE EVIDENCE','Results explorer','Compare observed behavior against the shared policy.')+'<div class="panel empty"><h3>No saved measurements yet.</h3><p>Run an evaluation to see the comparison here.</p><a href="#evaluate" class="button primary">Set up an evaluation ↗</a></div>';
  const s=summary(result.rows), failures=result.metadata.setup_failures||[];
  const measured=state.components.filter(c=>result.rows.some(r=>r.component===c.name));
  return heading('03 / THE EVIDENCE','Results explorer','Understand the difference between a valid signature and a validated token.',`<a class="button" href="/api/export?run=${encodeURIComponent(selectedRun)}">↓ Export raw CSV</a>`) +
    `<div class="toolbar"><label for="run-select" class="source">RESULT SET</label><select id="run-select" class="run-select">${state.runs.map(r=>`<option value="${esc(r.id)}" ${r.id===selectedRun?'selected':''}>${esc(r.label)}</option>`).join('')}</select><span class="spacer"></span><span class="source">Recorded ${esc(when(result.metadata.started_at_utc))}</span></div><p class="source">Source: results/${esc(selectedRun)}/raw.csv · ${measured.length} of ${state.components.length} targets measured · ${new Set(result.rows.map(r=>r.test_id)).size} test cases · ${(result.metadata.git_commit||result.metadata.base_commit)?'Commit '+esc((result.metadata.git_commit||result.metadata.base_commit).slice(0,8)):'Commit unavailable'}</p>${failures.length?`<div class="error-banner"><strong>${failures.length} setup failure(s), excluded from measurements.</strong>${failures.map(f=>`<div>${esc(f.message)}</div>`).join('')}</div>`:''}` +
    stats([['Recorded requests',result.rows.length,'Both configurations in this result set'],['Policy matches',s.matches,'Observed outcome matches expectation'],['Policy mismatches',s.mismatches,'False accepts + false rejects'],['Request errors',s.errors,'Excluded from validation rates']]) +
    `<div class="section-title"><h2>What slips through?</h2><span>FALSE-ACCEPT RATE · LOWER IS BETTER</span></div><div class="compare-grid">${measured.map(chart).join('')}</div><p class="chart-footnote">False-accept rate = accepted expected-reject tokens / expected-reject tokens without a request error. A dash means there is no eligible data. A 0% rate alone does not establish correct acceptance of valid tokens.</p><div class="section-title"><h2>Every case, every response</h2><div class="view-toggle"><button data-view="matrix" class="${resultView==='matrix'?'active':''}">Matrix</button><button data-view="requests" class="${resultView==='requests'?'active':''}">Requests</button></div></div><div class="toolbar"><div class="view-toggle">${['default','hardened'].map(m=>`<button data-mode="${m}" class="${resultMode===m?'active':''}">${m==='default'?'Default':'Hardened'}</button>`).join('')}</div><select id="result-target" aria-label="Filter target"><option value="all">All targets</option>${state.components.map(c=>`<option value="${esc(c.name)}" ${resultTarget===c.name?'selected':''}>${esc(c.name)}</option>`).join('')}</select><select id="result-category" aria-label="Filter category"><option value="all">All categories</option>${[...new Set(state.matrix.map(c=>c.category))].map(c=>`<option ${category===c?'selected':''}>${c}</option>`).join('')}</select><select id="result-verdict" aria-label="Filter outcome">${[['all','All outcomes'],['pass','Policy matches'],['fail','Policy mismatches'],['error','Request errors']].map(([v,l])=>`<option value="${v}" ${v===resultVerdict?'selected':''}>${l}</option>`).join('')}</select></div><div id="result-table">${resultTable()}</div><div class="legend"><span>${badge('✓ Match','pass')} Matches policy</span><span>${badge('! Mismatch','fail')} Violates policy</span><span>${badge('! Error','error')} Not a validation result</span><span>— Not measured / filtered out</span></div><p class="description">Click any measured cell or request to inspect its response. Both CTRL-01 and NBF-MISSING should be accepted: the policy requires iss, aud, and exp, while nbf is optional.</p>`;
}
function render() {
  page=location.hash.slice(1) || 'overview'; if (!names[page]) page='overview';
  busy=state.job.status==='running';
  document.title=`${names[page]} · JWT Lab`;
  $('#breadcrumb').textContent=names[page];
  document.querySelectorAll('[data-page]').forEach(a=>{a.classList.toggle('active',a.dataset.page===page); if(a.dataset.page===page)a.setAttribute('aria-current','page');else a.removeAttribute('aria-current');});
  $('#content').innerHTML=({overview,tokens,evaluate,results}[page])();
}
async function loadResults(id) {
  if (!id) {result=null;return;}
  result=await api(`/api/results?run=${encodeURIComponent(id)}`); selectedRun=id;
}
async function refresh() {
  state=await api('/api/state');
  if(state.runs.length) await loadResults(state.job.result || selectedRun || state.runs[0].id);
  render();
}
function poll() {
  clearTimeout(pollTimer);
  pollTimer=setTimeout(async()=>{
    try {
      state.job=await api('/api/job');
      if(state.job.status!=='running') {
        await refresh(); toast(state.job.status==='completed'?'Operation complete. Your workspace is up to date.':`Operation ${state.job.status}. Review the runner log.`); return;
      }
      if(page==='evaluate') $('#progress').innerHTML=progress();
      if(page==='tokens' && $('#job-log')) $('#job-log').textContent=state.job.logs.join('\n') || 'Preparing tokens…';
      poll();
    } catch(error) { toast(`Connection interrupted: ${error.message}. Retrying…`); poll(); }
  },1200);
}
async function start(kind) {
  state.job=await api(`/api/${kind}`,kind==='run'?{components:[...selectedTargets],launcher}:{});
  render(); poll();
}
$('#content').addEventListener('click',async event=>{
  const button=event.target.closest('button'); if(!button) return;
  try {
    if(button.dataset.case) {activeCase=button.dataset.case;$('#case-list').innerHTML=caseList();$('#token-detail').innerHTML=tokenDetail();}
    if(button.dataset.action==='generate') await start('generate');
    if(button.dataset.action==='run') await start('run');
    if(button.dataset.action==='select-all'){selectedTargets=selectedTargets.size===state.components.length?new Set():new Set(state.components.map(c=>c.name));render();}
    if(button.dataset.action==='copy-token') {await navigator.clipboard.writeText(state.tokens.tokens.find(t=>t.id===activeCase).raw);toast('Token copied to clipboard.');}
    if(button.dataset.mode){resultMode=button.dataset.mode;render();}
    if(button.dataset.view){resultView=button.dataset.view;render();}
    if(button.dataset.row!==undefined) {
      const r=result.rows[Number(button.dataset.row)];
      $('#detail-content').innerHTML=`<h2>${esc(r.test_id)}</h2><p class="description">${esc(r.component)} · v${esc(r.version)} · ${esc(r.config)}</p>${badge(r.verdict==='pass'?'Matches policy':r.verdict==='fail'?'Policy mismatch':'Request error',r.verdict)}<table class="details-table"><tbody>${[['Expected',r.expected],['Observed',r.outcome],['HTTP status',r.actual_status||'No response'],['Latency',r.latency_ms?Number(r.latency_ms).toFixed(2)+' ms':'Unavailable'],['Response body',r.response_body||'(empty)'],['WWW-Authenticate',r.www_authenticate||'(not present)']].map(([k,v])=>`<tr><td>${esc(k)}</td><td>${esc(v)}</td></tr>`).join('')}</tbody></table><div class="callout">${esc(state.matrix.find(c=>c.id===r.test_id)?.requirement||'Historical test case')}</div>`;
      $('#detail').showModal();
    }
  } catch(error) {toast(error.message);}
});
$('#content').addEventListener('input',event=>{if(event.target.id==='case-search'){query=event.target.value;$('#case-list').innerHTML=caseList();}});
$('#content').addEventListener('change',async event=>{
  const el=event.target;
  try {
    if(el.name==='target') {el.checked?selectedTargets.add(el.value):selectedTargets.delete(el.value);$('#request-count').textContent=`${selectedTargets.size*state.matrix.length*2} planned measurements`;$('#run-button').disabled=!selectedTargets.size||busy;$('[data-action="select-all"]').textContent=selectedTargets.size===state.components.length?'Clear selection':'Select all';}
    if(el.id==='launcher') launcher=el.value;
    if(el.id==='case-category'){category=el.value;$('#case-list').innerHTML=caseList();}
    if(el.id==='run-select'){await loadResults(el.value);render();}
    if(el.id==='result-target'){resultTarget=el.value;$('#result-table').innerHTML=resultTable();}
    if(el.id==='result-category'){category=el.value;$('#result-table').innerHTML=resultTable();}
    if(el.id==='result-verdict'){resultVerdict=el.value;$('#result-table').innerHTML=resultTable();}
  } catch(error){toast(error.message);}
});
$('#close-detail').addEventListener('click',()=>$('#detail').close());
$('.skip-link').addEventListener('click',event=>{event.preventDefault();$('#content').focus();});
$('#detail').addEventListener('click',event=>{if(event.target===$('#detail')){const r=$('#detail').getBoundingClientRect();if(event.clientX<r.left||event.clientX>r.right||event.clientY<r.top||event.clientY>r.bottom)$('#detail').close();}});
$('#present').addEventListener('click',()=>{const enabled=document.body.classList.toggle('presenting');$('#present').textContent=enabled?'↙ Exit presentation':'↗ Presentation mode';$('#present').setAttribute('aria-pressed',String(enabled));});
window.addEventListener('hashchange',()=>{if(state){category='all';render();window.scrollTo(0,0);}});
(async()=>{
  try {await refresh();selectedTargets=new Set(state.components.map(c=>c.name));render();if(state.job.status==='running')poll();}
  catch(error){$('#content').innerHTML=`<div class="error-banner"><strong>Could not load the workspace.</strong><p>${esc(error.message)}</p>Start the Python server and reload this page.</div>`;}
})();
