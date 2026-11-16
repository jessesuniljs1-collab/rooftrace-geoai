import {createSolarController} from './solar.js';

const $ = (id) => document.getElementById(id);
const state = { source: null, result: null, view: 'original', epoch: 0, filtering: 0, busy: false, pending: false, url: null, controller: null, timer: null };
const canvas = $('image-canvas');
const ctx = canvas.getContext('2d');
let samples = [];
let filterTimer;
let solarController;

function error(message = '') { $('error').textContent = message; $('error').hidden = !message; }
function status(message) { $('message').textContent = message; }
function controls() {
  $('analyze').disabled = !state.source || state.busy;
  $('upload').disabled = state.busy;
  document.querySelectorAll('.sample').forEach((button) => { button.disabled = state.busy; });
  $('threshold').disabled = state.busy;
}
function downloads(disabled) { $('download-png').disabled = disabled; $('download-csv').disabled = disabled; }
function clearResult() {
  solarController?.clear();
  state.result = null;
  state.view = 'original';
  $('results').hidden = true;
  $('view-annotated').disabled = true;
  $('view-original').setAttribute('aria-pressed', 'true');
  $('view-annotated').setAttribute('aria-pressed', 'false');
  $('viewer-badge').hidden = true;
  $('run-meta').textContent = 'RGB imagery · original pixel coordinates';
  downloads(true);
}
function stopWork() {
  state.controller?.abort();
  clearInterval(state.timer);
  clearTimeout(filterTimer);
  state.epoch++;
  state.filtering++;
  state.busy = false;
  state.pending = false;
  $('loading').hidden = true;
  $('viewer').setAttribute('aria-busy', 'false');
}
function renderImage(target = canvas, annotated = state.view === 'annotated') {
  if (!state.source) return;
  target.width = state.source.image.naturalWidth;
  target.height = state.source.image.naturalHeight;
  const context = target.getContext('2d');
  context.fillStyle = '#ffffff';
  context.fillRect(0, 0, target.width, target.height);
  context.drawImage(state.source.image, 0, 0);
  if (annotated && state.result) {
    context.lineWidth = Math.max(1.5, target.width / 380);
    context.font = `600 ${Math.max(9, Math.round(target.width / 65))}px Arial`;
    for (const r of state.result.regions) {
      const w = r.x_max - r.x_min, h = r.y_max - r.y_min;
      context.fillStyle = '#a5ee6026';
      context.fillRect(r.x_min, r.y_min, w, h);
      context.strokeStyle = '#c4ff73';
      // Half-open bounds are drawn inside the last included pixel.
      context.strokeRect(r.x_min + .5, r.y_min + .5, Math.max(0, w - 1), Math.max(0, h - 1));
      if ($('show-ids').checked) {
        const text = String(r.id), tw = context.measureText(text).width + 6;
        const y = Math.max(0, r.y_min - 13);
        const x = Math.min(r.x_min, target.width - tw);
        context.fillStyle = '#143d33'; context.fillRect(x, y, tw, 13);
        context.fillStyle = '#ecffd3'; context.fillText(text, x + 3, y + 10);
      }
    }
    solarController?.overlay(context);
  }
}
function renderResults() {
  const r = state.result;
  if (!r) return;
  $('results').hidden = false;
  $('count').textContent = r.count;
  $('threshold-value').textContent = Number(r.threshold).toFixed(2);
  $('active-threshold').textContent = `Active threshold: ${Number(r.threshold).toFixed(2)}`;
  $('viewer-badge').textContent = `${r.count} regions · p ≥ ${Number(r.threshold).toFixed(2)}`;
  $('viewer-badge').hidden = state.view !== 'annotated';
  $('image-canvas').setAttribute('aria-label', `${state.source.title}, ${state.view} view${state.view === 'annotated' ? ` with ${r.count} building regions at probability threshold ${Number(r.threshold).toFixed(2)}` : ''}`);
  $('table-count').textContent = `${r.count} regions`;
  $('region-table').replaceChildren();
  for (const region of r.regions.slice(0, 100)) {
    const row = document.createElement('tr');
    for (const value of [region.id, `${region.x_min}, ${region.y_min}, ${region.x_max}, ${region.y_max}`, region.area_pixels, `${(region.mean_probability * 100).toFixed(1)}%`]) {
      const td = document.createElement('td'); td.textContent = value; row.append(td);
    }
    $('region-table').append(row);
  }
  if (!r.count) {
    const row = document.createElement('tr'); const cell = document.createElement('td'); cell.colSpan = 4;
    cell.textContent = 'No building regions at this threshold. This does not establish that no buildings are present.';
    row.append(cell); $('region-table').append(row);
  }
  renderImage();
  downloads(state.pending);
}
async function loadImage(url) {
  const image = new Image();
  image.src = url;
  await image.decode();
  const { naturalWidth: w, naturalHeight: h } = image;
  if (Math.min(w, h) < 64 || Math.max(w, h) > 1024 || w * h > 1048576) throw new Error('Use 64–1024 pixels on each side, up to 1,048,576 pixels. Crop larger scenes before uploading.');
  return image;
}
async function selectSource(sample, file) {
  stopWork();
  const epoch = state.epoch;
  error(); clearResult(); state.source = null; controls();
  if (state.url) { URL.revokeObjectURL(state.url); state.url = null; }
  try {
    if (file && file.size > 3500000) throw new Error('This file exceeds 3.5 MB. Please choose a smaller JPG or PNG.');
    if (file && !/\.(jpe?g|png)$/i.test(file.name)) throw new Error('Please choose a JPG or PNG image.');
    const url = sample ? sample.image : URL.createObjectURL(file);
    if (file) state.url = url;
    const image = await loadImage(url);
    if (state.epoch !== epoch) return;
    state.source = { image, file, sample, title: sample?.title || 'Uploaded image' };
    solarController?.sourceChanged(sample);
    $('empty-view').hidden = true; canvas.hidden = false;
    $('image-title').textContent = state.source.title;
    $('dimensions').textContent = `${image.naturalWidth} × ${image.naturalHeight} px · RGB`;
    $('source-credit').textContent = sample ? `${sample.source}. ${sample.license}.` : 'Your uploaded image. You are responsible for permission to use it.';
    document.querySelectorAll('.sample').forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.id === sample?.id)));
    renderImage();
    status('Image ready. Select “Analyze image” to run fresh building segmentation.');
  } catch (e) {
    if (state.epoch !== epoch) return;
    error(e.message || 'The image could not be opened. Try a valid JPG or PNG.');
    status('No image loaded. Choose a valid JPG or PNG to continue.');
    canvas.hidden = true; $('empty-view').hidden = false;
    $('dimensions').textContent = 'No image selected'; $('image-title').textContent = 'Image workspace';
    $('source-credit').textContent = '';
    document.querySelectorAll('.sample').forEach((b) => b.setAttribute('aria-pressed', 'false'));
  }
  controls();
}
async function readResponse(response) {
  let body;
  try { body = await response.json(); } catch { throw new Error('The server returned an unexpected response. Please retry in a moment.'); }
  if (!response.ok) throw new Error(typeof body.detail === 'string' ? body.detail : `The request could not finish (${response.status}). Please check the image and try again.`);
  return body;
}
async function analyze() {
  if (!state.source || state.busy) return;
  stopWork(); clearResult(); error();
  const epoch = state.epoch;
  state.busy = true; controls();
  $('loading').hidden = false; $('viewer').setAttribute('aria-busy', 'true');
  status('Running the building model. Please keep this page open.');
  const start = performance.now();
  state.timer = setInterval(() => { $('elapsed').textContent = `${Math.floor((performance.now() - start) / 1000)} seconds elapsed`; }, 1000);
  state.controller = new AbortController();
  const timeout = setTimeout(() => state.controller?.abort(), 180000);
  const form = new FormData();
  if (state.source.sample) form.append('sample_id', state.source.sample.id);
  else form.append('file', state.source.file);
  form.append('threshold', $('threshold').value);
  try {
    const response = await fetch('/api/analyze', { method: 'POST', body: form, signal: state.controller.signal });
    const result = await readResponse(response);
    if (state.epoch !== epoch) return;
    if (result.width !== state.source.image.naturalWidth || result.height !== state.source.image.naturalHeight) throw new Error('Image orientation could not be aligned. Re-save as PNG and try again.');
    state.result = result; state.view = 'annotated';
    $('view-annotated').disabled = false;
    $('view-original').setAttribute('aria-pressed', 'false'); $('view-annotated').setAttribute('aria-pressed', 'true');
    $('run-meta').textContent = `${result.inference_seconds.toFixed(2)} s model time · ${result.tiles} ${result.tiles === 1 ? 'tile' : 'tiles'}`;
    renderResults();
    status(result.count ? 'Analysis complete. Inspect the regions, adjust the probability threshold, or download the active results.' : 'Analysis complete: no regions at the active threshold. Review the original image; buildings may have been missed.');
  } catch (e) {
    if (state.epoch !== epoch) return;
    error(e.name === 'AbortError' ? 'Analysis timed out. Please retry or use a smaller image.' : e.message);
    status('Analysis did not finish. You can retry with the selected image.');
  } finally {
    clearTimeout(timeout);
    if (state.epoch === epoch) { clearInterval(state.timer); state.busy = false; $('loading').hidden = true; $('viewer').setAttribute('aria-busy', 'false'); controls(); }
  }
}
async function applyThreshold() {
  if (!state.result) return;
  const epoch = state.epoch, serial = ++state.filtering;
  const threshold = Number($('threshold').value);
  downloads(true); error();
  $('active-threshold').textContent = `Updating to ${threshold.toFixed(2)}…`;
  try {
    const response = await fetch('/api/regions', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ probability_png: state.result.probability_png, threshold }) });
    const update = await readResponse(response);
    if (state.epoch !== epoch || serial !== state.filtering) return;
    Object.assign(state.result, update); state.pending = false; solarController?.detectionsChanged(); renderResults();
    status(update.count ? 'Threshold applied. The viewer, count and downloads now use the active threshold.' : 'No regions at this threshold. A zero estimate can include missed buildings.');
  } catch (e) {
    if (state.epoch !== epoch || serial !== state.filtering) return;
    $('threshold').value = state.result.threshold;
    state.pending = false;
    renderResults(); error(`${e.message} The previous threshold remains active.`);
  }
}
function download(blob, filename) {
  const url = URL.createObjectURL(blob), link = document.createElement('a');
  link.href = url; link.download = filename; document.body.append(link); link.click(); link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 30000);
}
function downloadCSV() {
  const r = state.result;
  if (!r) return;
  const rows = [['image_id','detection_id','class','x_min','y_min','x_max_exclusive','y_max_exclusive','area_pixels','mean_building_probability','active_probability_threshold','model_id']];
  for (const region of r.regions) rows.push([r.image_id, region.id, region.class_name, region.x_min, region.y_min, region.x_max, region.y_max, region.area_pixels, region.mean_probability, Number(r.threshold).toFixed(2), r.model]);
  const csv = rows.map((row) => row.map((v) => `"${String(v).replaceAll('"', '""')}"`).join(',')).join('\r\n') + '\r\n';
  download(new Blob([csv], { type: 'text/csv;charset=utf-8' }), `rooftrace-${r.image_id}-p${Number(r.threshold).toFixed(2)}.csv`);
}
$('analyze').addEventListener('click', analyze);
$('upload').addEventListener('change', (e) => { const file = e.target.files[0]; if (file) selectSource(null, file); });
for (const type of ['dragenter', 'dragover']) $('drop-zone').addEventListener(type, (e) => { e.preventDefault(); if (!state.busy) $('drop-zone').classList.add('dragover'); });
for (const type of ['dragleave', 'drop']) $('drop-zone').addEventListener(type, (e) => { e.preventDefault(); $('drop-zone').classList.remove('dragover'); });
$('drop-zone').addEventListener('drop', (e) => { if (!state.busy && e.dataTransfer.files[0]) selectSource(null, e.dataTransfer.files[0]); });
for (const view of ['original', 'annotated']) $(`view-${view}`).addEventListener('click', () => {
  state.view = view;
  for (const name of ['original', 'annotated']) $(`view-${name}`).setAttribute('aria-pressed', String(view === name));
  if (state.result) renderResults(); else renderImage();
});
$('show-ids').addEventListener('change', () => renderImage());
$('threshold').addEventListener('input', () => {
  solarController?.detectionsChanged();
  $('threshold-value').textContent = Number($('threshold').value).toFixed(2);
  state.pending = true; downloads(true); state.filtering++; clearTimeout(filterTimer); filterTimer = setTimeout(applyThreshold, 200);
});
$('download-png').addEventListener('click', () => {
  if (!state.result) return;
  const filename = `rooftrace-${state.result.image_id}-p${Number(state.result.threshold).toFixed(2)}.png`;
  const output = document.createElement('canvas'); renderImage(output, true);
  output.toBlob((blob) => { if (blob) download(blob, filename); }, 'image/png');
});
$('download-csv').addEventListener('click', downloadCSV);
$('reset').addEventListener('click', () => {
  stopWork(); clearResult(); error(); state.source = null;
  if (state.url) URL.revokeObjectURL(state.url); state.url = null;
  $('upload').value = ''; $('threshold').value = '0.5'; $('threshold-value').textContent = '0.50';
  canvas.hidden = true; ctx.clearRect(0, 0, canvas.width, canvas.height); $('empty-view').hidden = false;
  $('dimensions').textContent = 'No image selected'; $('image-title').textContent = 'Image workspace'; $('source-credit').textContent = '';
  document.querySelectorAll('.sample').forEach((b) => b.setAttribute('aria-pressed', 'false'));
  status('Workspace reset. Choose another image to begin.'); controls();
});
async function init() {
  try {
    samples = await readResponse(await fetch('/api/samples'));
    $('samples').replaceChildren();
    for (const s of samples) {
      const button = document.createElement('button'); button.className = 'sample'; button.dataset.id = s.id; button.setAttribute('aria-pressed', 'false');
      const image = document.createElement('img'); image.src = s.image; image.alt = ''; image.width = 53; image.height = 53;
      const text = document.createElement('span'), title = document.createElement('strong'), detail = document.createElement('small');
      title.textContent = s.title; detail.textContent = s.id === 'phoenix' ? 'USGS · transfer challenge' : s.id === 'uttari' ? 'India · open imagery · 0.3 m / px' : 'WHU test · 0.3 m / px';
      text.append(title, detail); button.append(image, text); button.addEventListener('click', () => selectSource(s)); $('samples').append(button);
    }
    if (samples[0]) await selectSource(samples[0]);
  } catch { error('Sample imagery could not load. Reload the page, or upload your own image.'); }
}
solarController=createSolarController({getSource:()=>state.source,getResult:()=>state.result,redraw:()=>renderImage(),download,canvas});
init();
