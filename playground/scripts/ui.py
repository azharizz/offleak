#!/usr/bin/env python3
"""SafeIRL debug UI: pick a video, choose who stays visible, watch it redact as a live stream.

  playground/.venv/bin/python playground/scripts/ui.py      then open http://127.0.0.1:8765

Local only (binds 127.0.0.1). Videos come from playground/videos/ or are uploaded to playground/uploads/;
each run's redacted video and report land in playground/results/ui/<time>/.
"""
import base64
import json
import threading
import time
from pathlib import Path

import cv2
import numpy as np
from flask import Flask, Response, jsonify, request
from werkzeug.utils import secure_filename

import combined_detector as cd
from pick_faces import scan_faces
from stream import live

UPLOADS, RUNS = cd.BASE / 'uploads', cd.BASE / 'results/ui'
EXTS = {'.mp4', '.mov', '.mkv', '.webm', '.m4v'}
app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 4 << 30
# ponytail: one session at a time (module-level state); a shared server would need per-user sessions
S = {'faces': [], 'stats': {}, 'jpeg': None, 'seq': 0, 'stop': None, 'thread': None, 'debug': True, 'report': None, 'error': None, 'out': None}


def videos():
    UPLOADS.mkdir(exist_ok=True)
    return sorted(str(p.relative_to(cd.BASE)) for d in (cd.BASE / 'videos', UPLOADS) for p in d.iterdir() if p.suffix.lower() in EXTS)


def checked_video(name):
    if name not in videos():  # only files the UI listed: no arbitrary paths
        raise ValueError('unknown video')
    return cd.BASE / name


def jpg(img, q=80):
    return cv2.imencode('.jpg', img, [cv2.IMWRITE_JPEG_QUALITY, q])[1].tobytes()


