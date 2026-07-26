#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Puxa a receita agregada (webhooks Greenn/Eduzz/Voomp) do App da Web do Apps Script
e atualiza receita_greenn.json. Roda no GitHub Actions (servidor), sem cookies/conta,
então usa a URL limpa /exec sem problema de multi-conta.
Seguranca: se a busca falhar ou vier vazia, NAO sobrescreve o arquivo existente."""
import json, sys, datetime, urllib.request, urllib.error

ARQ = "receita_greenn.json"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")

def carregar():
    try:
        return json.load(open(ARQ, encoding="utf-8"))
    except Exception:
        return {}

base = carregar()
url = (base.get("webapp_url") or "").strip()
if not url:
    print("sem webapp_url em receita_greenn.json — nada a fazer.", file=sys.stderr)
    sys.exit(0)

def buscar(u):
    req = urllib.request.Request(u, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=90) as r:
        return json.loads(r.read().decode("utf-8"))

try:
    d = buscar(url)
except urllib.error.HTTPError as he:
    # o /exec faz redirect para googleusercontent; urllib segue sozinho. Se cair aqui, loga.
    print(f"HTTP {he.code} ao buscar receita. Mantendo arquivo atual.", file=sys.stderr)
    sys.exit(0)
except Exception as e:
    print(f"aviso: falha ao buscar receita ({e}). Mantendo arquivo atual.", file=sys.stderr)
    sys.exit(0)

pmt = d.get("por_mes_total") or {}
pmp = d.get("por_mes_produto") or {}

# normaliza rótulos das classes do webhook -> rótulos de exibição do dashboard
LBL = {"tDCS": "tDCS", "Vagal": "Vagal", "Pos": "Pós-Graduação",
       "NeuroApp": "Aplicativo", "TEA": "TEA", "Outros": "Outros"}
def norm_prod(month_map):
    o = {}
    for k, v in (month_map or {}).items():
        lab = LBL.get(k, k)
        o[lab] = round(o.get(lab, 0) + float(v), 2)
    return o
pmp = {m: norm_prod(v) for m, v in pmp.items()}
if not pmt:
    print("ATENCAO: receita vazia do App da Web — mantendo receita_greenn.json existente.", file=sys.stderr)
    sys.exit(0)

# Merge por mês: só atualiza um mês se o webhook tiver MAIS receita que a base
# (preserva os números reais já lançados; deixa crescer com vendas novas).
mt = dict(base.get("por_mes_total", {}))
mp = dict(base.get("por_mes_produto", {}))
for m, v in pmt.items():
    v = round(float(v), 2)
    if v >= float(mt.get(m, 0)):
        mt[m] = v
        if m in pmp:
            mp[m] = pmp[m]
base["por_mes_total"] = mt
base["por_mes_produto"] = mp
base["total_ano"] = round(sum(float(x) for x in mt.values()), 2)
base["n_vendas"] = d.get("n_vendas", base.get("n_vendas", 0))
base["atualizado"] = d.get("atualizado", datetime.date.today().isoformat())

json.dump(base, open(ARQ, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print(f"receita_greenn.json atualizado: total R$ {base['total_ano']:,.2f} em {len(pmt)} meses")
