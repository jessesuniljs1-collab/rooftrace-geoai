const $ = (id) => document.getElementById(id);
const presets = {bengaluru:[12.9716,77.5946],chennai:[13.0827,80.2707],delhi:[28.6139,77.2090],mumbai:[19.0760,72.8777]};
const fields = ['scale','latitude','longitude','watts','length','width','setback','gap','coverage','tilt','azimuth','loss','shade'];
const fmt = (n, digits=1) => Number(n).toLocaleString('en-IN', {maximumFractionDigits:digits});

export function createSolarController({getSource,getResult,redraw,download,canvas}) {
  let result = null, version = 0, controller = null, selected = 'all', excluded = new Set(), calibration = null;
  function message(text) { $('solar-status').textContent=text; }
  function hideResult() {
    result=null; $('roof-popover').hidden=true; $('solar-output').hidden=true; $('solar-download-csv').disabled=true; $('solar-download-report').disabled=true;
  }
  function invalidate(text='Settings changed. Recalculate to update the panel layout and energy estimates.') {
    version++; controller?.abort(); hideResult(); $('solar-error').hidden=true; message(text); redraw();
    $('solar-calculate').disabled=false;
  }
  function mapLink() {
    const lat=Number($('solar-latitude').value), lon=Number($('solar-longitude').value);
    const valid=$('solar-latitude').value!=='' && $('solar-longitude').value!=='' && lat>=-60 && lat<=70 && lon>=-180 && lon<=180;
    $('google-satellite-link').hidden=!valid;
    if(valid) $('google-satellite-link').href=`https://www.google.com/maps/@?api=1&map_action=map&center=${lat},${lon}&zoom=20&basemap=satellite`;
  }
  function sourceChanged(sample) {
    invalidate('Analyze the image, then confirm its scale and solar scenario below.');
    excluded=new Set(); selected='all'; calibration=null;
    $('solar-calibration-note').hidden=true;
    $('solar-location').value='source'; $('solar-settings').open=!sample;
    $('solar-scale').value=sample?.ground_pixel_size_m || sample?.requested_ground_pixel_size_m || '';
    let coordinates=sample?.center_lon_lat;
    if(!coordinates && sample?.split==='test') {
      coordinates=[172.6362,-43.5321];
      $('solar-location-note').textContent='WHU imagery: approximate Christchurch-area climate scenario. Exact tile coordinates are unavailable; this is not a site-specific solar assessment.';
    } else if(coordinates) {
      $('solar-location-note').textContent='Sample center from source metadata; native image detail can be coarser than the requested sampling.';
    } else $('solar-location-note').textContent='For uploads, enter the real image scale and location. RoofTrace cannot recover metres or coordinates from an ordinary JPG/PNG.';
    $('solar-longitude').value=coordinates ? Number(coordinates[0]).toFixed(6) : '';
    $('solar-latitude').value=coordinates ? Number(coordinates[1]).toFixed(6) : '';
    $('solar-azimuth').value=coordinates && coordinates[1]<0 ? '0' : '180';
    mapLink();
  }
  function settings() {
    const number=(id)=>Number($(`solar-${id}`).value);
    return {meters_per_pixel:number('scale'),latitude:number('latitude'),longitude:number('longitude'),
      panel_watts:number('watts'),panel_length_m:number('length'),panel_width_m:number('width'),setback_m:number('setback'),
      panel_gap_m:number('gap'),usable_fraction:number('coverage')/100,tilt_degrees:number('tilt'),azimuth_degrees:number('azimuth'),
      system_loss_percent:number('loss'),additional_shade_percent:number('shade'),excluded_region_ids:[...excluded]};
  }
  function drawChart(values) {
    $('solar-chart').replaceChildren(); const max=Math.max(...values,1);
    values.forEach((value,i)=>{
      const col=document.createElement('div'); col.className='solar-bar-column';
      const amount=document.createElement('span'); amount.textContent=fmt(value,0);
      const bar=document.createElement('div'); bar.className='solar-bar'; bar.style.height=`${Math.max(1,value/max*100)}px`;
      const month=document.createElement('span'); month.textContent=result.months[i];
      col.append(amount,bar,month); col.title=`${result.months[i]}: ${fmt(value)} kWh`; $('solar-chart').append(col);
    });
    $('solar-chart').setAttribute('aria-label',values.map((v,i)=>`${result.months[i]} ${fmt(v)} kilowatt-hours`).join(', '));
  }
  function inspect() {
    if(!result) return;
    const roof=result.roofs.find((r)=>String(r.id)===selected);
    const data=roof || result;
    $('solar-exclude').disabled=!roof; $('solar-exclude').checked=roof?.excluded || false;
    $('solar-roof-summary').replaceChildren();
    for(const text of roof ? [`Region ${roof.id}`,`${fmt(roof.footprint_m2)} m² projected footprint`,`${roof.panel_count} panels · ${fmt(roof.capacity_kwp,2)} kWp`,`${fmt(roof.annual_kwh,0)} kWh / year${roof.excluded?' · excluded':''}`] : ['All roof regions',`${result.included_roof_count} included of ${result.roof_count}`,`${result.panel_count} panels · ${fmt(result.capacity_kwp,2)} kWp`,`${fmt(result.annual_kwh,0)} kWh / year`]) {
      const span=document.createElement('span'); span.textContent=text; $('solar-roof-summary').append(span);
    }
    $('solar-chart-title').textContent=roof ? `Region ${roof.id} · estimated monthly AC energy` : 'All regions · estimated monthly AC energy';
    drawChart(data.monthly_kwh);
    $('roof-popover').replaceChildren(); $('roof-popover').hidden=!roof;
    if(roof) { for(const text of [`Roof region ${roof.id}`,`${fmt(roof.footprint_m2)} m² · ${roof.panel_count} panels`,`${fmt(roof.capacity_kwp,2)} kWp capacity`,`${fmt(roof.annual_kwh,0)} kWh / year`]) {const line=document.createElement('div');line.textContent=text;$('roof-popover').append(line);} }
    redraw();
  }
  function render() {
    $('solar-output').hidden=false;
    $('solar-total-panels').textContent=fmt(result.panel_count,0);
    $('solar-total-capacity').textContent=`${fmt(result.capacity_kwp,2)} kWp`;
    $('solar-total-energy').textContent=`${fmt(result.annual_kwh,0)} kWh`;
    $('solar-roof').replaceChildren();
    const all=document.createElement('option'); all.value='all'; all.textContent='All regions'; $('solar-roof').append(all);
    for(const roof of [...result.roofs].sort((a,b)=>b.annual_kwh-a.annual_kwh)) {
      const option=document.createElement('option'); option.value=roof.id;
      option.textContent=`Region ${roof.id} · ${fmt(roof.annual_kwh,0)} kWh/year${roof.excluded?' · excluded':''}`; $('solar-roof').append(option);
    }
    if(!result.roofs.some((r)=>String(r.id)===selected)) selected='all';
    $('solar-roof').value=selected;
    $('solar-weather-credit').replaceChildren();
    if(result.weather) {
      const weather=result.weather; const a=document.createElement('a'); a.href=weather.url; a.target='_blank'; a.rel='noreferrer';
      a.textContent=`${weather.provider} / ${weather.database}, ${weather.years[0]}–${weather.years[1]}`;
      $('solar-weather-credit').append(a,document.createTextNode(`. Regional yield: ${fmt(weather.annual_kwh_per_kwp,0)} kWh/kWp/year. Scenario coordinates rounded to 0.01°. Local shade is not measured.`));
    } else $('solar-weather-credit').textContent='No panels fit at these settings. No climate request was needed.';
    $('solar-download-csv').disabled=false; $('solar-download-report').disabled=false;
    inspect();
  }
  async function calculate(event) {
    event?.preventDefault();
    const detection=getResult(); if(!detection) return;
    if(!$('solar-form').checkValidity()) { $('solar-settings').open=true; $('solar-form').reportValidity(); return; }
    version++; const requestVersion=version;
    controller?.abort(); controller=new AbortController(); hideResult(); redraw();
    $('solar-error').hidden=true; $('solar-calculate').disabled=true;
    message('Fitting panel scenarios and retrieving free PVGIS regional solar yield…');
    const timeout=setTimeout(()=>controller?.abort(),60000);
    try {
      const response=await fetch('/api/solar',{method:'POST',headers:{'Content-Type':'application/json'},signal:controller.signal,
        body:JSON.stringify({probability_png:detection.probability_png,threshold:detection.threshold,settings:settings()})});
      let body; try{body=await response.json();}catch{throw new Error('Unexpected server response. Please retry.');}
      if(!response.ok) throw new Error(typeof body.detail==='string'?body.detail:'Check the solar settings and try again.');
      if(requestVersion!==version) return;
      result={...body,image_id:detection.image_id,model_id:detection.model,image_width:detection.width,image_height:detection.height,calculated_at:new Date().toISOString()};
      render(); message('Solar scenario ready. Select a roof region or click its box on the image. Downloads use these exact settings.');
    }catch(error){
      if(requestVersion!==version)return;
      $('solar-error').textContent=error.name==='AbortError'?'Solar calculation timed out. Retry in a moment.':error.message; $('solar-error').hidden=false;
      message('No current solar estimate. Roof detection results remain available.');
    }finally{clearTimeout(timeout);if(requestVersion===version)$('solar-calculate').disabled=false;}
  }
  function overlay(context) {
    if(calibration?.points.length) {
      context.fillStyle='#ffce67'; for(const [x,y] of calibration.points){context.beginPath();context.arc(x,y,5,0,Math.PI*2);context.fill();}
    }
    if(!result)return;
    for(const roof of result.roofs){
      if(roof.excluded) continue;
      const highlight=selected==='all'||String(roof.id)===selected;
      if($('solar-show-panels').checked && highlight) {
        for(const points of roof.panels){context.beginPath();points.forEach(([x,y],i)=>i?context.lineTo(x,y):context.moveTo(x,y));context.closePath();context.fillStyle='#26788ac7';context.fill();context.lineWidth=.7;context.strokeStyle='#bee8ed';context.stroke();}
      }
      if(String(roof.id)===selected){context.strokeStyle='#ffce67';context.lineWidth=3;context.strokeRect(roof.x_min,roof.y_min,roof.x_max-roof.x_min,roof.y_max-roof.y_min);}
    }
  }
  canvas.addEventListener('click',(event)=>{
    const source=getSource();if(!source)return;
    const box=canvas.getBoundingClientRect();const x=(event.clientX-box.left)*canvas.width/box.width,y=(event.clientY-box.top)*canvas.height/box.height;
    if(calibration){
      calibration.points.push([x,y]);redraw();
      if(calibration.points.length===2){
        const [[ax,ay],[bx,by]]=calibration.points;const distance=Number(window.prompt('Real-world distance between these two points, in metres:'));
        const scale=distance/Math.hypot(bx-ax,by-ay);calibration=null;$('solar-calibration-note').hidden=true;
        if(distance>0&&scale>=.05&&scale<=5){$('solar-scale').value=scale.toFixed(4);invalidate('Scale calibrated. Confirm the location, then calculate solar potential.');}
        else{message('Calibration cancelled or out of supported range (0.05–5 m/pixel).');redraw();}
      }else message('Click the second end of the measured feature.');
      return;
    }
    const selectable=result?.roofs || getResult()?.regions || [];
    const hit=selectable.filter((r)=>x>=r.x_min&&x<r.x_max&&y>=r.y_min&&y<r.y_max).sort((a,b)=>a.area_pixels-b.area_pixels)[0];
    if(hit){selected=String(hit.id);if(result){$('solar-roof').value=selected;inspect();}else{message('Calculating selected roof…');calculate();}}
  });
  $('solar-form').addEventListener('submit',calculate);
  $('solar-recalculate').addEventListener('click',calculate);
  for(const field of fields) $(`solar-${field}`).addEventListener('input',()=>{invalidate();mapLink();});
  $('solar-location').addEventListener('change',()=>{
    const preset=$('solar-location').value;
    if(preset==='source'){sourceChanged(getSource()?.sample);return;}
    if(presets[preset]){[$('solar-latitude').value,$('solar-longitude').value]=presets[preset];$('solar-azimuth').value='180';}
    $('solar-location-note').textContent='Location is a user-selected solar scenario. Verify it matches your imagery; changing the city does not move the image.';
    invalidate();mapLink();
  });
  $('solar-roof').addEventListener('change',()=>{selected=$('solar-roof').value;inspect();});
  $('solar-exclude').addEventListener('change',()=>{if(selected==='all')return;if($('solar-exclude').checked)excluded.add(Number(selected));else excluded.delete(Number(selected));calculate();});
  $('solar-show-panels').addEventListener('change',redraw);
  $('solar-calibrate').addEventListener('click',()=>{invalidate('Click the first end of a known, measured distance on the image.');calibration={points:[]};$('solar-calibration-note').hidden=false;});
  function reportCSV(){
    if(!result)return;
    const s=result.settings;
    const rows=[['image_id','region_id','excluded','footprint_m2','panel_count','capacity_kwp','annual_ac_kwh','probability_threshold','meters_per_pixel','latitude','longitude','module_watts','module_length_m','module_width_m','edge_setback_m','max_roof_fraction','tilt_degrees','azimuth_degrees','system_loss_percent','extra_shade_percent','yield_provider','yield_database','yield_years','model_id',...result.months.map((m)=>`${m}_ac_kwh`)]];
    for(const roof of result.roofs)rows.push([result.image_id,roof.id,roof.excluded,roof.footprint_m2,roof.panel_count,roof.capacity_kwp,roof.annual_kwh,result.threshold,s.meters_per_pixel,s.latitude,s.longitude,s.panel_watts,s.panel_length_m,s.panel_width_m,s.setback_m,s.usable_fraction,s.tilt_degrees,s.azimuth_degrees,s.system_loss_percent,s.additional_shade_percent,result.weather?.provider||'',result.weather?.database||'',result.weather?.years?.join('-')||'',result.model_id,...roof.monthly_kwh]);
    const csv=rows.map((row)=>row.map((v)=>`"${String(v).replaceAll('"','""')}"`).join(',')).join('\r\n')+'\r\n';
    download(new Blob([csv],{type:'text/csv;charset=utf-8'}),`rooftrace-solar-${result.image_id}-p${Number(result.threshold).toFixed(2)}.csv`);
  }
  $('solar-download-csv').addEventListener('click',reportCSV);
  $('solar-download-report').addEventListener('click',()=>{if(result)download(new Blob([JSON.stringify(result,null,2)],{type:'application/json'}),`rooftrace-solar-${result.image_id}.json`);});
  return {sourceChanged,overlay,calculate,clear:()=>{invalidate('Analyze an image to begin a new solar scenario.');excluded=new Set();calibration=null;},
    detectionsChanged:()=>{invalidate('Roof detections changed. Recalculate solar potential with the active probability threshold.');excluded=new Set();}};
}