def on_frame(orig, red, mask, keep):
    S['n'] = S.get('n', 0) + 1
    if S['n'] % 2:  # 15 fps preview keeps the encoder load off the live loop
        return
    left = orig.copy()
    if S['debug']:
        cs, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        cv2.drawContours(left, cs, -1, (0, 0, 255), 3)  # red: what got blurred
        for x1, y1, x2, y2 in keep:
            cv2.rectangle(left, (x1, y1), (x2, y2), (0, 220, 0), 3)  # green: recognised streamer kept visible
    h = 360
    side = np.hstack([cv2.resize(left, (h * left.shape[1] // left.shape[0], h)), cv2.resize(red, (h * red.shape[1] // red.shape[0], h))])
    S['jpeg'], S['seq'] = jpg(side, 75), S['seq'] + 1


def run(path, out, exclude):
    try:
        S['report'] = live(path, str(out / 'redacted.mp4'), exclude, realtime=True, on_frame=on_frame, stop=S['stop'], stats=S['stats'])
        (out / 'report.json').write_text(json.dumps(S['report'], indent=2))
    except BaseException as e:  # surface failures in the page instead of a silent dead thread
        S['error'] = f'{type(e).__name__}: {e}'


@app.get('/')
def page():
    return PAGE


@app.get('/videos')
def list_videos():
    return jsonify(videos())


@app.post('/upload')
def upload():
    f = request.files.get('file')
    name = secure_filename(f.filename or '') if f else ''
    if not name or Path(name).suffix.lower() not in EXTS:
        return jsonify(error='choose a video file (mp4, mov, mkv, webm, m4v)'), 400
    UPLOADS.mkdir(exist_ok=True)
    f.save(UPLOADS / name)
    return jsonify(name=str((UPLOADS / name).relative_to(cd.BASE)))


@app.post('/scan')
def scan():
    try:
        path = checked_video(request.json.get('video'))
    except ValueError as e:
        return jsonify(error=str(e)), 400
    S['faces'] = scan_faces(path, every=1.)
    return jsonify([{'i': i, 'seen': seen, 'img': 'data:image/jpeg;base64,' + base64.b64encode(jpg(cv2.resize(c, (128, 128)))).decode()}
                    for i, (c, seen) in enumerate(S['faces'])])


@app.post('/start')
def start():
    try:
        path = checked_video(request.json.get('video'))
    except ValueError as e:
        return jsonify(error=str(e)), 400
    keep = [int(i) for i in request.json.get('keep', []) if 0 <= int(i) < len(S['faces'])]
    stop()
    out = RUNS / time.strftime('%Y%m%d-%H%M%S')
    out.mkdir(parents=True)
    exclude = []
    for i in keep:
        cv2.imwrite(str(out / f'keep-{i + 1}.png'), S['faces'][i][0])
        exclude.append(out / f'keep-{i + 1}.png')
    S.update(stats={}, report=None, error=None, jpeg=None, stop=threading.Event(), out=str(out.relative_to(cd.BASE)))
    S['thread'] = threading.Thread(target=run, args=(path, out, exclude), daemon=True)
    S['thread'].start()
    return jsonify(ok=True, out=S['out'])


@app.post('/stop')
def stop():
    if S['stop']:
        S['stop'].set()
    if S['thread']:
        S['thread'].join(timeout=30)
    return jsonify(ok=True)


@app.post('/debug')
def debug():
    S['debug'] = bool(request.json.get('on'))
    return jsonify(ok=True)


@app.get('/stats')
def stats():
    running = bool(S['thread'] and S['thread'].is_alive())
    return jsonify(running=running, stats=S['stats'], report=S['report'], error=S['error'], out=S['out'])


@app.get('/feed')
def feed():
    def gen():
        seen = -1
        while True:
            if S['seq'] != seen and S['jpeg']:
                seen = S['seq']
                yield b'--f\r\nContent-Type: image/jpeg\r\n\r\n' + S['jpeg'] + b'\r\n'
            time.sleep(.02)
    return Response(gen(), mimetype='multipart/x-mixed-replace; boundary=f')


PAGE = '''<!doctype html><html><head><meta charset="utf-8"><title>SafeIRL Debug</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
:root{--bg:#111418;--panel:#1b2027;--text:#e6e8eb;--muted:#9aa3ad;--accent:#3ea6ff;--ok:#2fbf71;--bad:#ff5c5c;--line:#2b323c}
@media (prefers-color-scheme:light){:root{--bg:#f4f5f7;--panel:#fff;--text:#16191d;--muted:#5b6470;--line:#dde1e6}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:14px/1.45 system-ui,-apple-system,sans-serif}
main{max-width:1340px;margin:auto;padding:16px;display:grid;gap:14px}
h1{font-size:18px;margin:0}h2{font-size:13px;text-transform:uppercase;letter-spacing:.05em;color:var(--muted);margin:0 0 8px}
.panel{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:14px}
.row{display:flex;gap:8px;flex-wrap:wrap;align-items:center}
select,button,input[type=file]{font:inherit;color:var(--text);background:var(--bg);border:1px solid var(--line);border-radius:7px;padding:7px 10px}
button{cursor:pointer}button.primary{background:var(--accent);border-color:var(--accent);color:#fff}button:disabled{opacity:.5;cursor:default}
#faces{display:flex;gap:10px;flex-wrap:wrap}
.face{width:128px;text-align:center;cursor:pointer;border:3px solid transparent;border-radius:10px;padding:3px;user-select:none}
.face img{width:100%;border-radius:7px;display:block}.face.on{border-color:var(--ok)}.face small{color:var(--muted)}
#feed{width:100%;border-radius:8px;background:#000;min-height:120px;display:block}
.legend{color:var(--muted);font-size:12px}.legend b.r{color:var(--bad)}.legend b.g{color:var(--ok)}
#stats{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:8px}
.stat{background:var(--bg);border-radius:8px;padding:8px 10px}.stat span{display:block;color:var(--muted);font-size:12px}.stat b{font-size:18px}
#msg{color:var(--muted)}#msg.err{color:var(--bad)}
</style></head><body><main>
<h1>SafeIRL &mdash; live redaction debugger</h1>
<section class="panel"><h2>1 &middot; Video</h2><div class="row">
<select id="video"></select><input type="file" id="file" accept="video/*"><button id="up">Upload</button>
<button id="scan" class="primary">Scan faces</button><span id="msg"></span></div></section>
<section class="panel"><h2>2 &middot; Who stays visible? <span class="legend">(click to select; most-seen first, the streamer is usually #1; select none to blur everyone)</span></h2>
<div id="faces"><span class="legend">Scan a video first.</span></div></section>
<section class="panel"><h2>3 &middot; Live stream</h2><div class="row" style="margin-bottom:10px">
<button id="start" class="primary">Start stream</button><button id="stop">Stop</button>
<label><input type="checkbox" id="debug" checked> Debug overlay</label>
<span class="legend">Left: original (<b class="r">red</b> = blurred region, <b class="g">green</b> = recognised streamer) &middot; Right: what viewers see</span></div>
<img id="feed" alt="live feed appears here after Start">
<div id="stats" style="margin-top:10px"></div><p id="out" class="legend"></p></section>
</main><script>
const $=id=>document.getElementById(id), keep=new Set();
const msg=(t,err)=>{$('msg').textContent=t||'';$('msg').className=err?'err':''};
async function post(u,b){const r=await fetch(u,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(b||{})});const j=await r.json();if(!r.ok)throw new Error(j.error||r.status);return j}
async function loadVideos(sel){const v=await (await fetch('/videos')).json();$('video').innerHTML=v.map(x=>`<option>${x}</option>`).join('');if(sel)$('video').value=sel}
$('up').onclick=async()=>{const f=$('file').files[0];if(!f)return msg('Choose a file first',1);msg('Uploading…');const fd=new FormData();fd.append('file',f);
 const r=await fetch('/upload',{method:'POST',body:fd});const j=await r.json();if(!r.ok)return msg(j.error,1);await loadVideos(j.name);msg('Uploaded')};
$('scan').onclick=async()=>{msg('Scanning faces (about 1s per 10s of video)…');$('scan').disabled=true;keep.clear();
 try{const fs=await post('/scan',{video:$('video').value});$('faces').innerHTML=fs.length?fs.map(f=>`<div class="face" data-i="${f.i}"><img src="${f.img}"><small>#${f.i+1} &middot; seen ${f.seen}&times;</small></div>`).join(''):'<span class="legend">No clear faces found - everyone will be blurred.</span>';
  document.querySelectorAll('.face').forEach(el=>el.onclick=()=>{const i=+el.dataset.i;keep.has(i)?keep.delete(i):keep.add(i);el.classList.toggle('on')});msg(fs.length+' people found')}
 catch(e){msg(e.message,1)}finally{$('scan').disabled=false}};
$('start').onclick=async()=>{try{const j=await post('/start',{video:$('video').value,keep:[...keep]});$('feed').src='/feed?'+Date.now();$('out').textContent='Saving to playground/'+j.out+'/';msg('Loading models, then streaming…')}catch(e){msg(e.message,1)}};
$('stop').onclick=()=>post('/stop');
$('debug').onchange=e=>post('/debug',{on:e.target.checked});
const label={frames:'Frames out',output_fps:'Output fps',latency_ms:'Delay (ms)',head_det_per_s:'Face/head det /s',object_det_per_s:'OCR/QR det /s',dropped:'Dropped frames',failsafe_frames:'Fail-safe frames',late:'Late detections',rotation_deg:'Rotation fix (deg)',mirrored:'Mirrored text'};
setInterval(async()=>{const s=await (await fetch('/stats')).json();const st=s.stats||{};
 $('stats').innerHTML=Object.keys(label).filter(k=>k in st).map(k=>`<div class="stat"><span>${label[k]}</span><b>${st[k]}</b></div>`).join('');
 if(s.error)msg(s.error,1);else if(s.running&&st.frames)msg('Streaming');else if(s.report)msg('Finished - p95 delay '+s.report.latency_ms_p95+' ms, output '+s.report.output_fps+' fps')},1000);
loadVideos();
</script></body></html>'''

if __name__ == '__main__':
    print('SafeIRL debug UI: http://127.0.0.1:8765')
    app.run(host='127.0.0.1', port=8765, threaded=True)
