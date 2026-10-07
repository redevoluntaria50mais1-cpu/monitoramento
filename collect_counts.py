#!/usr/bin/env python3
"""Snapshot (a cada execução) do total acumulado de cada hashtag, TikTok e Instagram.
Roda no GitHub Actions a cada 2h. Token vem de APIFY_TOKEN (secret). Grava counts_history.json e counts.js."""
import os, sys, json, urllib.request, datetime as dt

TOKEN = os.environ["APIFY_TOKEN"]
TAGS = {  # mesmo nº e tipo de hashtags dos dois lados
  "lula":      ["lula", "lula13", "forabolsonaro"],
  "bolsonaro": ["bolsonaro", "bolsonaro22", "forapt"],
}
ALL = [t for ts in TAGS.values() for t in ts]
SIDE = {t: s for s, ts in TAGS.items() for t in ts}
PLAT = {
  "tiktok":    dict(actor="funny_ground~tiktok-hashtag-stats", inp={"hashtags": ALL},
                    name="hashtag", posts="video_count", views="view_count"),
  "instagram": dict(actor="leadsbrary~instagram-hashtag-stats", inp={"hashtags": ALL, "includeTopPosts": False},
                    name="hashtag", posts="mediaCount", views=None),
}

def run(actor, payload):
    url = f"https://api.apify.com/v2/acts/{actor}/run-sync-get-dataset-items?token={TOKEN}"
    req = urllib.request.Request(url, json.dumps(payload).encode(), {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=900) as r: return json.load(r)

hist = json.load(open("counts_history.json")) if os.path.exists("counts_history.json") else {}
ts = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%MZ")
added = 0
for plat, cfg in PLAT.items():
    try: items = run(cfg["actor"], cfg["inp"])
    except Exception as e: print("ERRO", plat, e); continue
    for it in items:
        tag = str(it.get(cfg["name"], "")).lower().lstrip("#")
        if tag not in SIDE: continue
        p = it.get(cfg["posts"]); v = it.get(cfg["views"]) if cfg["views"] else None
        print(plat, SIDE[tag], tag, "posts:", p, "views:", v)
        if p is None and v is None: continue
        hist[f"{ts}|{plat}|{SIDE[tag]}|{tag}"] = {"ts": ts, "platform": plat, "side": SIDE[tag], "tag": tag, "posts": p or 0, "views": v or 0}
        added += 1
if added == 0:
    print("Nenhum dado coletado; nada gravado."); sys.exit(1)
json.dump(hist, open("counts_history.json", "w"), ensure_ascii=False)
rows = sorted(hist.values(), key=lambda r: (r["ts"], r["platform"], r["side"], r["tag"]))
open("counts.js", "w").write("window.COUNTS=" + json.dumps(rows, ensure_ascii=False) + ";")
print("ok:", added, "linhas novas;", len(rows), "no total")
