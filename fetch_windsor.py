#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Puxa o investimento diario da Meta (Facebook Ads) da API do Windsor e grava data.json.
Requer a variavel de ambiente WINDSOR_API_KEY (configurada como secret no GitHub)."""
import os, json, sys, datetime, urllib.request, urllib.parse

KEY = os.environ.get("WINDSOR_API_KEY", "").strip()
if not KEY:
    print("ERRO: defina o secret WINDSOR_API_KEY", file=sys.stderr); sys.exit(1)

YEAR = int(os.environ.get("ANO", datetime.date.today().year))
today = datetime.date.today()

def fetch(dfrom, dto):
    q = urllib.parse.urlencode({
        "api_key": KEY, "date_from": dfrom, "date_to": dto,
        "fields": "date,campaign,spend", "filter[spend][gt]": "0",
    })
    url = "https://connectors.windsor.ai/facebook?" + q
    with urllib.request.urlopen(url, timeout=120) as r:
        d = json.loads(r.read().decode("utf-8"))
    return d.get("data") or d.get("result") or d.get("results") or []

recs = {}
m = 1
while m <= 12:
    dfrom = f"{YEAR}-{m:02d}-01"
    last = 28
    for dd in (31, 30, 29, 28):
        try:
            datetime.date(YEAR, m, dd); last = dd; break
        except ValueError:
            continue
    dto = f"{YEAR}-{m:02d}-{last:02d}"
    if datetime.date(YEAR, m, 1) > today:
        break
    try:
        for row in fetch(dfrom, dto):
            sp = float(row.get("spend") or 0)
            if sp <= 0: continue
            recs[(row.get("date"), row.get("campaign"))] = sp
    except Exception as e:
        print(f"aviso: mes {m} falhou: {e}", file=sys.stderr)
    m += 1

records = [{"date": k[0], "campaign": k[1], "spend": v} for k, v in recs.items() if k[0]]
records.sort(key=lambda r: r["date"])
out = {"atualizado": today.isoformat(), "records": records}
json.dump(out, open("data.json", "w", encoding="utf-8"), ensure_ascii=False)
print(f"data.json: {len(records)} registros ate {today.isoformat()}")
