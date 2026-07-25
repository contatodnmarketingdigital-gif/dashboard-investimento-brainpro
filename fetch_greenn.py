#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Puxa a RECEITA (vendas pagas) do Greenn e agrega por mes x produto -> receita_greenn.json
API: GET https://apiadm.greenn.com.br/api/v2/sale  (Authorization: Bearer <GREENN_API_TOKEN>)
Requer env GREENN_API_TOKEN (secret no GitHub).
1a execucao imprime as CHAVES do primeiro item p/ ajustarmos os nomes de campo."""
import os, json, sys, re, datetime, urllib.request, urllib.parse, urllib.error
from collections import defaultdict

TOKEN = os.environ.get("GREENN_API_TOKEN", "").strip()
if not TOKEN:
    print("ERRO: defina o secret GREENN_API_TOKEN", file=sys.stderr); sys.exit(1)

YEAR = str(os.environ.get("ANO", datetime.date.today().year))
today = datetime.date.today()
BASE = "https://apiadm.greenn.com.br/api/v2/sale"
UA = "brainpro-dashboard/1.0"

def classify(nome):
    u = (nome or "").upper()
    if re.search(r"TDCS|TRANSCRANIANA|CORRENTE\s*CONT", u): return "tDCS"
    if re.search(r"PÓS|POS[- ]?GRAD|EXTENS[ÃA]O", u): return "Pós-Graduação"
    if re.search(r"VAGAL|VAGO", u): return "Vagal"
    if re.search(r"\bTEA\b|AUTIS|TRANSTORNO DO ESPECTRO", u): return "TEA"
    if re.search(r"\bAPP\b|APLICATIVO", u): return "App"
    return "Outros"

def money(v):
    if v is None: return 0.0
    if isinstance(v, (int, float)): return float(v)
    s = str(v).strip().replace("R$", "").replace(" ", "")
    # trata "1.234,56" e "1234.56"
    if "," in s and "." in s: s = s.replace(".", "").replace(",", ".")
    elif "," in s: s = s.replace(",", ".")
    try: return float(s)
    except: return 0.0

def get(params):
    url = BASE + "?" + urllib.parse.urlencode(params, safe=",:")
    req = urllib.request.Request(url, headers={
        "Authorization": "Bearer " + TOKEN,
        "Accept": "application/json",
        "User-Agent": UA,
    })
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as he:
        body = ""
        try: body = he.read().decode("utf-8", "replace")[:300]
        except: pass
        print(f"HTTP {he.code} do Greenn. Corpo: {body}", file=sys.stderr)
        raise

def first_list(d):
    if isinstance(d, list): return d
    for k in ("data", "sales", "results", "items"):
        if isinstance(d, dict) and isinstance(d.get(k), list): return d[k]
    return []

def pick(item, *cands):
    for c in cands:
        if c in item and item[c] not in (None, ""): return item[c]
    return None

agg = defaultdict(lambda: defaultdict(float))
diagnosed = False
page = 1
per_page = 100
total_rows = 0
while page <= 200:
    params = {
        "date_start": f"{YEAR}-01-01T00:00:00-03:00",
        "date_end": f"{today.isoformat()}T23:59:59-03:00",
        "status": "paid",
        "page": page,
        "per_page": per_page,
        "type": "paid_at",
    }
    try:
        d = get(params)
    except Exception as e:
        print(f"aviso: pagina {page} falhou: {e}", file=sys.stderr)
        break
    rows = first_list(d)
    if not rows:
        break
    if not diagnosed:
        diagnosed = True
        it = rows[0]
        print("DIAG item keys:", list(it.keys()), file=sys.stderr)
        prod = it.get("product")
        if isinstance(prod, dict):
            print("DIAG product keys:", list(prod.keys()), file=sys.stderr)
    for it in rows:
        total_rows += 1
        # nome do produto (varias possibilidades)
        prod = it.get("product")
        nome = None
        if isinstance(prod, dict):
            nome = prod.get("name") or prod.get("title")
        nome = nome or pick(it, "product_name", "productName", "offer_name", "product") or ""
        # valor (faturamento) — tentar bruto primeiro, depois liquido
        val = pick(it, "amount", "total", "value", "gross_value", "grossValue",
                   "total_value", "net_value", "netValue", "paid_value", "liquid")
        v = money(val)
        # data (pagamento)
        dt = pick(it, "paid_at", "paidAt", "payment_date", "updated_at", "created_at", "date") or ""
        m = str(dt)[:7]
        if not m.startswith(YEAR):
            continue
        agg[m][classify(nome)] += v
    if len(rows) < per_page:
        break
    page += 1

out = {"atualizado": today.isoformat(),
       "por_mes_produto": {m: {p: round(v, 2) for p, v in agg[m].items()} for m in sorted(agg)}}
if total_rows == 0:
    print("ATENCAO: nenhuma venda retornada — mantendo receita_greenn.json existente.", file=sys.stderr)
    sys.exit(0)
json.dump(out, open("receita_greenn.json", "w", encoding="utf-8"), ensure_ascii=False)
tot = sum(v for m in agg for v in agg[m].values())
print(f"receita_greenn.json: {total_rows} vendas, R$ {tot:,.2f} agregadas por mes x produto")
