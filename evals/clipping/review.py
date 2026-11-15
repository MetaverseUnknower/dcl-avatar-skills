#!/usr/bin/env python3
"""Label the eval's candidate frames in the browser: one frame at a time, four renders, keyboard labels.

usage: python3 review.py ~/.cache/dcl-clip-eval/runs/<run> [--labels ~/.cache/dcl-clip-eval/labels.json] [--port 8765]

Keys: 1 visible clip (the item's fault)   2 clean   3 the animation's fault (the bare avatar would clip too)
      4 unsure   n note   j / k or arrows: next / previous   b toggle blind mode   u jump to next unlabeled
For REST frames, 1 means a bug (a piece through a hard piece, a visible poke-through) and 2 means fine.

Blind mode (on by default) hides what the detector said until you label, so the labels aren't anchored on it.
Labels are saved on every keypress to one labels.json shared by all runs (keyed by candidate id), so a second run
with another Blender or checker version reuses them. score.py turns them into the report.
"""
import argparse, glob, json, os, threading, webbrowser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

ROOT = os.path.expanduser('~/.cache/dcl-clip-eval')
LOCK = threading.Lock()


def load_candidates(run):
    out = []
    for path in sorted(glob.glob(os.path.join(run, '*', '*', 'candidates.json'))):
        s = json.load(open(path))
        rel = os.path.relpath(os.path.dirname(path), run)
        it = s['item']
        for c in s['candidates']:
            out.append(c | {'images': [f'/run/{rel}/{p}' for p in c.get('images', [])],
                            'item_name': it.get('name') or it['slug'], 'category': it['category'], 'shape': s['shape'],
                            'thumb': f"/corpus/{it['slug']}/thumbnail.png", 'marketplace': it.get('marketplace'),
                            'gate_result': s['gate_result'], 'blender': s['blender']})
    return out


