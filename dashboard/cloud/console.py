"""The multi-tenant cloud console — /cloud on the bridge.

This is the screen that answers "what happens when you have 400 customers
instead of one node": every farm's gateway writes into the same Firestore
project under its own farm id, and this page reads across all of them.

Everything shown here is COMPUTED from stored history, not decorated onto it:
the risk percentage comes from the fleet model, the drivers come from that
model's per-feature contributions, and the regional banner comes from
correlating farms that have never heard of each other.

Mounted as a Flask blueprint so `dashboard/app.py` gains a two-line diff and
nothing about the frozen demo path changes.
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timedelta, timezone

from flask import Blueprint, Response, request

from . import CFG, open_store, status as cloud_status
from .fleet import (FEATURE_KEYS, RiskModel, WINDOW_H, HORIZON_H, featurize,
                    forecast, regional_signal, _hour_of)
from .sink import SINK

bp = Blueprint("cloud", __name__)

MARKER_TYPES = ("DISTRESS_SOUND", "FOOD_LOW", "WATER_LOW", "NH3_HIGH",
                "NH3_CRITICAL", "TEMP_CRITICAL", "GAS_CRITICAL", "MORTALITY")

_cache = {"t": 0.0, "payload": None}
CACHE_SEC = 4.0          # the page polls; Firestore reads cost money


def _model(store):
    m = RiskModel.from_doc(store.get_doc("fleet/model"))
    return m


def _farm_view(store, farm: dict, model, deep: bool = False):
    fid = farm.get("_id") or farm.get("farm_id")
    hist = store.list_docs(f"farms/{fid}/telemetry", order_by="ts",
                           desc=True, limit=72 if deep else 12)
    hist = sorted(hist, key=lambda s: s.get("ts", ""))
    events = store.list_docs(f"farms/{fid}/events", order_by="ts",
                             desc=True, limit=40 if deep else 12)

    risk, drivers = None, []
    if model and len(hist) >= WINDOW_H:
        win = hist[-WINDOW_H:]
        x = featurize(win, _hour_of(win[-1].get("ts", "")))
        risk = round(100 * model.predict(x), 1)
        drivers = model.explain(x)

    cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)) \
        .strftime("%Y-%m-%dT%H:%M:%SZ")
    recent = [e for e in events if str(e.get("ts", "")) >= cutoff]
    markers = sorted({e.get("type", "") for e in recent
                      if e.get("type") in MARKER_TYPES})

    last = hist[-1] if hist else {}
    live = farm.get("live") or {k: last.get(k) for k in
                                ("nh3", "temp", "hum", "gas", "water", "food")}
    out = {
        "_id": fid,
        "name": farm.get("name", fid), "region": farm.get("region", "—"),
        "town": farm.get("town", ""), "species": farm.get("species", ""),
        "herd": farm.get("herd", 0), "plan": farm.get("plan", "—"),
        "owner": farm.get("owner", ""), "is_live_node": bool(farm.get("is_live_node")),
        "mode": farm.get("mode") or last.get("mode", "—"),
        "last_seen": farm.get("last_seen") or last.get("ts", ""),
        "samples": farm.get("samples", len(hist)),
        "alerts_24h": len([e for e in recent
                           if e.get("sev") in ("ALERT", "EMERG")]),
        "live": {k: v for k, v in (live or {}).items() if v is not None},
        "risk": risk if risk is not None else (farm.get("risk_pct") or 0),
        "drivers": drivers or (farm.get("risk_drivers") or []),
        "forecast": forecast(hist) or (farm.get("forecast") or []),
        "markers": markers,
        "spark": [round(float(s.get("nh3") or 0), 1) for s in hist[-48:]],
    }
    if deep:
        out["history"] = hist
        out["events"] = events
        out["daily"] = sorted(
            store.list_docs(f"farms/{fid}/daily", order_by="date",
                            desc=True, limit=14),
            key=lambda d: d.get("date", ""))
    return out


def _fleet_payload(force: bool = False):
    if not force and _cache["payload"] and time.time() - _cache["t"] < CACHE_SEC:
        return _cache["payload"]
    store = open_store()
    model = _model(store)
    farms = [_farm_view(store, f, model)
             for f in store.list_docs("farms", limit=200)]
    farms.sort(key=lambda f: -(f["risk"] or 0))
    summary = store.get_doc("fleet/summary") or {}

    payload = {
        "farms": farms,
        "regions": regional_signal(farms),
        "summary": {
            "farms": len(farms),
            "regions": len({f["region"] for f in farms}),
            "animals": sum(int(f.get("herd") or 0) for f in farms),
            "samples": summary.get("samples", sum(f.get("samples", 0) for f in farms)),
            "alerts_24h": sum(f["alerts_24h"] for f in farms),
            "at_risk": len([f for f in farms if (f["risk"] or 0) >= 35]),
            "history_days": summary.get("history_days", 0),
        },
        "model": (model.meta | {"features": len(FEATURE_KEYS),
                                "horizon_h": HORIZON_H, "window_h": WINDOW_H})
                 if model else None,
        "cloud": cloud_status(),
        "sink": SINK.snapshot(),
        "t": datetime.now(timezone.utc).strftime("%H:%M:%S"),
    }
    _cache.update(t=time.time(), payload=payload)
    return payload


# ── JSON API (also the Flutter app's fallback when the SDK can't init) ───
@bp.route("/cloud/api/fleet")
def api_fleet():
    return _fleet_payload(force=request.args.get("force") == "1")


@bp.route("/cloud/api/farm/<fid>")
def api_farm(fid):
    store = open_store()
    doc = store.get_doc(f"farms/{fid}")
    if not doc:
        return {"error": "no such farm"}, 404
    doc["_id"] = fid
    return _farm_view(store, doc, _model(store), deep=True)


@bp.route("/cloud/api/status")
def api_status():
    return {"cloud": cloud_status(), "sink": SINK.snapshot()}


@bp.route("/cloud/api/seed", methods=["POST"])
def api_seed():
    from .seed import seed
    days = int((request.json or {}).get("days", 30))
    model, _ = seed(days, wipe=bool((request.json or {}).get("wipe")), verbose=False)
    SINK._load_model(open_store())
    _cache["payload"] = None
    return {"ok": True, "model": model.meta}


@bp.route("/cloud/api/train", methods=["POST"])
def api_train():
    """Retrain on whatever is ACTUALLY in the cloud right now."""
    store = open_store()
    series = []
    for f in store.list_docs("farms", limit=200):
        fid = f.get("_id")
        h = store.list_docs(f"farms/{fid}/telemetry", order_by="ts",
                            desc=False, limit=2000)
        if len(h) > 50:
            series.append(h)
    from .fleet import build_dataset
    X, y = build_dataset(series)
    try:
        model = RiskModel.train(X, y)
    except ValueError as e:
        return {"ok": False, "err": str(e)}, 400
    store.set_doc("fleet/model", model.to_doc(), merge=False)
    SINK.model = model
    _cache["payload"] = None
    return {"ok": True, "model": model.meta}


@bp.route("/cloud/api/validate", methods=["POST"])
def api_validate():
    from .validate import run
    return run(verbose=False)


@bp.route("/cloud")
@bp.route("/cloud/")
def page():
    return Response(PAGE, mimetype="text/html")


PAGE = r"""<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>BioGuard Cloud — Fleet Console</title>
<style>
 /* Same ISA-101 industrial skin as the bridge test bench: status color means
    STATE and nothing else, sans for chrome, mono only for measured data. */
 :root{--bg:#0B0E12;--card:#151A21;--inset:#0A0D11;--line:#28313D;--edge:#33404F;
       --tx:#F2F6FA;--dim:#95A1AF;--ok:#35C46F;--warn:#F0A72E;--alert:#FF5449;
       --sim:#B18CFF;--acc:#41A8FF;
       --sans:"Avenir Next","Segoe UI",system-ui,-apple-system,sans-serif;
       --mono:ui-monospace,"SF Mono",Menlo,Consolas,monospace}
 *{box-sizing:border-box}
 body{margin:0;background:var(--bg);color:var(--tx);padding:14px 16px;
   font-family:var(--sans);font-size:13.5px}
 #topbar{display:flex;align-items:center;justify-content:space-between;gap:12px;
   flex-wrap:wrap;padding:2px 2px 12px;border-bottom:1px solid var(--line)}
 .brand{display:flex;align-items:center;gap:11px}
 .brand-tick{width:4px;height:36px;background:var(--acc);border-radius:2px}
 .brand-name{font-weight:800;font-size:19px;line-height:1;letter-spacing:.14em}
 .brand-sub{font-size:11.5px;color:var(--dim);margin-top:4px}
 .topbar-right{display:flex;align-items:center;gap:9px;flex-wrap:wrap}
 .pill{display:inline-block;border:1px solid var(--line);border-radius:4px;
   padding:4px 10px;font-family:var(--mono);font-size:11px;color:var(--dim)}
 .pill.on{border-color:var(--ok);color:var(--ok)}
 .pill.off{border-color:var(--warn);color:var(--warn)}
 .navlink{color:var(--acc);font-weight:700;font-size:11px;letter-spacing:.08em;
   text-decoration:none;border:1px solid var(--acc);border-radius:4px;padding:6px 11px}
 .navlink:hover{background:#41A8FF1A}
 .dim{color:var(--dim);font-size:12px}
 .lbl{font-weight:700;font-size:10.5px;letter-spacing:.1em;text-transform:uppercase;
   color:var(--dim)}
 .card{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:14px}
 .row{display:flex;gap:12px;flex-wrap:wrap;margin-top:12px}

 /* KPI strip */
 #kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin-top:14px}
 .kpi{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:12px 14px}
 .kpi b{display:block;font-family:var(--mono);font-size:26px;font-weight:700;
   line-height:1.15;font-variant-numeric:tabular-nums;margin-top:5px}

 /* regional banner — the cross-farm finding */
 .region{border:1px solid var(--alert);border-left:4px solid var(--alert);
   background:#FF54490E;border-radius:8px;padding:13px 15px;margin-top:14px}
 .region.WARN{border-color:var(--warn);background:#F0A72E0E}
 .region h3{margin:0 0 5px;font-size:14px;letter-spacing:.02em}
 .region .who{font-family:var(--mono);font-size:11.5px;color:var(--dim);margin-top:7px}
 .tag{display:inline-block;border:1px solid var(--edge);border-radius:3px;
   padding:2px 7px;font-family:var(--mono);font-size:10px;color:var(--dim);margin:3px 4px 0 0}

 /* farm grid */
 #farms{display:grid;grid-template-columns:repeat(auto-fill,minmax(340px,1fr));gap:12px;margin-top:12px}
 .farm{background:var(--card);border:1px solid var(--line);border-radius:8px;
   padding:14px;border-left:3px solid var(--edge);cursor:pointer}
 .farm:hover{border-color:var(--edge)}
 .farm.r-warn{border-left-color:var(--warn)}
 .farm.r-alert{border-left-color:var(--alert)}
 .farm.r-ok{border-left-color:var(--ok)}
 .fhead{display:flex;justify-content:space-between;align-items:flex-start;gap:10px}
 .fname{font-weight:700;font-size:15px}
 .live-dot{display:inline-block;width:7px;height:7px;border-radius:50%;
   background:var(--ok);margin-right:6px;vertical-align:middle}
 .riskn{font-family:var(--mono);font-size:25px;font-weight:700;line-height:1;
   font-variant-numeric:tabular-nums}
 .bar{height:5px;background:var(--inset);border-radius:3px;overflow:hidden;margin-top:8px}
 .bar i{display:block;height:100%;border-radius:3px}
 .metrics{display:grid;grid-template-columns:repeat(3,1fr);gap:7px;margin-top:11px}
 .metrics div{background:var(--inset);border:1px solid var(--line);border-radius:5px;
   padding:6px 8px}
 .metrics span{display:block;font-family:var(--mono);font-size:14px;font-weight:600;
   font-variant-numeric:tabular-nums;margin-top:2px}
 .why{margin-top:10px;font-size:12px;line-height:1.55}
 .why b{font-family:var(--mono);font-weight:700}
 .fc{margin-top:8px;font-family:var(--mono);font-size:11.5px;color:var(--warn)}
 svg.spark{display:block;width:100%;height:30px;margin-top:9px}

 /* footer cards */
 .kv{display:grid;grid-template-columns:auto 1fr;gap:4px 14px;font-family:var(--mono);
   font-size:11.5px;margin-top:9px}
 .kv b{color:var(--dim);font-weight:400}
 button{background:var(--inset);color:var(--tx);border:1px solid var(--edge);
   border-radius:5px;padding:7px 12px;cursor:pointer;font-family:var(--sans);
   font-weight:600;font-size:11.5px;margin:8px 6px 0 0}
 button:hover{border-color:var(--acc)}
 button:disabled{opacity:.45;cursor:default}
 .ok{color:var(--ok)}.warn{color:var(--warn)}.alert{color:var(--alert)}
 #drawer{position:fixed;inset:0;background:#000A;display:none;z-index:50}
 #drawer.on{display:block}
 #dpanel{position:absolute;right:0;top:0;bottom:0;width:min(560px,94vw);
   background:var(--bg);border-left:1px solid var(--line);padding:16px;overflow-y:auto}
 table{width:100%;font-family:var(--mono);font-size:11.5px;border-collapse:collapse;margin-top:8px}
 td,th{border-bottom:1px solid var(--line);padding:4px 6px;text-align:left}
 th{font-family:var(--sans);font-size:10px;font-weight:700;letter-spacing:.08em;
   text-transform:uppercase;color:var(--dim)}
 .EMERG,.ALERT{color:var(--alert)}.WARN{color:var(--warn)}
 .SEC{color:var(--sim)}.INFO{color:var(--dim)}
</style></head><body>

<div id="topbar">
  <div class="brand"><div class="brand-tick"></div><div>
    <div class="brand-name">BIO GUARD CLOUD</div>
    <div class="brand-sub">Multi-tenant fleet console — every farm, one model</div>
  </div></div>
  <div class="topbar-right">
    <span class="pill" id="backend">…</span>
    <span class="pill" id="project">…</span>
    <span class="pill" id="clock">--:--:--</span>
    <a class="navlink" href="/">BRIDGE</a>
    <a class="navlink" href="/app/">APP</a>
  </div>
</div>

<div id="kpis"></div>
<div id="regions"></div>
<div id="farms"></div>

<div class="row">
  <div class="card" style="flex:1;min-width:330px">
    <div class="lbl">Fleet risk model</div>
    <div class="dim" style="margin-top:6px;line-height:1.5">
      Logistic regression over an 11-feature window, trained on every farm's
      pooled history. Predicts an ALERT-grade incident
      <b id="hz">6</b> h ahead.
    </div>
    <div class="kv" id="modelkv"></div>
    <button onclick="post('/cloud/api/train',{},'retraining on stored history…')">
      Retrain from cloud history</button>
    <button onclick="post('/cloud/api/validate',{},'holding each farm out…')">
      Leave-one-farm-out validation</button>
    <div id="valout" class="dim" style="margin-top:9px;font-family:var(--mono);
      font-size:11.5px;white-space:pre-line"></div>
  </div>

  <div class="card" style="flex:1;min-width:330px">
    <div class="lbl">This gateway → cloud</div>
    <div class="dim" style="margin-top:6px;line-height:1.5">
      The bridge mirrors the live Pi node into Firestore under its farm id.
      Batched, rate-limited and fail-open: losing the network costs telemetry
      resolution, never the node.
    </div>
    <div class="kv" id="sinkkv"></div>
    <button onclick="post('/cloud/api/seed',{days:30},'regenerating fleet history…')">
      Reseed demo fleet (30 d)</button>
  </div>
</div>

<div id="drawer" onclick="if(event.target.id=='drawer')closeD()">
  <div id="dpanel"></div></div>

<script>
const $ = s => document.querySelector(s);
const num = n => (n==null?'—':(+n).toLocaleString('en-US'));
const riskColor = r => r>=45?'var(--alert)':r>=20?'var(--warn)':'var(--ok)';
// a farm sitting at 0.4% must not render as a flat "0%" — that reads as a
// dead sensor rather than as a quiet barn
const riskText = r => r<1 ? '&lt;1' : Math.round(r);
const riskClass = r => r>=45?'r-alert':r>=20?'r-warn':'r-ok';

function spark(vals){
  if(!vals||vals.length<2) return '';
  const w=300,h=30,mn=Math.min(...vals),mx=Math.max(...vals),rg=(mx-mn)||1;
  const pts=vals.map((v,i)=>`${(i/(vals.length-1)*w).toFixed(1)},${(h-2-(v-mn)/rg*(h-5)).toFixed(1)}`);
  return `<svg class="spark" viewBox="0 0 ${w} ${h}" preserveAspectRatio="none">
    <polyline points="${pts.join(' ')}" fill="none" stroke="var(--acc)"
      stroke-width="1.4" vector-effect="non-scaling-stroke"/></svg>`;
}

function farmCard(f){
  const r = Math.round(f.risk||0);
  const live = f.live||{};
  const cell = (k,l,u='') => live[k]==null?'' :
    `<div><div class="lbl" style="font-size:9px">${l}</div>
     <span>${(+live[k]).toFixed(k=='gas'?0:1)}${u}</span></div>`;
  const why = (f.drivers||[]).length
    ? `<div class="why"><span class="dim">Driven by</span> `
      + f.drivers.map(d=>`<b>${d.factor}</b> <span class="dim">${d.share}%</span>`)
          .join('<span class="dim"> · </span>') + `</div>`
    : '';
  const fc = (f.forecast||[]).length
    ? `<div class="fc">▸ ${f.forecast[0].metric.toUpperCase()} ${f.forecast[0].text}</div>` : '';
  const mk = (f.markers||[]).map(m=>`<span class="tag">${m.replace(/_/g,' ').toLowerCase()}</span>`).join('');
  return `<div class="farm ${riskClass(r)}" onclick="openD('${f._id}')">
    <div class="fhead">
      <div>
        <div class="fname">${f.is_live_node?'<i class="live-dot"></i>':''}${f.name}</div>
        <div class="dim" style="margin-top:3px">${f.region} · ${f.species} ·
          ${num(f.herd)} head</div>
      </div>
      <div style="text-align:right">
        <div class="riskn" style="color:${riskColor(r)}">${riskText(f.risk||0)}<span
          style="font-size:13px">%</span></div>
        <div class="lbl" style="font-size:9px">6 h risk</div>
      </div>
    </div>
    <div class="bar"><i style="width:${Math.min(100,r)}%;background:${riskColor(r)}"></i></div>
    <div class="metrics">
      ${cell('nh3','NH₃',' ppm')}${cell('temp','Temp','°')}${cell('hum','Hum','%')}
      ${cell('gas','CH₄')}${cell('water','Water','%')}${cell('food','Feed','%')}
    </div>
    ${why}${fc}${mk?`<div style="margin-top:7px">${mk}</div>`:''}
    ${spark(f.spark)}
    <div class="dim" style="margin-top:7px;font-family:var(--mono);font-size:10.5px">
      ${f.mode} · ${f.alerts_24h} alert${f.alerts_24h==1?'':'s'}/24 h ·
      ${num(f.samples)} samples · ${f.plan}</div>
  </div>`;
}

function render(d){
  const s=d.summary, c=d.cloud||{};
  $('#backend').textContent = (c.backend||'?').toUpperCase();
  $('#backend').className = 'pill ' + (c.backend=='firestore'?'on':'off');
  $('#backend').title = c.detail||'';
  $('#project').textContent = c.project||'—';
  $('#clock').textContent = d.t;

  $('#kpis').innerHTML = [
    ['Farms online', s.farms, ''],
    ['Animals monitored', num(s.animals), ''],
    ['Samples stored', num(s.samples), ''],
    ['Farms at risk', s.at_risk, s.at_risk?'alert':'ok'],
    ['Alerts / 24 h', s.alerts_24h, s.alerts_24h?'warn':'ok'],
  ].map(([l,v,cl])=>`<div class="kpi"><div class="lbl">${l}</div>
      <b class="${cl||''}">${v}</b></div>`).join('');

  $('#regions').innerHTML = (d.regions||[]).map(r=>`
    <div class="region ${r.severity}">
      <h3>${r.severity=='ALERT'?'⚠':'▲'} Regional biosecurity signal — ${r.region}</h3>
      <div style="line-height:1.55">${r.text}</div>
      <div class="who">${r.names.join('  ·  ')}</div>
    </div>`).join('');

  $('#farms').innerHTML = (d.farms||[]).map(farmCard).join('');

  const m=d.model;
  $('#modelkv').innerHTML = m ? [
    ['trained', m.trained_at],['windows', num(m.samples)],
    ['incidents', m.incidents],['features', m.features],
    ['horizon', m.horizon_h+' h'],['look-back', m.window_h+' h'],
    ['training AUC', m.auc]].map(([k,v])=>`<b>${k}</b><span>${v}</span>`).join('')
    : '<b>model</b><span class="warn">not trained yet</span>';
  if(m) $('#hz').textContent = m.horizon_h;

  const k=d.sink||{};
  $('#sinkkv').innerHTML = [
    ['farm id', k.farm_id],['docs uploaded', num(k.uploaded)],
    ['queued', k.queued],['dropped', k.dropped],
    ['errors', k.errors ? `<span class="warn">${k.errors}</span>` : 0],
    ['last write', k.last_ok||'—'],
    ['live risk (peak-hold)', k.risk!=null?k.risk+' %':'—'],
    ['live risk (now)', k.risk_now!=null?k.risk_now+' %':'—'],
    ['last error', k.last_error?`<span class="warn">${k.last_error}</span>`:'none'],
  ].map(([a,b])=>`<b>${a}</b><span>${b}</span>`).join('');
}

async function tick(){
  try{ render(await (await fetch('/cloud/api/fleet')).json()); }
  catch(e){ $('#backend').textContent='OFFLINE'; }
}

async function post(url, body, msg){
  const bs=[...document.querySelectorAll('button')];
  bs.forEach(b=>b.disabled=true);
  $('#valout').textContent = msg;
  try{
    const r = await (await fetch(url,{method:'POST',
      headers:{'Content-Type':'application/json'},body:JSON.stringify(body)})).json();
    if(r.mean_auc!=null){
      $('#valout').textContent =
        r.rows.map(x=>`${x.farm.padEnd(14)} held out → AUC ${x.test_auc}  (${x.test_positives} incidents)`)
         .join('\n') + `\n\nmean held-out AUC ${r.mean_auc} over ${r.folds} folds`;
    } else if(r.model){
      $('#valout').textContent =
        `retrained: ${r.model.samples} windows, ${r.model.incidents} incidents, AUC ${r.model.auc}`;
    } else { $('#valout').textContent = JSON.stringify(r); }
  }catch(e){ $('#valout').textContent = 'failed: '+e; }
  bs.forEach(b=>b.disabled=false);
  tick();
}

async function openD(id){
  $('#drawer').classList.add('on');
  $('#dpanel').innerHTML = '<div class="dim">loading…</div>';
  const f = await (await fetch('/cloud/api/farm/'+id)).json();
  const r = Math.round(f.risk||0);
  $('#dpanel').innerHTML = `
    <div style="display:flex;justify-content:space-between;align-items:flex-start">
      <div><div style="font-weight:800;font-size:18px">${f.name}</div>
      <div class="dim">${f.owner} · ${f.town}, ${f.region}</div></div>
      <button onclick="closeD()" style="margin:0">Close</button></div>
    <div class="card" style="margin-top:13px">
      <div class="lbl">6-hour incident risk</div>
      <div class="riskn" style="color:${riskColor(r)};font-size:34px;margin-top:6px">${riskText(f.risk||0)}%</div>
      <div class="bar"><i style="width:${Math.min(100,r)}%;background:${riskColor(r)}"></i></div>
      ${(f.drivers||[]).map(d=>`<div style="margin-top:7px;font-size:12px">
        <b style="font-family:var(--mono)">${d.factor}</b>
        <span class="dim"> — ${d.share}% of the signal, now ${d.value}</span></div>`).join('')}
      ${(f.forecast||[]).map(x=>`<div class="fc">▸ ${x.metric.toUpperCase()} ${x.text}</div>`).join('')}
    </div>
    <div class="card" style="margin-top:12px">
      <div class="lbl">Daily history (stored in the cloud)</div>
      <table><tr><th>date</th><th>NH₃ avg</th><th>NH₃ max</th><th>T max</th>
        <th>CH₄ max</th><th>alerts</th><th>kWh saved</th></tr>
      ${(f.daily||[]).slice().reverse().map(d=>`<tr><td>${d.date}</td><td>${d.nh3_avg}</td>
        <td>${d.nh3_max}</td><td>${d.temp_max}</td><td>${d.gas_max}</td>
        <td class="${d.alerts?'alert':''}">${d.alerts}</td><td>${d.kwh_saved}</td></tr>`).join('')}
      </table></div>
    <div class="card" style="margin-top:12px">
      <div class="lbl">Recent events</div>
      <table>${(f.events||[]).slice(0,25).map(e=>`<tr><td>${(e.ts||'').slice(5,16).replace('T',' ')}</td>
        <td class="${e.sev}">${e.sev}</td><td>${(e.type||'').replace(/_/g,' ')}</td></tr>`).join('')}
      </table></div>`;
}
function closeD(){ $('#drawer').classList.remove('on'); }
document.addEventListener('keydown',e=>{ if(e.key=='Escape') closeD(); });

tick(); setInterval(tick, 4000);
</script></body></html>"""
