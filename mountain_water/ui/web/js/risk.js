import {ROLES,surface,interpretation,selectionFromHash} from './risk-rules.js';
const dialog=document.createElement('dialog');dialog.id='risk-dialog';dialog.className='about';dialog.setAttribute('aria-labelledby','risk-title');
dialog.innerHTML=`<style>
/* The existing dialog and results classes supply the selected UI's visual style. */
#risk-dialog{width:min(1150px,94vw);max-height:92vh;overflow:auto}
#risk-dialog .risk-body{padding:16px}
#risk-dialog form{display:flex;flex-wrap:wrap;gap:14px;align-items:end;margin-bottom:18px}
#risk-dialog label{display:grid;gap:5px}#risk-dialog input{width:105px;border:1px solid var(--k);padding:3px 8px 2px}
#risk-dialog .risk-body p{padding:12px 0;color:var(--gw)}
#risk-dialog .risk-body button{border-color:var(--k)}#risk-dialog .risk-body button:hover{background:var(--k);color:var(--w)}
#risk-dialog .risk-body th,#risk-dialog .risk-body td{border-color:var(--rw)}#risk-dialog .risk-body th{color:var(--gw)}
#risk-verdict{border-top:1px solid var(--rw);border-bottom:1px solid var(--rw);padding:16px 0;margin:18px 0}
#risk-dialog .risk-plot{height:360px}#risk-space,#risk-surface{height:470px!important}
#risk-dialog details{margin:16px 0}#risk-dialog pre{white-space:pre-wrap}#risk-dialog .risk-table{max-height:260px;overflow:auto}
</style><header><h2 id='risk-title'>River water: change and operational screening</h2><button id='risk-close'>Close</button></header><div class='risk-body res'><p id='risk-source'></p>
<form id='risk-form'><label>Operation<select id='risk-role'></select></label><label>Season<select name='months'><option value='8,9'>August–September</option><option value='1,2,3,4,5,6,7,8,9,10,11,12'>Annual</option><option value='10,11,12,1,2,3'>Winter (Oct–Mar)</option><option value='4,5,6,7,8,9'>Summer (Apr–Sep)</option></select></label>
<label>Analysis start<input name='first' type='number' min='1800' max='2200' value='1982' required></label><label>Analysis end<input name='last' type='number' min='1800' max='2200' value='2020' required></label><label>Baseline start<input name='basefirst' type='number' min='1800' max='2200' value='1982' required></label><label>Baseline end<input name='baselast' type='number' min='1800' max='2200' value='2001' required></label><label>Scenario flow threshold (m³/s)<input name='requirement' type='number' min='0' step='any' placeholder='Optional'></label><button>Calculate</button></form>
<p id='risk-status' role='status'></p><section id='risk-output' hidden><div class='readout' id='risk-cards'></div><section id='risk-verdict'></section>
<details><summary>How the hardcoded screening works</summary><p>Prototype rules, not scientifically calibrated safety limits. Relatively stable: |volume change| &lt; 5%/decade, |timing change| &lt; 3 days/decade and variation &lt; 15%. Changing: any of these limits is reached. Strong change or high variability: |volume change| ≥ 10%, |timing change| ≥ 7 days or variation ≥ 30%; this overrides Changing. Increasing volume is change, not automatically a shortage. Missing indicators mean insufficient evidence. These rules do not measure acceleration or predict the future.</p><p>Operational screening is separate: a supplied threshold plus any observed shortfall flags a potential constraint. No observed shortfall with less than 90% daily coverage remains undetermined. Otherwise no historical shortfall is detected—not a safe-to-operate approval.</p></details>
<h3>Historical variability surface</h3><p>Each cell is calculated from complete seasonal volumes: X = last year of the window; Y = window length (5–15 years); height/color = standard deviation as % of the fixed baseline. Overlapping windows are not independent. This is not a forecast, a risk probability, or a surface fitted through the three indicator values. Gaps stay blank.</p><label>Surface view<select id='risk-surface-mode'><option value='3d'>3D variability surface</option><option value='2d'>2D variability heatmap</option></select></label><div id='risk-surface' class='risk-plot'></div>
<h3>Three-indicator position</h3><label>Indicator view<select id='risk-projection'><option value='3d'>3D: volume, timing, variation</option><option value='2d'>2D: volume and timing; color = variation</option></select></label><div id='risk-space' class='risk-plot'></div>
<div id='risk-volume' class='risk-plot'></div><div id='risk-timing' class='risk-plot'></div><div id='risk-flow' class='risk-plot'></div><p id='risk-exposure'></p><div id='risk-exposure-plot' class='risk-plot' hidden></div>
<details><summary>Coverage and limitations</summary><p id='risk-coverage'></p><ul id='risk-warnings'></ul></details><details id='risk-events'><summary>Below-threshold episodes</summary><div id='risk-event-table' class='risk-table'></div></details><button id='risk-export'>Export assessment JSON</button></section></div>`;
document.body.append(dialog);
const $=s=>dialog.querySelector(s), topRole=document.querySelector('#occupation-select');
const esc=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const num=x=>x==null?'Unavailable':Number(x).toLocaleString('en-GB',{maximumFractionDigits:2});
$('#risk-role').innerHTML='<option value="">Select an operation</option>'+Object.entries(ROLES).map(([id,v])=>`<option value='${id}'>${v[0]}</option>`).join('');
let selection,result,controller,ticket=0;
let drawing=Promise.resolve();
// Plotly mutates its nodes asynchronously. Never purge or redraw them until every
// plot from the previous operation has settled, even when its request is stale.
function enqueue(work){
  const next=drawing.then(work);
  drawing=next.catch(()=>{});
  return next;
}
function current(t){return t===ticket&&dialog.open;}
function redraw(t,work){return enqueue(()=>current(t)?work():undefined);}
function showError(t,error){if(current(t)&&error.name!=='AbortError')$('#risk-status').textContent=error.message;}
function clearResult(){result=null;$('#risk-output').hidden=true;}

