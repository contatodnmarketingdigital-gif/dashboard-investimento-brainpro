#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Sincronia diária: puxa o histórico da PLANILHA MESTRE (Google Sheets) via o
App da Web do Apps Script (endpoint ?tipo=historico) e grava historico_planilha.json.
Roda no GitHub Actions (servidor), sem cookies/conta — usa a URL limpa /exec.

Fonte da verdade = a planilha. O Apps Script (lerHistorico) lê as abas
PERFORMANCE MENSAL / POR PRODUTO / KPIs / VENDAS diárias e devolve o JSON pronto.

Segurança: se a busca falhar OU vier claramente vazia/inconsistente,
NÃO sobrescreve o arquivo existente (mantém o último bom)."""
import json, sys, datetime, urllib.request, urllib.error

ARQ = "historico_planilha.json"
BASE = "receita_greenn.json"          # de onde tiramos a webapp_url
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")


def carregar(arq):
    try:
        return json.load(open(arq, encoding="utf-8"))
    except Exception:
        return {}


atual = carregar(ARQ)
base = carregar(BASE)
raiz = (base.get("webapp_url") or "").strip()
if not raiz:
    print("sem webapp_url em receita_greenn.json — nada a fazer.", file=sys.stderr)
    sys.exit(0)

url = raiz + ("&" if "?" in raiz else "?") + "tipo=historico"


def buscar(u):
    req = urllib.request.Request(u, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=90) as r:
        return json.loads(r.read().decode("utf-8"))


try:
    d = buscar(url)
except urllib.error.HTTPError as he:
    print(f"HTTP {he.code} ao buscar histórico. Mantendo arquivo atual.", file=sys.stderr)
    sys.exit(0)
except Exception as e:
    print(f"aviso: falha ao buscar histórico ({e}). Mantendo arquivo atual.", file=sys.stderr)
    sys.exit(0)

if not isinstance(d, dict):
    print("resposta não é um objeto JSON — mantendo arquivo atual.", file=sys.stderr)
    sys.exit(0)

# --- Sanidade: precisa ter os blocos mensais preenchidos ---
inv = d.get("investimento_mensal") or {}
fat = d.get("faturamento_mensal") or {}
tot_fat = sum(float(x) for x in fat.values()) if fat else 0.0
if not inv or not fat or tot_fat < 1000:
    print(f"ATENÇÃO: histórico veio vazio/inconsistente (fat total {tot_fat:.2f}) — "
          "mantendo historico_planilha.json existente.", file=sys.stderr)
    sys.exit(0)

# --- Merge defensivo: começa do que veio da planilha, e preserva quaisquer
#     chaves que existiam localmente e que o endpoint por acaso não trouxe. ---
novo = dict(atual)          # base = o que já tínhamos
novo.update(d)              # sobrepõe com o fresco da planilha
if not novo.get("atualizado"):
    novo["atualizado"] = datetime.date.today().isoformat()

json.dump(novo, open(ARQ, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
n_meses = len(fat)
print(f"historico_planilha.json atualizado a partir da planilha: "
      f"faturamento R$ {tot_fat:,.2f} em {n_meses} meses (atualizado {novo.get('atualizado')}).")
