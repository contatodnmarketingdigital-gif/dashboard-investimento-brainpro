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
if not pmt:
    print("ATENCAO: receita vazia do App da Web — mantendo receita_greenn.json existente.", file=sys.stderr)
    sys.exit(0)

# Atualiza apenas os campos de receita, preservando webapp_url e o resto.
base["por_mes_total"] = {m: round(float(v), 2) for m, v in pmt.items()}
base["por_mes_produto"] = pmp
base["total_ano"] = round(sum(float(v) for v in pmt.values()), 2)
base["n_vendas"] = d.get("n_vendas", base.get("n_vendas", 0))
base["atualizado"] = d.get("atualizado", datetime.date.today().isoformat())
base["fonte"] = d.get("fonte", base.get("fonte", ""))

json.dump(base, open(ARQ, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print(f"receita_greenn.json atualizado: total R$ {base['total_ano']:,.2f} em {len(pmt)} meses")