function purge(){for(const n of dialog.querySelectorAll('.risk-plot')){if(n.data)Plotly.purge(n);n.textContent='';}}
// The selected interface redraws result blocks; one delegated handler survives those redraws.
document.addEventListener('click', event => {
  if (!event.target.closest('[data-risk-open]')) return;
  event.preventDefault();
  open();
});
function open(){
  const next=selectionFromHash(location.hash);
  if(!selection||selection.dataset!==next.dataset||selection.gauge!==next.gauge)$('#risk-form').elements.requirement.value='';
  selection=next;
  const p=new URLSearchParams(location.hash.slice(1));
  $('#risk-role').value=topRole?.value||p.get('o')||'';
  $('#risk-source').textContent=`Gauge ${selection.gauge||'not selected'} / ${selection.dataset||'no source selected'}`;
  if(!dialog.open)dialog.showModal();
  load();
}
function roleChanged(){ $('#risk-role').value=topRole?.value||'';$('#risk-form').elements.requirement.value='';result=null;if(dialog.open)load(); }
topRole?.addEventListener('change',roleChanged);
$('#risk-role').onchange=()=>{if(topRole){topRole.value=$('#risk-role').value;topRole.dispatchEvent(new Event('change',{bubbles:true}));}else{$('#risk-form').elements.requirement.value='';load();}};
$('#risk-close').onclick=()=>dialog.close();
dialog.addEventListener('close',()=>{
  // Native close events are queued: a previous close must not cancel a reopen.
  if(dialog.open)return;
  const t=++ticket;
  controller?.abort();clearResult();$('#risk-status').textContent='';
  enqueue(()=>{if(t===ticket&&!dialog.open)purge();});
});
$('#risk-form').onsubmit=e=>{e.preventDefault();load();};
$('#risk-projection').onchange=()=>{const t=ticket;redraw(t,()=>result?space(result):undefined).catch(e=>showError(t,e));};
$('#risk-surface-mode').onchange=()=>{const t=ticket;redraw(t,()=>result?drawSurface(result):undefined).catch(e=>showError(t,e));};
async function load(){
  const t=++ticket;
  controller?.abort();controller=new AbortController();clearResult();
  $('#risk-status').textContent='Reading saved observed river flow...';
  const f=new FormData($('#risk-form'));
  const q=new URLSearchParams({...selection,months:f.get('months'),period:`${f.get('first')},${f.get('last')}`,baseline:`${f.get('basefirst')},${f.get('baselast')}`,requirement:f.get('requirement')});
  try{
    const response=await fetch(`/api/risk?${q}`,{signal:controller.signal});
    const d=await response.json();
    if(!current(t))return;
    if(!response.ok||d.status!=='ready')throw Error([d.error||d.message,d.build_command].filter(Boolean).join(' '));
    await redraw(t,async()=>{
      purge();$('#risk-output').hidden=false;
      $('#risk-source').textContent=`${d.source} / gauge ${d.gauge}`;
      $('#risk-status').textContent='Drawing historical assessment...';
      await draw(d);
      if(!current(t))return;
      result=d;
      $('#risk-status').textContent=d.xyz_ready?'Historical assessment ready.':'Partial assessment: review coverage.';
    });
  }catch(e){showError(t,e);}
}
async function plot(id,data,title,extra={}){return Plotly.react($(id),data,{title:{text:title,font:{size:15}},paper_bgcolor:'#ffffff',plot_bgcolor:'#ffffff',font:{family:getComputedStyle(document.body).fontFamily,color:'#0a0a0a'},colorway:['#0a0a0a','#ff4f00','#1f6fe0','#00875a','#c9a100'],margin:{l:80,r:55,t:60,b:70},...extra},{responsive:true,displaylogo:false});}
function drawSurface(d){const s=surface(d);if(!s.z.flat().some(v=>v!==null)){$('#risk-surface').textContent='Not enough consecutive complete seasons and baseline coverage for a surface.';return;}const three=$('#risk-surface-mode').value==='3d';const titles={xaxis:{title:{text:'Window ending year'}},yaxis:{title:{text:'Window length (years)'}},zaxis:{title:{text:'Variation (% baseline)'}}};return plot('#risk-surface',[{type:three?'surface':'heatmap',x:s.years,y:s.windows,z:s.z,connectgaps:false,colorscale:'Viridis',colorbar:{title:{text:'Variation %'}},hovertemplate:'Ending year %{x}<br>Window %{y} years<br>Variation %{z:.2f}%<extra></extra>'}],'Historical seasonal-flow variability',three?{scene:titles}:{xaxis:titles.xaxis,yaxis:titles.yaxis});}
function space(d){const a=d.xyz;if(!d.xyz_ready){$('#risk-space').textContent='Three-indicator position unavailable; see coverage.';return;}const three=$('#risk-projection').value==='3d';const trace={type:three?'scatter3d':'scatter',mode:'markers',x:[a.quantity_pct_decade],y:[a.timing_days_decade],marker:{size:three?8:18,color:[a.variability_pct_baseline],colorscale:'Viridis',showscale:!three,colorbar:{title:{text:'Variation %'}}},text:[`Gauge ${esc(d.gauge)}; variation ${num(a.variability_pct_baseline)}%`],hovertemplate:'%{text}<br>Volume %{x:.2f}% / decade<br>Timing %{y:.2f} days / decade<extra></extra>'};if(three)trace.z=[a.variability_pct_baseline];const axes={xaxis:{title:{text:'Volume change (% baseline / decade)'},zeroline:true},yaxis:{title:{text:'Timing change (days / decade)'},zeroline:true},zaxis:{title:{text:'Year-to-year variation (% baseline)'}}};return plot('#risk-space',[trace],'Selected gauge: three independent indicators',three?{scene:axes}:{xaxis:axes.xaxis,yaxis:axes.yaxis});}
async function draw(d){const a=d.xyz;const cards=[['Water volume',a.quantity_pct_decade,'% of baseline per decade','Positive means more water in the selected season over time; negative means less.'],['Arrival timing',a.timing_days_decade,'days per decade','Negative means the annual halfway-volume date is moving earlier; positive means later. This is not seasonal onset.'],['Year-to-year variation',a.variability_pct_baseline,'% of baseline','How much seasonal volume differs between years (standard deviation). Higher means less consistent; this is not a percentage loss.']];$('#risk-cards').innerHTML=cards.map(([name,v,unit,text])=>`<div><small>${name}</small><b>${num(v)}</b><span>${unit}</span><span>${text}</span></div>`).join('');
const info=interpretation(d,$('#risk-role').value);$('#risk-verdict').dataset.level=String(info.trend.level);$('#risk-verdict').innerHTML=`<div>Historical flow pattern · prototype rules</div><h3>${info.trend.label}</h3><p>${esc(info.trend.reason)}</p><h3>${info.operation.label}</h3><p>${esc(info.operation.text)}</p><h4>${esc(ROLES[info.role]?.[0]||'Operation not selected')}</h4><p>${esc(info.context)}</p><p>${esc(info.action)}</p><p>Possible implications at this gauge, not a regional prediction. Site-specific water rights, usable supply, demand, storage and alternatives still require assessment. Changing occupation clears the previous threshold.</p>`;
const jobs=[drawSurface(d),space(d)];const years=d.annual.map(r=>r.year);
for(const [id,key,fitKey,title,unit,scale] of [['#risk-volume','volume_m3','volume','Water volume each season','Volume (hm³)',1e6],['#risk-timing','half_volume_day','timing','When half the annual water has passed','Day of hydrological year',1]]){const traces=[{x:years,y:d.annual.map(r=>r[key]==null?null:r[key]/scale),mode:'lines+markers',connectgaps:false,name:'Complete records'}];const f=d.fits[fitKey];if(f)traces.push({x:years,y:years.map(y=>(f.slope*y+f.intercept)/scale),name:'Sen trend',line:{dash:'dash'}});if(key==='volume_m3'&&d.baseline_volume_m3!=null)traces.push({x:years,y:years.map(()=>d.baseline_volume_m3/scale),name:'Fixed baseline'});jobs.push(plot(id,traces,title,{yaxis:{title:{text:unit}},xaxis:{title:{text:'Hydrological year'}}}));}
const h=d.hydrograph;jobs.push(plot('#risk-flow',[{x:h.dates,y:h.low,name:'10th percentile',line:{width:0}},{x:h.dates,y:h.high,name:'Baseline 10–90%',fill:'tonexty',line:{width:0}},{x:h.dates,y:h.median,name:'Baseline median'},{x:h.dates,y:h.flow,name:'Observed flow'},{x:h.dates,y:h.requirement,name:'Scenario threshold',line:{dash:'dash'}}].map(t=>({...t,connectgaps:false})),`River flow: hydrological year ${d.display_year}`,{yaxis:{title:{text:'Discharge (m³/s)'}}}));
$('#risk-coverage').textContent=`Analysis ${d.settings.period.join('–')}; baseline ${d.settings.baseline.join('–')}; ${d.common_years} common complete indicator years; ${d.baseline_years} complete baseline seasons. Baseline volume ${num(d.baseline_volume_m3)} m³. Hydrological year starts in month ${d.settings.hydro_year_start_month}. Surface uses all complete seasonal volumes, whereas XYZ uses complete full years. Raw variability includes long-term change. Small baselines can inflate relative values.`;$('#risk-warnings').innerHTML=d.warnings.map(w=>`<li>${esc(w)}</li>`).join('');$('#risk-events').hidden=!d.exposure;$('#risk-exposure-plot').hidden=!d.exposure;$('#risk-exposure').textContent='';
if(d.exposure){const e=d.exposure;$('#risk-exposure').textContent=`Below threshold: ${num(e.below_percent)}% of ${e.valid_days} valid days; ${e.missing_days} missing days. ${e.observed_segments} observed episode segments, ${e.complete_events} complete episodes. Longest observed segment ${e.longest_observed_segment_days} days; median complete duration ${num(e.median_complete_duration_days)} days. Deficit ${num(e.deficit_m3)} m³; above-threshold volume ${num(e.above_requirement_m3)} m³ (not flood risk).`;jobs.push(plot('#risk-exposure-plot',[{type:'bar',x:d.annual_exposure.map(r=>r.year),y:d.annual_exposure.map(r=>r.below_percent)}],'Days below threshold by year',{yaxis:{title:{text:'% of valid selected-season days'}}}));$('#risk-event-table').innerHTML='<table><tr><th>Start</th><th>End</th><th>Days</th><th>Deficit m³</th><th>Censored</th></tr>'+e.events.map(r=>`<tr><td>${esc(r.start)}</td><td>${esc(r.end)}</td><td>${r.days}</td><td>${num(r.deficit_m3)}</td><td>${r.censored?'Yes':'No'}</td></tr>`).join('')+'</table>';}
const settled=await Promise.allSettled(jobs);
const failed=settled.find(item=>item.status==='rejected');
if(failed)throw failed.reason;
}
$('#risk-export').onclick=()=>{if(!result)return;const body={...result,screening:interpretation(result,$('#risk-role').value),variability_surface:surface(result)};const u=URL.createObjectURL(new Blob([JSON.stringify(body,null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=u;a.download='rivascope-risk-assessment.json';a.click();setTimeout(()=>URL.revokeObjectURL(u),1000);};
