import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
// Browser modules have .js filenames without a Node package. Load this standalone
// module explicitly as ESM, including on Node 18 without experimental type flags.
const source=await readFile(new URL('../../mountain_water/ui/web/js/risk-rules.js',import.meta.url));
const {classify,verdict,surface,interpretation,ROLES,selectionFromHash}=await import(`data:text/javascript;base64,${source.toString('base64')}`);
const d=(x,y,z)=>({xyz_ready:true,xyz:{quantity_pct_decade:x,timing_days_decade:y,variability_pct_baseline:z}});
assert.equal(classify(d(2.24,-1.85,18.87)).level,1);
assert.equal(classify(d(0,0,0)).level,0);
assert.equal(classify(d(5,0,0)).level,1);
assert.equal(classify(d(-10,0,0)).level,2);
assert.equal(classify(d(0,7,0)).level,2);
assert.equal(classify(d(0,0,30)).level,2);
assert.equal(classify(d(null,0,0)).level,null);
assert.equal(classify({...d(0,0,0),xyz_ready:false}).level,null);
assert.equal(verdict(d(0,0,0)).label,'Operational risk not determined');
const e={valid_days:100,missing_days:0,below_percent:0,below_days:0};
assert.match(verdict({exposure:e}).label,/No historical/);
assert.match(verdict({exposure:{...e,missing_days:100}}).label,/not determined/);
assert.match(verdict({exposure:{...e,below_days:1,below_percent:1}}).label,/Potential/);
const annual=Array.from({length:16},(_,i)=>({year:2000+i,volume_m3:100}));
assert.equal(surface({annual,baseline_volume_m3:100}).z[0][4],0);
assert.equal(surface({annual,baseline_volume_m3:100}).z[0][3],null);
annual[4].volume_m3=null;
assert.equal(surface({annual,baseline_volume_m3:100}).z[0][5],null);
assert.equal(surface({annual,baseline_volume_m3:0}).z[0][15],null);
for(const role of Object.keys(ROLES)){for(const v of [d(0,0,0),d(5,0,0),d(10,0,0)])assert.ok(interpretation(v,role).action);}
assert.deepEqual(selectionFromHash('#c=NO&d=no&r=2.13.0'),{dataset:'no',gauge:'2.13.0'});
assert.deepEqual(selectionFromHash('#c=CH&d=ch_gldas&r=2268'),{dataset:'ch_gldas',gauge:'2268'});
assert.deepEqual(selectionFromHash('#c=NO&d=no_gldas&r=2.13.0'),{dataset:'no_gldas',gauge:'2.13.0'});
assert.deepEqual(selectionFromHash('#c=CH&d=stations&r=2268'),{dataset:'stations',gauge:'2268'});
assert.deepEqual(selectionFromHash('#dataset=no&gauge=2.13.0'),{dataset:'no',gauge:'2.13.0'});
assert.deepEqual(selectionFromHash(''),{dataset:'',gauge:''});
console.log('Screening boundary, missingness, role and surface assertions passed.');