PAGE = r'''<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Clipping Labels</title><style>
:root{--bg:#f4f4f2;--fg:#1d1d1f;--mut:#6b6b70;--card:#fff;--line:#d9d9dc;--acc:#2f6fdf;--clip:#c8372d;--clean:#2f8f4e;--anim:#b07b12;--uns:#7a7a80}
@media (prefers-color-scheme:dark){:root{--bg:#141416;--fg:#ececee;--mut:#9a9aa2;--card:#1d1d21;--line:#33333a;--acc:#6b9cff;--clip:#ff6b5e;--clean:#5fcf83;--anim:#e8b04a;--uns:#a0a0a8}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:14px/1.45 -apple-system,system-ui,sans-serif}
header{display:flex;gap:16px;align-items:center;flex-wrap:wrap;padding:10px 16px;border-bottom:1px solid var(--line);position:sticky;top:0;background:var(--bg);z-index:2}
header b{font-size:15px}select,button,input{font:inherit;color:inherit;background:var(--card);border:1px solid var(--line);border-radius:6px;padding:4px 8px}
.bar{flex:1;min-width:120px;height:6px;background:var(--line);border-radius:3px;overflow:hidden}.bar i{display:block;height:100%;background:var(--acc)}
main{display:grid;grid-template-columns:minmax(0,1fr) 300px;gap:16px;padding:16px;max-width:1500px;margin:auto}
@media (max-width:900px){main{grid-template-columns:1fr}}
.imgs{display:grid;grid-template-columns:repeat(2,minmax(0,min(50%,calc((100vh - 96px)/2))));gap:8px;justify-content:center;align-content:start}.imgs figure{margin:0;position:relative;background:#000;border-radius:6px;overflow:hidden}
.imgs img{display:block;width:100%;height:auto;cursor:zoom-in}.imgs figcaption{position:absolute;left:6px;bottom:4px;color:#fff;font-size:11px;text-shadow:0 1px 2px #000}
.x::before,.x::after{content:"";position:absolute;left:50%;top:50%;background:rgba(255,60,60,.75);pointer-events:none}.x::before{width:22px;height:1px;margin-left:-11px}.x::after{width:1px;height:22px;margin-top:-11px}
.noX .x::before,.noX .x::after{display:none}
aside{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:14px;align-self:start;position:sticky;top:64px}
aside h2{font-size:15px;margin:0 0 4px}.mut{color:var(--mut)}.kv{display:grid;grid-template-columns:auto 1fr;gap:2px 10px;margin:10px 0;font-size:13px}
.kv dt{color:var(--mut)}.kv dd{margin:0;word-break:break-word}.thumb{width:64px;height:64px;float:right;border-radius:6px;background:var(--bg)}
.q{font-weight:600;margin:12px 0 6px}.btns{display:grid;grid-template-columns:1fr 1fr;gap:6px}.btns button{padding:8px;cursor:pointer;text-align:left}
.btns button[data-v=clip].on{background:var(--clip);color:#fff}.btns button[data-v=clean].on{background:var(--clean);color:#fff}
.btns button[data-v=anim].on{background:var(--anim);color:#fff}.btns button[data-v=unsure].on{background:var(--uns);color:#fff}
kbd{font:11px ui-monospace,monospace;border:1px solid var(--line);border-radius:3px;padding:0 4px;margin-right:6px}
textarea{width:100%;min-height:54px;margin-top:8px;font:inherit;color:inherit;background:var(--bg);border:1px solid var(--line);border-radius:6px;padding:6px}
.det{margin-top:10px;padding:8px;border-radius:6px;background:var(--bg);font-size:13px}.hidden{filter:blur(5px);user-select:none}
.zoom{position:fixed;inset:0;background:rgba(0,0,0,.88);display:none;align-items:center;justify-content:center;z-index:9}.zoom img{max-width:96vw;max-height:96vh}
</style></head><body>
<header><b>Clipping labels</b><span id="pos" class="mut"></span><div class="bar"><i id="prog"></i></div>
<select id="fk"><option value="">all kinds</option><option>pos-deep</option><option>pos-shallow</option><option>seam</option><option>graze</option><option>control</option><option>rest</option></select>
<select id="fc"><option value="">all categories</option></select>
<label><input type="checkbox" id="fu"> unlabeled only</label><label><input type="checkbox" id="bl" checked> blind</label><label><input type="checkbox" id="xh" checked> crosshair</label></header>
<main><section class="imgs" id="imgs"></section><aside id="side"></aside></main>
<div class="zoom" id="zoom"><img></div>
<script>
let C=[],L={},view=[],k=0;const $=s=>document.querySelector(s);
const CAP=['close-up','close-up, 70° round','from the other side','context'],CAPC=['front','right','back','left'];
const Q={rest:'Is this rest overlap a bug?',control:'Any visible clipping anywhere on the item?',seam:'Visible clipping at the crosshair?',graze:'Visible clipping at the crosshair?','pos-deep':'Visible clipping at the crosshair?','pos-shallow':'Visible clipping at the crosshair?'};
const OPT=[['clip','1','Visible clip'],['clean','2','Clean'],['anim','3','Animation\'s fault'],['unsure','4','Unsure']];
async function boot(){C=await (await fetch('/api/candidates')).json();L=await (await fetch('/api/labels')).json();
 [...new Set(C.map(c=>c.category))].sort().forEach(c=>$('#fc').add(new Option(c)));
 ['#fk','#fc','#fu'].forEach(s=>$(s).onchange=()=>{filter();k=0;draw()});$('#bl').onchange=draw;$('#xh').onchange=()=>document.body.classList.toggle('noX',!$('#xh').checked);
 filter();k=Math.max(0,view.findIndex(c=>!L[c.id]));draw()}
function filter(){const fk=$('#fk').value,fc=$('#fc').value,fu=$('#fu').checked;view=C.filter(c=>(!fk||c.kind==fk)&&(!fc||c.category==fc)&&(!fu||!L[c.id]))}
function esc(s){return String(s??'').replace(/[&<>"]/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[m]))}
function draw(){const n=C.filter(c=>L[c.id]).length;$('#prog').style.width=(100*n/Math.max(1,C.length))+'%';$('#pos').textContent=`${n}/${C.length} labeled`;
 const c=view[k];if(!c){$('#imgs').innerHTML='<p>Nothing to show with these filters.</p>';$('#side').innerHTML='';return}
 $('#imgs').innerHTML=c.images.map((src,i)=>`<figure class="${c.kind=='control'?'':'x'}"><img src="${src}" loading="eager"><figcaption>${c.kind=='control'?CAPC[i]:CAP[i]}</figcaption></figure>`).join('');
 const lab=L[c.id]||{},blind=$('#bl').checked&&!lab.v;
 const det=c.kind=='rest'?`REST overlap the skill asks you to judge, ${c.depth_cm} cm deep`:c.kind=='control'?'detector: clean frame (random control)':
  c.detector=='clip'?`detector: CLIP ${c.depth_cm} cm deep${c.gated?' (gated clip → FAIL)':' (reported clip)'}${c.bare_hand?' · bare body overlaps here too':''}`:
  c.kind=='seam'?`detector: clean (masked as rest seam; ${c.depth_cm} cm deep, grew ${c.growth_cm} cm from ${c.rest_depth_cm} at rest)`:`detector: graze, ${c.depth_cm} cm (under threshold)`;
 $('#side').innerHTML=`<img class="thumb" src="${c.thumb}" onerror="this.remove()"><h2>${esc(c.item_name)}</h2>
 <div class="mut">${c.category} · ${c.shape} · <a href="${c.marketplace}" target="_blank" style="color:var(--acc)">marketplace</a></div>
 <dl class="kv"><dt>clip</dt><dd>${esc(c.clip||'rest pose')}${c.frame!=null?' · frame '+c.frame:''}</dd><dt>pair</dt><dd>${esc(c.label)}</dd><dt>#</dt><dd>${k+1} of ${view.length}</dd></dl>
 <div class="q">${Q[c.kind]}</div><div class="btns">${OPT.map(([v,key,t])=>`<button data-v="${v}" class="${lab.v==v?'on':''}"><kbd>${key}</kbd>${c.kind=='rest'&&v=='clip'?'Bug':c.kind=='rest'&&v=='clean'?'Fine':t}</button>`).join('')}</div>
 <textarea id="note" placeholder="note (n)">${esc(lab.note||'')}</textarea>
 <div class="det ${blind?'hidden':''}">${esc(det)}<div class="mut">${esc(c.kind)} · ${esc(c.blender)}</div></div>
 <div class="mut" style="margin-top:10px;font-size:12px"><kbd>j</kbd>/<kbd>k</kbd> next/prev · <kbd>u</kbd> next unlabeled · <kbd>b</kbd> blind</div>`;
 document.querySelectorAll('.btns button').forEach(b=>b.onclick=()=>label(b.dataset.v));$('#note').onchange=e=>save(c,{...(L[c.id]||{}),note:e.target.value});
 document.querySelectorAll('.imgs img').forEach(im=>im.onclick=()=>{$('#zoom img').src=im.src;$('#zoom').style.display='flex'})}
async function save(c,v){L[c.id]=v;await fetch('/api/label',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({id:c.id,label:v})})}
function label(v){const c=view[k];save(c,{...(L[c.id]||{}),v,at:new Date().toISOString()});if(k<view.length-1)k++;draw()}
$('#zoom').onclick=()=>$('#zoom').style.display='none';
document.onkeydown=e=>{if(e.target.tagName=='TEXTAREA'){if(e.key=='Escape')e.target.blur();return}
 const o=OPT.find(o=>o[1]==e.key);if(o)return label(o[0]);
 if(e.key=='j'||e.key=='ArrowRight'){k=Math.min(view.length-1,k+1);draw()}else if(e.key=='k'||e.key=='ArrowLeft'){k=Math.max(0,k-1);draw()}
 else if(e.key=='u'){const i=view.findIndex((c,i)=>i>k&&!L[c.id]);if(i>=0){k=i;draw()}}else if(e.key=='b'){$('#bl').checked=!$('#bl').checked;draw()}
 else if(e.key=='n'){e.preventDefault();$('#note').focus()}else if(e.key=='Escape')$('#zoom').style.display='none'};
boot();
</script></body></html>'''


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('run')
    ap.add_argument('--labels', default=os.path.join(ROOT, 'labels.json'))
    ap.add_argument('--port', type=int, default=8765)
    ap.add_argument('--no-open', action='store_true')
    A = ap.parse_args()
    run = os.path.abspath(os.path.expanduser(A.run))
    corpus = json.load(open(os.path.join(run, 'run.json'))).get('corpus') if os.path.exists(os.path.join(run, 'run.json')) \
        else os.path.join(ROOT, 'corpus')
    cands = load_candidates(run)

    class H(SimpleHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def send(self, body, ctype='application/json'):
            b = body.encode() if isinstance(body, str) else body
            self.send_response(200)
            self.send_header('content-type', ctype)
            self.send_header('content-length', str(len(b)))
            self.end_headers()
            self.wfile.write(b)

        def labels(self):
            return json.load(open(A.labels)) if os.path.exists(A.labels) else {}

        def do_GET(self):
            p = self.path.split('?')[0]
            if p == '/':
                return self.send(PAGE, 'text/html; charset=utf-8')
            if p == '/api/candidates':
                return self.send(json.dumps(cands))
            if p == '/api/labels':
                return self.send(json.dumps(self.labels()))
            for prefix, base in (('/run/', run), ('/corpus/', corpus)):
                if p.startswith(prefix):
                    f = os.path.realpath(os.path.join(base, p[len(prefix):]))
                    if f.startswith(os.path.realpath(base)) and os.path.isfile(f):
                        return self.send(open(f, 'rb').read(), 'image/png')
            self.send_error(404)

        def do_POST(self):
            if self.path != '/api/label':
                return self.send_error(404)
            body = json.loads(self.rfile.read(int(self.headers['content-length'])))
            with LOCK:
                lab = self.labels()
                lab[body['id']] = body['label']
                tmp = A.labels + '.tmp'
                json.dump(lab, open(tmp, 'w'), indent=1)
                os.replace(tmp, A.labels)
            self.send('{"ok":true}')

    srv = ThreadingHTTPServer(('127.0.0.1', A.port), H)
    url = f'http://127.0.0.1:{A.port}/'
    print(f'{len(cands)} candidates from {run}\nlabels -> {A.labels}\nopen {url}  (ctrl-c to stop)')
    if not A.no_open:
        webbrowser.open(url)
    srv.serve_forever()


if __name__ == '__main__':
    main()
