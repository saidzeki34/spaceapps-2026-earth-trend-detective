// Independent modal; does not change the map, saved selection or trend plots.
const dialog = document.createElement('dialog');
dialog.id = 'risk-dialog';
dialog.setAttribute('aria-labelledby', 'risk-title');
dialog.innerHTML = `<style>
#risk-dialog{width:min(1120px,94vw);max-height:92vh;overflow:auto;border:1px solid #c9cec8;border-radius:8px;padding:24px;background:#fdfcfa;color:#39453e;font:14px system-ui}
#risk-dialog::backdrop{background:#0008}#risk-dialog header{display:flex;justify-content:space-between;gap:20px}
#risk-dialog form{display:flex;flex-wrap:wrap;gap:12px;align-items:end;margin:20px 0}#risk-dialog label{display:grid;gap:5px}
#risk-dialog input{width:110px}#risk-dialog input,#risk-dialog select,#risk-dialog button{padding:8px;border:1px solid #aaa;border-radius:4px;background:#fff;color:inherit}
#risk-dialog .risk-cards{display:flex;flex-wrap:wrap;gap:20px;margin:16px 0}#risk-dialog .risk-cards p{padding:12px;background:#edf2ef;margin:0;flex:1;min-width:160px}
#risk-dialog .risk-plot{height:340px;min-width:0}#risk-space{height:450px!important}#risk-dialog details{margin:16px 0}#risk-dialog table{border-collapse:collapse;width:100%}#risk-dialog th,#risk-dialog td{padding:6px;text-align:left;border-bottom:1px solid #ddd}#risk-dialog .risk-table{max-height:280px;overflow:auto}
</style><header><div><h2 id="risk-title">Water-flow risk assessment</h2><p id="risk-source"></p></div><button type="button" id="risk-close">Close</button></header>
<p>Historical flow changes and optional threshold exposure. No forecast or operational risk score.</p>
<form id="risk-form">
<label>Season<select name="months"><option value="8,9">August–September</option><option value="1,2,3,4,5,6,7,8,9,10,11,12">Annual</option><option value="10,11,12,1,2,3">Winter (Oct–Mar)</option><option value="4,5,6,7,8,9">Summer (Apr–Sep)</option></select></label>
<label>Analysis start<input name="first" type="number" min="1800" max="2200" value="1982" required></label><label>Analysis end<input name="last" type="number" min="1800" max="2200" value="2020" required></label>
<label>Baseline start<input name="basefirst" type="number" min="1800" max="2200" value="1982" required></label><label>Baseline end<input name="baselast" type="number" min="1800" max="2200" value="2001" required></label>
<label>Scenario threshold (m³/s)<input name="requirement" type="number" min="0" step="any" placeholder="Optional"></label>
<button type="submit">Calculate</button></form>
<p id="risk-status" role="status" aria-live="polite"></p><section id="risk-output" hidden>
<div class="risk-cards" id="risk-cards"></div><label>Diagram<select id="risk-projection"><option value="3d">3D: quantity, timing, variability</option><option value="2d">2D: quantity vs timing; size = variability</option></select></label>
<div id="risk-space" class="risk-plot"></div><div id="risk-volume" class="risk-plot"></div><div id="risk-timing" class="risk-plot"></div><div id="risk-flow" class="risk-plot"></div>
<div id="risk-exposure"></div><div id="risk-exposure-plot" class="risk-plot" hidden></div>
<details><summary>Evidence, coverage and limitations</summary><p id="risk-coverage"></p><ul id="risk-warnings"></ul></details>
<details id="risk-events"><summary>Below-threshold episodes (censored = incomplete duration)</summary><div class="risk-table" id="risk-event-table"></div></details>
<button type="button" id="risk-export">Export assessment JSON</button></section>`;
document.body.append(dialog);
const $ = s => dialog.querySelector(s);
const num = x => x == null ? 'Unavailable' : Number(x).toLocaleString('en-GB', {maximumFractionDigits: 2});
const esc = x => String(x ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let selection, result, controller, ticket = 0;
function clearPlots() { for (const node of dialog.querySelectorAll('.risk-plot')) if (node.data) Plotly.purge(node); }
function selectionNow() { const p = new URLSearchParams(location.hash.slice(1)); return {dataset:p.get('dataset') || p.get('c')?.toLowerCase(), gauge:p.get('gauge') || p.get('r')}; }
function installButton() {
  const side = document.querySelector('#side');
  for (const label of side?.querySelectorAll('label.check') || []) {
    if (!label.querySelector('input[disabled]') || !label.textContent.includes('Risk assessment')) continue;
    const button = document.createElement('button'); button.type = 'button'; button.className = 'link'; button.textContent = 'Open water-flow risk assessment';
    button.addEventListener('click', open); label.replaceWith(button);
  }
}
new MutationObserver(installButton).observe(document.querySelector('#side'), {childList:true, subtree:true});
installButton();
function open() { selection = selectionNow(); $('#risk-source').textContent = `${selection.dataset || ''} / gauge ${selection.gauge || 'not selected'}`; dialog.showModal(); load(); }
$('#risk-close').onclick = () => dialog.close();
dialog.addEventListener('close', () => { ++ticket; controller?.abort(); clearPlots(); });
$('#risk-form').onsubmit = e => { e.preventDefault(); load(); };
$('#risk-projection').onchange = () => { if (result) drawSpace(); };
async function load() {
  const current = ++ticket; controller?.abort(); controller = new AbortController();
  result = null; clearPlots(); $('#risk-output').hidden = true; $('#risk-status').textContent = 'Reading saved observed discharge…';
  const form = new FormData($('#risk-form'));
  const query = new URLSearchParams({...selection, months:form.get('months'), period:`${form.get('first')},${form.get('last')}`, baseline:`${form.get('basefirst')},${form.get('baselast')}`, requirement:form.get('requirement')});
  try {
    const response = await fetch(`/api/risk?${query}`, {signal:controller.signal}); const data = await response.json();
    if (current !== ticket || !dialog.open) return;
    if (!response.ok || data.status !== 'ready') throw new Error([data.error || data.message, data.build_command].filter(Boolean).join(' '));
    result = data; $('#risk-output').hidden = false;
    $('#risk-status').textContent = data.xyz_ready ? 'Historical assessment ready.' : 'Partial assessment: insufficient complete years or baseline for the full XYZ point.';
    $('#risk-source').textContent = `${data.source} / gauge ${data.gauge}`;
    draw();
  } catch (e) { if (current === ticket && e.name !== 'AbortError') $('#risk-status').textContent = e.message; }
}
function plot(id, traces, title, ytitle, extra={}) {
  return Plotly.react($(id), traces, {title:{text:title,font:{size:15}}, paper_bgcolor:'#fdfcfa',plot_bgcolor:'#fdfcfa', margin:{l:75,r:25,t:55,b:55}, yaxis:{title:{text:ytitle}}, ...extra}, {responsive:true,displaylogo:false});
}
function drawSpace() {
  const a = result.xyz;
  if (!result.xyz_ready) { $('#risk-space').textContent = 'XYZ unavailable. See coverage and limitations below.'; return; }
  const text = [`Gauge ${result.gauge}<br>${result.common_years} common complete years`];
  const x = [a.quantity_pct_decade], y = [a.timing_days_decade], z = [a.variability_pct_baseline];
  if ($('#risk-projection').value === '2d') {
    plot('#risk-space', [{type:'scatter',mode:'markers',x,y,text,marker:{size:[Math.max(10,Math.min(70,z[0]))],color:'#28715e'},hovertemplate:'%{text}<br>X=%{x:.2f}% / decade<br>Y=%{y:.2f} days / decade<extra></extra>'}], 'Flow-change diagram (marker diameter capped at 70 px)', 'Timing change (days / decade)', {xaxis:{title:{text:'Quantity change (% baseline / decade)'},zeroline:true},yaxis:{title:{text:'Timing change (days / decade)'},zeroline:true}});
  } else plot('#risk-space', [{type:'scatter3d',mode:'markers',x,y,z,text,marker:{size:8,color:'#28715e'},hovertemplate:'%{text}<br>X=%{x:.2f}% / decade<br>Y=%{y:.2f} days / decade<br>Z=%{z:.2f}% baseline<extra></extra>'}], 'Historical flow-change diagram', '', {scene:{xaxis:{title:{text:'Quantity (% baseline / decade)'}},yaxis:{title:{text:'Timing (days / decade)'}},zaxis:{title:{text:'Variability (% baseline)'}}}});
}
function draw() {
  const d = result, a = d.xyz;
  $('#risk-cards').innerHTML = [['Quantity change',a.quantity_pct_decade,'% baseline / decade'],['Timing change',a.timing_days_decade,'days / decade'],['Interannual variability',a.variability_pct_baseline,'% of baseline']].map(([label,value,unit]) => `<p>${label}<br><strong>${num(value)}</strong><br>${unit}</p>`).join('');
  drawSpace();
  const years = d.annual.map(r=>r.year);
  function annual(id, key, fitKey, title, unit, scale=1) {
    const traces = [{type:'scatter',mode:'lines+markers',x:years,y:d.annual.map(r=>r[key]==null?null:r[key]/scale),connectgaps:false,name:'Complete records'}];
    const fit = d.fits[fitKey];
    if (fit) traces.push({type:'scatter',x:years,y:years.map(y=>(fit.slope*y+fit.intercept)/scale),name:'Sen trend (common complete years)',line:{dash:'dash'}});
    if (key==='volume_m3' && d.baseline_volume_m3!=null) traces.push({type:'scatter',x:years,y:years.map(()=>d.baseline_volume_m3/scale),name:'Fixed baseline',line:{dash:'dot'}});
    plot(id,traces,title,unit,{xaxis:{title:{text:'Hydrological year (labelled by end year)'}}});
  }
  annual('#risk-volume','volume_m3','volume','Seasonal volume','Volume (hm³)',1e6);
  annual('#risk-timing','half_volume_day','timing','Half-volume delivery date','Day of hydrological year');
  const h = d.hydrograph;
  plot('#risk-flow', [{x:h.dates,y:h.low,name:'Baseline 10th percentile',line:{width:0},connectgaps:false},{x:h.dates,y:h.high,name:'Baseline 10–90% band',fill:'tonexty',line:{width:0},connectgaps:false},{x:h.dates,y:h.median,name:'Baseline median',line:{dash:'dot'},connectgaps:false},{x:h.dates,y:h.flow,name:'Observed flow',connectgaps:false},{x:h.dates,y:h.requirement,name:'Scenario threshold',line:{dash:'dash'},connectgaps:false}],`River flow: hydrological year ${d.display_year}`,'Discharge (m³/s)');
  $('#risk-coverage').textContent = `Analysis ${d.settings.period.join('–')}; fixed baseline ${d.settings.baseline.join('–')}; ${d.baseline_years} complete baseline seasons; ${d.common_years} common complete years (${d.common_year_labels.join(', ')}). Hydrological year starts in month ${d.settings.hydro_year_start_month}. Raw interannual variability includes the trend. Baseline bands require 10 valid samples per calendar day. No small-baseline stability threshold is imposed; inspect absolute baseline volume (${num(d.baseline_volume_m3)} m³).`;
  $('#risk-warnings').innerHTML = d.warnings.map(w=>`<li>${esc(w)}</li>`).join('');
  $('#risk-events').hidden = !d.exposure; $('#risk-exposure-plot').hidden = !d.exposure;
  $('#risk-exposure').textContent = '';
  if (d.exposure) {
    const e=d.exposure;
    $('#risk-exposure').textContent = `Scenario exposure: ${num(e.below_percent)}% of ${e.valid_days} valid selected-season days below threshold; ${e.missing_days} missing selected-season days. ${e.observed_segments} observed episode segments; ${e.complete_events} complete episodes. Longest observed segment: ${e.longest_observed_segment_days} days; median complete duration: ${num(e.median_complete_duration_days)} days. Deficit: ${num(e.deficit_m3)} m³; above-requirement volume: ${num(e.above_requirement_m3)} m³.`;
    plot('#risk-exposure-plot',[{type:'bar',x:d.annual_exposure.map(r=>r.year),y:d.annual_exposure.map(r=>r.below_percent),name:'Below-threshold days'}],'Annual scenario exposure (valid selected-season days)','Days below threshold (%)');
    $('#risk-event-table').innerHTML = '<table><thead><tr><th>Start</th><th>End</th><th>Days</th><th>Deficit m³</th><th>Censored</th></tr></thead><tbody>'+e.events.map(r=>`<tr><td>${esc(r.start)}</td><td>${esc(r.end)}</td><td>${r.days}</td><td>${num(r.deficit_m3)}</td><td>${r.censored?'Yes':'No'}</td></tr>`).join('')+'</tbody></table>';
  }
}
$('#risk-export').onclick = () => {
  if (!result) return;
  const url = URL.createObjectURL(new Blob([JSON.stringify(result,null,2)],{type:'application/json'}));
  const a=document.createElement('a');a.href=url;a.download='rivascope-risk-assessment.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
};
