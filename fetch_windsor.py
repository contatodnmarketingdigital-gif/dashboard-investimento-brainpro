#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Puxa o investimento diario da Meta (Facebook Ads) da API do Windsor e grava data.json.
Requer a variavel de ambiente WINDSOR_API_KEY (secret no GitHub).
Usa o endpoint /all + date_preset=this_year (o /facebook e o date_from/date_to
retornam 400 nesta conta) e filtra datasource=facebook.
Seguranca: se a busca voltar vazia (erro/sem dados), NAO sobrescreve o data.json
existente — mantem o ultimo bom."""
import os, json, sys, datetime, urllib.request, urllib.parse

KEY = os.environ.get("WINDSOR_API_KEY", "").strip()
if not KEY:
    print("ERRO: defina o secret WINDSOR_API_KEY", file=sys.stderr); sys.exit(1)

YEAR = str(os.environ.get("ANO", datetime.date.today().year))
today = datetime.date.today()

def fetch(preset):
    q = urllib.parse.urlencode({
        "api_key": KEY,
        "date_preset": preset,
        "fields": "date,datasource,campaign,spend",
    })
    url = "https://connectors.windsor.ai/all?" + q
    req = urllib.request.Request(url, headers={"User-Agent": "brainpro-dashboard/1.0"})
    with urllib.request.urlopen(req, timeout=180) as r:
        d = json.loads(r.read().decode("utf-8"))
    return d.get("data") or d.get("result") or d.get("results") or []

recs = {}
try:
    rows = fetch("this_year")
    for row in rows:
        if str(row.get("datasource", "")).lower() != "facebook":
            continue
        date = str(row.get("date") or "")
        if not date.startswith(YEAR):   # so o ano corrente
            continue
        sp = float(row.get("spend") or 0)
        if sp <= 0:
            continue
        recs[(date, row.get("campaign"))] = sp
except Exception as e:
    print(f"aviso: busca this_year falhou: {e}", file=sys.stderr)

records = [{"date": k[0], "campaign": k[1], "spend": v} for k, v in recs.items() if k[0]]
records.sort(key=lambda r: r["date"])

# SEGURANCA: so grava se veio dado. Se veio vazio, mantem o data.json atual.
if not records:
    print("ATENCAO: nenhuma linha retornada — mantendo data.json existente (nao sobrescrevo).", file=sys.stderr)
    sys.exit(0)

out = {"atualizado": today.isoformat(), "records": records}
json.dump(out, open("data.json", "w", encoding="utf-8"), ensure_ascii=False)
print(f"data.json: {len(records)} registros ate {today.isoformat()}")
