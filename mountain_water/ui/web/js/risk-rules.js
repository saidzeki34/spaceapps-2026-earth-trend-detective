// Prototype screening rules, not calibrated probabilities or operating limits.
export const RULES = {version:'screening-v1', change:{volume:5,timing:3,variation:15}, strong:{volume:10,timing:7,variation:30}};
export const ROLES = {
 hydropower:['Hydropower','If generation depends on this river, compare seasonal flow with turbine flow needs, head, storage and release rules.',['Check minimum operating flows even when the long-term pattern looks steady.','Review seasonal generation scheduling and reservoir flexibility.','Stress-test dry-year generation and backup electricity arrangements.']],
 data_center:['Data center infrastructure','If cooling uses this river directly or through a connected utility, check cooling design, peak demand, water temperature and supply agreements.',['Confirm peak cooling demand and alternative water supplies; steady flow is not a cooling guarantee.','Review whether cooling demand overlaps with low-flow months and assess water-saving options.','Stress-test cooling continuity and alternative supplies during prolonged low flow.']],
 power_plant:['Power plant','For water-dependent thermal generation, check cooling-water intake needs, water temperature and discharge-permit limits.',['Check cooling and permit constraints even with a steady historical flow pattern.','Review seasonal cooling constraints and operating flexibility.','Stress-test cooling-water availability and potential output constraints in dry periods.']],
 government:['Government official','Use this gauge as one input to allocation and service-continuity planning; it does not represent the whole region.',['Maintain monitoring and check local demand against available supply.','Review seasonal allocation, competing demands and vulnerable users.','Prioritize drought-contingency exercises and assessment of alternative supplies.']],
 defence:['Defence','For facilities dependent on this source, assess potable-water demand, treatment, storage and alternative supply routes.',['Verify water-quality treatment and continuity arrangements.','Review seasonal resupply needs and storage operating plans.','Stress-test essential water services and backup supply arrangements.']]
};
const finite = x => typeof x === 'number' && Number.isFinite(x);
export function classify(d) {
 const a=d.xyz || {}, x=a.quantity_pct_decade,y=a.timing_days_decade,z=a.variability_pct_baseline;
 if (!d.xyz_ready || ![x,y,z].every(finite)) return {level:null,label:'Insufficient evidence',reason:'A complete three-parameter assessment is unavailable.'};
 const s=RULES.strong,c=RULES.change;
 const level=Math.abs(x)>=s.volume || Math.abs(y)>=s.timing || z>=s.variation ? 2 : Math.abs(x)>=c.volume || Math.abs(y)>=c.timing || z>=c.variation ? 1 : 0;
 const reasons=[];
 if(Math.abs(x)>=c.volume) reasons.push('water volume is shifting');
 if(Math.abs(y)>=c.timing) reasons.push('delivery timing is shifting');
 if(z>=c.variation) reasons.push('year-to-year variation exceeds the screening threshold');
 return {level,label:['Relatively stable','Changing','Strong change or high variability'][level],reason:reasons.length?reasons.join('; ')+'.':'All three indicators are below the prototype screening thresholds.'};
}
export function verdict(d) {
 const e=d.exposure;
 if(!e || !finite(e.below_percent) || !e.valid_days) return {label:'Operational risk not determined',text:'Enter a documented river-flow threshold or a clearly labelled scenario. The three indicators alone cannot establish operational feasibility.'};
 const coverage=e.valid_days/(e.valid_days+e.missing_days);
 if(e.below_days>0) return {label:'Potential water-supply constraint',text:`Flow was below the scenario threshold on ${e.below_percent.toFixed(1)}% of valid selected-season days. This flags historical threshold exposure, not proven service failure.${coverage<.9?' Less than 90% of selected-season days are available; exposure may be understated.':''}`};
 if(!finite(coverage) || coverage<.9) return {label:'Operational risk not determined',text:'No shortfall was found in available days, but coverage is below 90%. Missing days cannot establish reliable supply.'};
 return {label:'No historical threshold shortfall detected',text:'This threshold was met on available selected-season days. This is not a safe-to-operate approval or a guarantee of future supply.'};
}
export function surface(d) {
 const rows=d.annual || [], b=d.baseline_volume_m3;
 const years=rows.map(r=>r.year).sort((a,b)=>a-b), windows=[5,6,7,8,9,10,11,12,13,14,15];
 const values=new Map(rows.map(r=>[r.year,r.volume_m3]));
 const z=windows.map(w=>years.map(y=>{
   if(!finite(b)||b<=0)return null;
   const v=Array.from({length:w},(_,i)=>values.get(y-i));
   if(!v.every(finite))return null;
   const mean=v.reduce((a,b)=>a+b,0)/w;
   return 100*Math.sqrt(v.reduce((s,x)=>s+(x-mean)**2,0)/(w-1))/b;
 }));
 return {years,windows,z};
}
export function interpretation(d,role) {
 const trend=classify(d),operation=verdict(d),profile=ROLES[role];
 return {rules:RULES,role:profile?role:null,trend,operation,context:profile?profile[1]:'Select an operation to see relevant planning checks.',action:profile?trend.level===null?'Resolve coverage gaps before interpreting the historical trend.':profile[2][trend.level]:''};
}
