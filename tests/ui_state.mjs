// DOM-state regression checks with explicit test-only API fixtures; no browser control.
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import vm from 'node:vm';
import {pathToFileURL} from 'node:url';
const root=process.cwd();
const jsdomPath=process.env.ROOFTRACE_JSDOM_PATH || path.join(root,'private/ui-tests/node_modules/jsdom/lib/api.js');
const {JSDOM}=await import(pathToFileURL(jsdomPath));
const dom=new JSDOM(await fs.readFile('static/index.html','utf8'),{url:'http://localhost/',runScripts:'outside-only'});
const window=dom.window, document=window.document, context=dom.getInternalVMContext();
const tick=()=>new Promise(resolve=>setTimeout(resolve,20));
const region={id:1,class_name:'building_region',x_min:10,y_min:10,x_max:50,y_max:50,area_pixels:1600,mean_probability:.9};
let activeCount=2, regionDelay=null;
const downloadBlobs=new Map(), downloads=[];
window.Blob=Blob;
window.URL.createObjectURL=blob=>{const id=`blob:test-${downloadBlobs.size}`;downloadBlobs.set(id,blob);return id;};
window.URL.revokeObjectURL=()=>{};
window.HTMLAnchorElement.prototype.click=function(){if(this.download)downloads.push({name:this.download,blob:downloadBlobs.get(this.href)});};
window.HTMLCanvasElement.prototype.getContext=()=>({fillRect(){},drawImage(){},strokeRect(){},clearRect(){},beginPath(){},arc(){},fill(){},moveTo(){},lineTo(){},closePath(){},stroke(){},fillText(){},measureText(t){return {width:t.length*6};}});
window.Image=class{naturalWidth=512;naturalHeight=512;async decode(){}};
const roofs=()=>Array.from({length:activeCount},(_,i)=>({...region,id:i+1}));
const json=value=>Promise.resolve(new Response(JSON.stringify(value),{status:200,headers:{'Content-Type':'application/json'}}));
window.fetch=async(url,options={})=>{
  if(url==='/api/samples')return json([{id:'fixture',title:'Test-only image',image:'/fixture.png',source:'Test fixture',license:'test',ground_pixel_size_m:.3,center_lon_lat:[77,13]}]);
  if(url==='/api/analyze')return json({image_id:'fixture',width:512,height:512,model:'test-fixture',threshold:.5,count:activeCount,regions:roofs(),probability_png:'test-only',inference_seconds:.1,tiles:1});
  if(url==='/api/regions'){if(regionDelay)await regionDelay;activeCount=3;const {threshold}=JSON.parse(options.body);return json({count:3,regions:roofs(),threshold});}
  if(url==='/api/solar'){
    const {threshold,settings}=JSON.parse(options.body);
    return json({threshold,settings,roofs:roofs().map(r=>({...r,excluded:false,footprint_m2:144,panel_count:10,capacity_kwp:4.5,annual_kwh:6000,monthly_kwh:Array(12).fill(500),panels:[]})),roof_count:activeCount,included_roof_count:activeCount,panel_count:activeCount*10,capacity_kwp:activeCount*4.5,annual_kwh:activeCount*6000,monthly_kwh:Array(12).fill(activeCount*500),months:['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'],weather:{provider:'Test fixture only',database:'test',years:[2005,2023],annual_kwh_per_kwp:1400,url:'https://example.invalid/fixture'}});
  }
  throw new Error(`Unexpected request ${url}`);
};
const modules=new Map();
async function load(filename){
  if(modules.has(filename))return modules.get(filename);
  const mod=new vm.SourceTextModule(await fs.readFile(filename,'utf8'),{context,identifier:filename});modules.set(filename,mod);
  await mod.link(spec=>load(path.resolve(path.dirname(filename),spec)));return mod;
}
try{
  await (await load(path.resolve('static/app.js'))).evaluate();await tick();
  assert.equal(document.getElementById('analyze').disabled,false);
  document.getElementById('analyze').click();await tick();
  assert.equal(document.getElementById('count').textContent,'2');
  document.getElementById('solar-form').dispatchEvent(new window.Event('submit',{cancelable:true}));await tick();
  assert.equal(document.getElementById('solar-output').hidden,false);
  assert.match(document.getElementById('solar-total-energy').textContent,/12,000/);
  document.getElementById('solar-download-csv').click();await tick();
  const csv=await downloads.at(-1).blob.text();assert.match(csv,/annual_ac_kwh/);assert.equal(csv.trim().split('\r\n').length,3);
  assert.match(csv,/'?"0.5"/);
  let release;regionDelay=new Promise(resolve=>{release=resolve;});
  const slider=document.getElementById('threshold');slider.value='.7';slider.dispatchEvent(new window.Event('input'));
  assert.equal(document.getElementById('solar-output').hidden,true);
  assert.equal(document.getElementById('solar-download-csv').disabled,true);
  assert.equal(document.getElementById('download-csv').disabled,true);
  await new Promise(resolve=>setTimeout(resolve,250));release();await tick();
  assert.equal(document.getElementById('count').textContent,'3');
  assert.equal(document.getElementById('active-threshold').textContent,'Active threshold: 0.70');
  document.getElementById('solar-form').dispatchEvent(new window.Event('submit',{cancelable:true}));await tick();
  assert.equal(document.getElementById('solar-output').hidden,false);
  document.getElementById('solar-scale').value='.4';document.getElementById('solar-scale').dispatchEvent(new window.Event('input'));
  assert.equal(document.getElementById('solar-output').hidden,true);
  document.getElementById('reset').click();
  assert.equal(document.getElementById('results').hidden,true);
  assert.equal(document.getElementById('solar-download-csv').disabled,true);
  assert.equal(document.getElementById('analyze').disabled,true);
  console.log('DOM state checks passed: analysis, solar result, CSV, threshold invalidation, settings invalidation, reset. Visual browser layout not tested.');
}finally{window.close();}
