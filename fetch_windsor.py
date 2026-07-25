#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Puxa o investimento diario da Meta (Facebook Ads) da API do Windsor e grava data.json.
Requer a variavel de ambiente WINDSOR_API_KEY (secret no GitHub).
Usa /all + date_preset=this_year e filtra datasource=facebook.
Seguranca: se a busca voltar vazia (erro/sem dados), NAO sobrescreve o data.json."""
import os, json, sys, datetime, urllib.request, urllib.parse, urllib.error

KEY = os.environ.get("WINDSOR_API_KEY", "").strip()
if not KEY:
    print("ERRO: defina o secret WINDSOR_API_KEY", file=sys.stderr); sys.exit(1)

YEAR = str(os.environ.get("ANO", datetime.date.today().year))
today = datetime.date.today()

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")

def fetch(preset):
    q = urllib.parse.urlencode({
        "api_key": KEY,
        "date_preset": preset,
        "fields": "date,datasource,campaign,spend",
    }, safe=",")
    url = "https://connectors.windsor.ai/all?" + q
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept": "application/json",
    })
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            d = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as he:
        body = ""
        try:
            body = he.read().decode("utf-8", "replace")[:400]
        except Exception:
            pass
        print(f"HTTP {he.code} do Windsor. Corpo: {body}", file=sys.stderr)
        raise
    return d.get("data") or d.get("result") or d.get("results") or []

recs = {}
try:
    for row in fetch("this_year"):
        if str(row.get("datasource", "")).lower() != "facebook":
            continue
        date = str(row.get("date") or "")
        if not date.startswith(YEAR):
            continue
        sp = float(row.get("spend") or 0)
        if sp <= 0:
            continue
        recs[(date, row.get("campaign"))] = sp
except Exception as e:
    print(f"aviso: busca this_year falhou: {e}", file=sys.stderr)

records = [{"date": k[0], "campaign": k[1], "spend": v} for k, v in recs.items() if k[0]]
records.sort(key=lambda r: r["date"])

if not records:
    print("ATENCAO: nenhuma linha retornada — mantendo data.json existente (nao sobrescrevo).", file=sys.stderr)
    sys.exit(0)

out = {"atualizado": today.isoformat(), "records": records}
json.dump(out, open("data.json", "w", encoding="utf-8"), ensure_ascii=False)
print(f"data.json: {len(records)} registros ate {today.isoformat()}")
