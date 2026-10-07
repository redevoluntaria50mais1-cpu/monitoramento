#!/usr/bin/env python3
"""Painel de perfis (fase 1: Instagram). A cada execução lê os posts recentes de cada perfil e calcula o
ENGAJAMENTO NOVO desde a coleta anterior (curtidas + comentários), post a post. Também guarda seguidores.
Uso:  export APIFY_TOKEN=...
      python3 collect_panel.py --probe   # mostra quais perfis foram encontrados e seguidores, sem gravar
      python3 collect_panel.py           # coleta e acumula em panel_history.json / panel_state.json / panel.js
Handles abaixo são os mais prováveis, NÃO confirmados: o --probe lista os que não voltaram (MISSING)."""
import os, sys, json, urllib.request, datetime as dt

TOKEN = os.environ["APIFY_TOKEN"]
POSTS_PER_PROFILE = 12          # posts recentes lidos por perfil (controle de custo)
RECENT_HOURS = 24               # post "novo" só conta se foi publicado nas últimas 24h na 1a vez que aparece
PANEL = {  # mesmo nº de perfis nos dois lados
  "lula": {
    "lulaoficial": "Lula", "janjalula": "Janja", "fernandohaddadoficial": "Fernando Haddad", "gleisihoffmann": "Gleisi Hoffmann",
    "guilhermeboulos.oficial": "Guilherme Boulos", "hilton_erika": "Erika Hilton", "andrejanones": "André Janones",
    "anaelisast": "Ana Elisa", "ptbrasil": "PT",
  },
  "bolsonaro": {
    "flaviobolsonaro": "Flávio Bolsonaro", "jairmessiasbolsonaro": "Jair Bolsonaro", "michellebolsonaro": "Michelle Bolsonaro",
    "bolsonarosp": "Eduardo Bolsonaro", "nikolasferreiradm": "Nikolas Ferreira", "sargentofahur": "Sargento Fahur",
    "lucaspavanato": "Lucas Pavanato", "tarcisiogdf": "Tarcísio de Freitas", "plnacional22": "PL",
  },
}
SIDE = {u: s for s, d in PANEL.items() for u in d}
NAME = {u: n for d in PANEL.values() for u, n in d.items()}

def run(actor, payload):
    url = f"https://api.apify.com/v2/acts/{actor}/run-sync-get-dataset-items?token={TOKEN}"
    req = urllib.request.Request(url, json.dumps(payload).encode(), {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=900) as r: return json.load(r)

def parse_ts(s):
    try: return dt.datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except Exception: return None

probe = "--probe" in sys.argv
now = dt.datetime.now(dt.timezone.utc); ts = now.strftime("%Y-%m-%dT%H:%MZ")
state = json.load(open("panel_state.json")) if os.path.exists("panel_state.json") else {}
hist = json.load(open("panel_history.json")) if os.path.exists("panel_history.json") else {}
posts_log = json.load(open("posts_log.json")) if os.path.exists("posts_log.json") else {}
first_run = not state

items = run("apify~instagram-profile-scraper", {"usernames": list(SIDE)})
got = {str(it.get("username", "")).lower(): it for it in items}
missing = [u for u in SIDE if u.lower() not in got]
if probe:
    json.dump(items[:2], open("probe_panel.json", "w"), ensure_ascii=False, indent=1, default=str)
for u in SIDE:
    it = got.get(u.lower())
    if not it: continue
    posts = (it.get("latestPosts") or [])[:POSTS_PER_PROFILE]
    new_eng = 0; new_posts = 0; engs = []
    for p in posts:
        pid = str(p.get("id") or p.get("shortCode") or "")
        if not pid: continue
        eng = max(0, p.get("likesCount") or 0) + max(0, p.get("commentsCount") or 0)
        engs.append(eng)
        if not probe:
            posts_log[f"instagram|{pid}"] = {"id": pid, "platform": "instagram", "profile": NAME[u], "side": SIDE[u], "ts": p.get("timestamp"),
                "caption": (p.get("caption") or "")[:500], "eng": eng,
                "url": p.get("url") or (f"https://www.instagram.com/p/{p.get('shortCode')}/" if p.get("shortCode") else "")}
        key = f"instagram|{pid}"; prev = state.get(key)
        t = parse_ts(p.get("timestamp"))
        if prev is not None:
            new_eng += max(0, eng - prev)
        elif not first_run and t and (now - t).total_seconds() <= RECENT_HOURS * 3600:
            new_eng += eng; new_posts += 1
        if not probe: state[key] = eng
    fol = it.get("followersCount") or 0
    sus = "  <-- SUSPEITO (poucos seguidores/sem posts: handle errado?)" if fol < 10000 or not posts else ""
    print(f"{SIDE[u]:10} {NAME[u]:20} seguidores={fol:>10,} posts_lidos={len(posts)} media_eng/post={round(sum(engs)/len(engs)) if engs else 0:,} eng_novo={new_eng} posts_novos={new_posts}{sus}")
    if not probe:
        hist[f"{ts}|instagram|{u}"] = {"ts": ts, "platform": "instagram", "side": SIDE[u], "profile": NAME[u],
                                       "followers": fol, "avg_eng": round(sum(engs)/len(engs)) if engs else 0, "new_posts": new_posts, "new_eng": new_eng, "baseline": first_run}
if missing: print("MISSING (handle não encontrado, corrija em PANEL):", ", ".join(missing))
if probe: sys.exit(0)
if first_run: print("1a coleta: apenas base registrada; engajamento novo começa na próxima rodada.")
cut = now - dt.timedelta(days=14)   # mantém só posts dos últimos 14 dias no log de assuntos
posts_log = {k: v for k, v in posts_log.items() if (parse_ts(v.get("ts")) or now) >= cut}
json.dump(posts_log, open("posts_log.json", "w"), ensure_ascii=False)
open("posts.js", "w").write("window.POSTS=" + json.dumps(list(posts_log.values()), ensure_ascii=False) + ";")
json.dump(state, open("panel_state.json", "w")); json.dump(hist, open("panel_history.json", "w"), ensure_ascii=False)
rows = sorted(hist.values(), key=lambda r: (r["ts"], r["side"], r["profile"]))
open("panel.js", "w").write("window.PANEL=" + json.dumps(rows, ensure_ascii=False) + ";")
print("ok:", len(rows), "linhas")
