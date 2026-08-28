#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Gera index.html do dashboard (2 abas: Mes e Ano) a partir de data.json.
data.json = {"atualizado":"YYYY-MM-DD","records":[{"date","campaign","spend"}...]}
Investimento = Meta (automatico). Receita = lancada pelo usuario (localStorage)."""
import json, re
from collections import defaultdict

PRODUCTS = ["Pós-Graduação","Recorrência Pós","TEA","tDCS","Vagal","Lançamento Vagal","App","Fotobio","Impulsionamento Estratégia Instagram","Outros"]

def classify(c):
    u = c.upper()
    if re.search(r"FOTOBIO", u): return "Fotobio"
    if re.search(r"TDCS", u): return "tDCS"
    if re.search(r"PÓS|POS-GRAD|\[POS\]", u): return "Pós-Graduação"
    if re.search(r"LAN[ÇC]AMENTO.*VAGAL|VAGAL.*LAN[ÇC]AMENTO", u): return "Lançamento Vagal"
    if re.search(r"VAGAL", u): return "Vagal"
    if re.search(r"\bTEA\b|\[TEA\]", u): return "TEA"
    if re.search(r"\bAPP\b|\[APP\]", u): return "App"
    if re.search(r"IMPULSIONAMENTO|VISITAS?\s*AO\s*PERFIL|VISITASAOPERFIL|POSTS?\s*INSTA|PERFIL\]\[POST|TRÁFEGO|TRAFEGO", u):
        return "Impulsionamento Estratégia Instagram"
    return "Outros"

def load_receita(path="receita_greenn.json"):
    """Le a receita real do Greenn (se existir) para pre-preencher o dashboard.
    Nunca falha: se o arquivo nao existir, retorna vazio."""
    try:
        r = json.load(open(path, encoding="utf-8"))
        return {
            "receitaDefault": r.get("por_mes_total", {}),
            "receitaBruto": r.get("por_mes_bruto", {}),
            "receitaProduto": r.get("por_mes_produto", {}),
            "receitaAtualizado": r.get("atualizado", ""),
            "receitaFonte": r.get("fonte", ""),
            "webappUrl": r.get("webapp_url", ""),
            "receitaDia": r.get("por_dia", {}),
            "metaDefault": r.get("meta_default", 250000),
            "supermetaDefault": r.get("supermeta_default", 300000),
        }
    except Exception:
        return {"receitaDefault": {}, "receitaProduto": {}, "receitaAtualizado": "", "receitaFonte": "", "webappUrl": "",
                "receitaDia": {}, "metaDefault": 250000, "supermetaDefault": 300000}

def load_planilha(path="historico_planilha.json"):
    """Le o historico da planilha mestre (Google Sheets), fonte de verdade do usuario."""
    try:
        return json.load(open(path, encoding="utf-8"))
    except Exception:
        return {}

def build(src="data.json", out="index.html"):
    d = json.load(open(src, encoding="utf-8"))
    recs = d["records"]; atualizado = d.get("atualizado", "")
    dd = defaultdict(float)
    for r in recs:
        dd[(r["date"], r["campaign"])] += float(r["spend"])
    # Investimento = GASTO REAL do Meta (todas as 5 contas, via Windsor).
    # Nao ajustamos mais pela planilha: a planilha estava abaixo do gasto real
    # (ex.: a conta 02-TEA nao entrava por completo). Total real ~R$ 201 mil.
    plan = load_planilha()
    rows = [(k[0], k[1], v, classify(k[1])) for k, v in dd.items()]
    ptot = defaultdict(float); mon = defaultdict(lambda: defaultdict(float)); day = defaultdict(lambda: defaultdict(float))
    for date, camp, spend, prod in rows:
        ptot[prod] += spend; mon[date[:7]][prod] += spend; day[date][prod] += spend
    months = sorted(mon); days = sorted(day)
    all_months = [f"2026-{i:02d}" for i in range(1, 13)]
    mon_map = {m: {"mes": m, **{p: round(mon[m].get(p, 0), 2) for p in PRODUCTS}, "total": round(sum(mon[m].values()), 2)} for m in months}
    monthly_full = [mon_map.get(m, {"mes": m, **{p: 0 for p in PRODUCTS}, "total": 0}) for m in all_months]
    daily = [{"data": dt, **{p: round(day[dt].get(p, 0), 2) for p in PRODUCTS}, "total": round(sum(day[dt].values()), 2)} for dt in days]
    totals = {p: round(ptot.get(p, 0), 2) for p in PRODUCTS}
    grand = round(sum(ptot.values()), 2)
    best_m = max(months, key=lambda m: sum(mon[m].values())) if months else "2026-01"
    cur_m = months[-1] if months else "2026-01"
    active = [p for p in PRODUCTS if p != "Outros" and ptot.get(p, 0) > 0]
    data = {
        "atualizado": atualizado, "products": PRODUCTS, "totals": totals, "grand": grand,
        "monthly": monthly_full, "daily": daily, "curMonth": cur_m,
        "kpis": {"total": grand, "melhor_mes": best_m,
                 "melhor_mes_valor": round(sum(mon[best_m].values()), 2) if months else 0,
                 "n_produtos": len(active), "media_diaria": round(grand / len(days), 2) if days else 0,
                 "dias": len(days), "outros": totals["Outros"]},
    }
    whook = load_receita()
    data.update(whook)
    # Faturamento = VALORES RECEBIDOS nas plataformas (webhooks Greenn/Eduzz/Voomp).
    # A planilha entra para os meses em que ela tem mais que o recebido (historico
    # que os webhooks ainda nao cobriam). Regra por mes: vence o MAIOR valor.
    if plan:
        fat_w = {k: float(v) for k, v in (whook.get("receitaDefault") or {}).items()}
        fat_p = {k: float(v) for k, v in (plan.get("faturamento_mensal") or {}).items()}
        prod_w = whook.get("receitaProduto") or {}
        prod_p = plan.get("por_produto_mes") or {}
        dia_w = whook.get("receitaDia") or {}
        dia_p = plan.get("por_dia") or {}
        fat, prod, winner = {}, {}, {}
        for m in sorted(set(fat_w) | set(fat_p)):
            vw, vp = fat_w.get(m, 0.0), fat_p.get(m, 0.0)
            if vw >= vp and vw > 0:
                winner[m] = "w"; fat[m] = round(vw, 2)
                if m in prod_w: prod[m] = prod_w[m]
            else:
                winner[m] = "p"; fat[m] = round(vp, 2)
                if m in prod_p: prod[m] = prod_p[m]
        dia = {}
        for d, v in dia_w.items():
            if winner.get(d[:7]) == "w": dia[d] = v
        for d, v in dia_p.items():
            if winner.get(d[:7]) == "p": dia[d] = v
        data["receitaDefault"] = fat
        data["receitaProduto"] = prod
        data["receitaDia"] = dia
        data["receitaFonte"] = "Valores recebidos nas plataformas (Greenn/Eduzz/Voomp); meses anteriores pela planilha mestre."
        data["receitaAtualizado"] = plan.get("atualizado") or whook.get("receitaAtualizado", "")
        data["produtoAno"] = plan.get("produto_ano", {})
    html = TEMPLATE.replace("__DATA__", json.dumps(data, ensure_ascii=False))
    open(out, "w", encoding="utf-8").write(html)
    print(f"gerado {out}: {len(rows)} registros, {len(days)} dias, total R$ {grand:,.2f}")

TEMPLATE = r'''<!DOCTYPE html>
<html lang="pt-BR" data-theme="light">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Dashboard Investimento &amp; Receita · BrainPro 2026</title>
<style>
  :root{--plane:#f9f9f7;--surface:#fcfcfb;--ink:#0b0b0b;--ink2:#52514e;--muted:#898781;
    --grid:#e1e0d9;--axis:#c3c2b7;--ring:rgba(11,11,11,.10);
    --s1:#2a78d6;--s2:#eb6834;--s3:#1baf7a;--s4:#eda100;--s5:#e87ba4;--s6:#008300;--s7:#7b61c9;--s8:#ff7a3d;--s9:#38a9d9;--sOut:#9a988f;
    --good:#006300;--bad:#c0392b;--accent:#2a78d6;}
  :root[data-theme="dark"]{--plane:#0d0d0d;--surface:#1a1a19;--ink:#fff;--ink2:#c3c2b7;--muted:#898781;
    --grid:#2c2c2a;--axis:#383835;--ring:rgba(255,255,255,.10);
    --s1:#3987e5;--s2:#d95926;--s3:#199e70;--s4:#c98500;--s5:#d55181;--s6:#008300;--s7:#9b82e0;--s8:#ff8c55;--s9:#4fb8e6;--sOut:#8a887f;
    --good:#0ca30c;--bad:#e66767;--accent:#3987e5;}
  *{box-sizing:border-box}
  body{margin:0;background:var(--plane);color:var(--ink);font-family:system-ui,-apple-system,"Segoe UI",sans-serif;-webkit-font-smoothing:antialiased;}
  .wrap{max-width:1180px;margin:0 auto;padding:24px 22px 60px;}
  header.top{display:flex;justify-content:space-between;align-items:flex-start;gap:16px;flex-wrap:wrap;margin-bottom:10px;}
  .brand{display:flex;align-items:center;gap:13px;}
  .logo{flex:none;display:block;width:52px;height:38px;}
  .bp1{color:var(--ink);font-weight:800;}
  .bp2{color:#2f86e0;font-weight:800;}
  .htail{color:var(--ink2);font-weight:500;}
  h1{font-size:22px;line-height:1.2;margin:0 0 4px;letter-spacing:-.01em;}
  .sub{color:var(--ink2);font-size:13px;margin:0;}
  .sub b{color:var(--ink);font-weight:600;}
  .toggle{border:1px solid var(--ring);background:var(--surface);color:var(--ink2);border-radius:9px;padding:8px 12px;font-size:12.5px;cursor:pointer;font-family:inherit;white-space:nowrap;}
  .toggle:hover{color:var(--ink);}
  .tabs{display:flex;gap:6px;background:var(--surface);border:1px solid var(--ring);border-radius:12px;padding:5px;width:max-content;margin:4px 0 16px;}
  .tab{border:none;background:transparent;color:var(--ink2);font-family:inherit;font-size:14px;font-weight:600;
    padding:9px 22px;border-radius:8px;cursor:pointer;}
  .tab.active{background:var(--accent);color:#fff;}
  .pill{display:inline-block;font-size:11px;padding:2px 8px;border-radius:20px;background:color-mix(in srgb,var(--good) 15%,transparent);color:var(--good);font-weight:600;}
  .kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(158px,1fr));gap:11px;margin:6px 0 8px;}
  .kpi{background:var(--surface);border:1px solid var(--ring);border-radius:13px;padding:14px 15px;}
  .kpi .lab{font-size:11px;text-transform:uppercase;letter-spacing:.05em;color:var(--muted);margin-bottom:6px;}
  .kpi .val{font-size:22px;font-weight:650;letter-spacing:-.01em;}
  .kpi .note{font-size:11.5px;color:var(--ink2);margin-top:3px;}
  .kpi .val.pos{color:var(--good);}.kpi .val.neg{color:var(--bad);}
  .card{background:var(--surface);border:1px solid var(--ring);border-radius:15px;padding:18px 18px 12px;margin-top:16px;}
  .card h2{font-size:15px;margin:0 0 2px;}
  .card p.desc{font-size:12.5px;color:var(--ink2);margin:0 0 12px;}
  .legend{display:flex;flex-wrap:wrap;gap:10px 15px;margin:2px 0 14px;}
  .lg{display:flex;align-items:center;gap:7px;font-size:12.5px;color:var(--ink2);cursor:pointer;user-select:none;}
  .lg .sw{width:12px;height:12px;border-radius:3px;flex:none;}.lg.off{opacity:.32;text-decoration:line-through;}
  svg{display:block;width:100%;height:auto;overflow:visible;}
  .ax{fill:var(--muted);font-size:11px;font-variant-numeric:tabular-nums;}
  .axl{fill:var(--ink2);font-size:11.5px;}.gl{stroke:var(--grid);stroke-width:1;}.bl{stroke:var(--axis);stroke-width:1;}
  table{border-collapse:collapse;width:100%;font-size:12.5px;font-variant-numeric:tabular-nums;}
  th,td{padding:7px 9px;text-align:right;border-bottom:1px solid var(--grid);white-space:nowrap;}
  th:first-child,td:first-child{text-align:left;font-variant-numeric:normal;}
  thead th{color:var(--muted);font-weight:600;font-size:10.5px;text-transform:uppercase;letter-spacing:.04em;}
  tbody tr:hover{background:color-mix(in srgb,var(--ink) 4%,transparent);}
  tfoot td{font-weight:650;border-top:2px solid var(--axis);border-bottom:none;}
  .pos{color:var(--good);}.neg{color:var(--bad);}
  input.rev{width:120px;text-align:right;font-family:inherit;font-size:12.5px;font-variant-numeric:tabular-nums;
    border:1px solid var(--ring);background:var(--plane);color:var(--ink);border-radius:7px;padding:6px 8px;}
  input.rev:focus{outline:2px solid var(--accent);outline-offset:-1px;border-color:transparent;}
  select.msel{font-family:inherit;font-size:14px;font-weight:600;border:1px solid var(--ring);background:var(--surface);
    color:var(--ink);border-radius:9px;padding:8px 12px;cursor:pointer;}
  .toolbar{display:flex;gap:12px;flex-wrap:wrap;align-items:center;margin:2px 0 12px;}
  .toolbar label{font-size:12.5px;color:var(--ink2);}
  .toolbar input.tax{width:66px}
  .btn{border:1px solid var(--ring);background:var(--plane);color:var(--ink2);border-radius:8px;padding:6px 11px;font-size:12px;cursor:pointer;font-family:inherit;}
  .btn:hover{color:var(--ink);}
  .revbox{display:flex;align-items:center;gap:10px;flex-wrap:wrap;background:color-mix(in srgb,var(--accent) 7%,var(--surface));
    border:1px solid color-mix(in srgb,var(--accent) 25%,transparent);border-radius:11px;padding:12px 14px;margin-bottom:4px;}
  .revbox label{font-size:13px;font-weight:600;}
  .foot{color:var(--muted);font-size:12px;margin-top:22px;line-height:1.6;}
  .note-outros{background:color-mix(in srgb,var(--s4) 12%,var(--surface));border:1px solid color-mix(in srgb,var(--s4) 40%,transparent);border-radius:11px;padding:12px 14px;font-size:12.5px;color:var(--ink2);margin-top:16px;}
  .note-outros b{color:var(--ink);}
  .hide{display:none!important;}
  .mhead{display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:10px;margin:2px 0 10px;}
  .mtoolbar{display:flex;align-items:center;gap:14px;flex-wrap:wrap;}
  .mtoolbar label{font-size:13px;color:var(--ink2);display:flex;align-items:center;gap:5px;}
  input.mini{width:92px;border:1px solid var(--ring);background:var(--surface);color:var(--ink);border-radius:7px;padding:5px 8px;font-size:13px;font-family:inherit;}
  .statuspill{font-size:13.5px;font-weight:650;padding:7px 15px;border-radius:999px;white-space:nowrap;}
  .sp-ok{background:color-mix(in srgb,#0ca30c 15%,var(--surface));color:#0a8a0a;border:1px solid color-mix(in srgb,#0ca30c 35%,transparent);}
  .sp-late{background:color-mix(in srgb,#f5a623 17%,var(--surface));color:#b9770f;border:1px solid color-mix(in srgb,#f5a623 42%,transparent);}
  :root[data-theme="dark"] .sp-ok{color:#3ad13a;} :root[data-theme="dark"] .sp-late{color:#f5b53a;}
  .lg-green{color:#0ca30c;font-weight:600;} .lg-amber{color:#e0921a;font-weight:600;}
  .tt{position:fixed;pointer-events:none;background:var(--surface);border:1px solid var(--ring);border-radius:9px;padding:9px 11px;font-size:12px;color:var(--ink);box-shadow:0 6px 22px rgba(0,0,0,.16);opacity:0;transition:opacity .09s;z-index:20;min-width:150px;}
  .tt .th{font-weight:650;margin-bottom:6px;font-size:12.5px;}
  .tt .row{display:flex;justify-content:space-between;gap:14px;line-height:1.5;}
  .tt .row .k{display:flex;align-items:center;gap:6px;color:var(--ink2);}
  .tt .row .k i{width:9px;height:9px;border-radius:2px;display:inline-block;}
</style>
</head>
<body>
<div class="wrap">
  <header class="top">
    <div class="brand">
      <svg class="logo" width="52" height="38" viewBox="0 0 52 38" aria-label="BrainPro">
        <path d="M6 33 A20 20 0 0 1 46 33" fill="none" stroke="#2a5db0" stroke-width="4.6" stroke-linecap="round"/>
        <path d="M13.5 33 A12.5 12.5 0 0 1 38.5 33" fill="none" stroke="#2f86e0" stroke-width="4.6" stroke-linecap="round"/>
        <path d="M21 33 A5 5 0 0 1 31 33" fill="none" stroke="#7ab3ec" stroke-width="4.6" stroke-linecap="round"/>
      </svg>
      <div>
        <h1><span class="bp1">Brain</span><span class="bp2">Pro</span> <span class="htail">· Corrida da Meta &amp; Faturamento 2026</span></h1>
        <p class="sub">Faturamento <b>recebido</b> das plataformas (Greenn/Eduzz/Voomp) · investimento da Meta via Windsor · <span class="pill" id="upd">atualizado</span></p>
      </div>
    </div>
    <button class="toggle" id="themeBtn">◐ Tema</button>
  </header>

  <div class="tabs">
    <button class="tab active" data-view="mes" id="tabMes">📅 Mês</button>
    <button class="tab" data-view="ano" id="tabAno">📆 Ano</button>
  </div>

  <!-- ================= VIEW MÊS ================= -->
  <div id="viewMes">
    <div class="mhead">
      <div class="mtoolbar">
        <label>Mês: <select class="msel" id="monthSel"></select></label>
        <label>Meta R$ <input class="mini" id="metaInp" inputmode="numeric"></label>
        <label>Super R$ <input class="mini" id="superInp" inputmode="numeric"></label>
      </div>
      <div id="statusPill" class="statuspill"></div>
    </div>
    <div class="kpis" id="mesKpis"></div>
    <div class="card">
      <h2>Corrida da meta — acumulado</h2>
      <p class="desc">Tracejado = onde deveríamos estar. Faturado real (área azul) vs meta e super meta.</p>
      <svg id="cCorrida" viewBox="0 0 900 380" role="img"></svg>
    </div>
    <div class="card">
      <h2>Faturamento por dia</h2>
      <p class="desc"><span class="lg-green">Verde</span> = bateu a meta do dia · <span class="lg-amber">âmbar</span> = abaixo</p>
      <svg id="cFatDia" viewBox="0 0 900 320" role="img"></svg>
    </div>
    <div class="card">
      <h2>Tráfego (Meta Ads) × Faturamento — <span id="mesTitTraf"></span></h2>
      <p class="desc">Investimento em anúncios no mês e o retorno sobre ele (ROI/ROAS). Gráfico: gasto diário por produto.</p>
      <div class="kpis" id="trafKpis"></div>
      <div class="legend" id="legendMes"></div>
      <svg id="cDailyMes" viewBox="0 0 900 300" role="img"></svg>
    </div>
    <div class="card">
      <h2>Por produto — acumulado no mês</h2>
      <p class="desc">Faturamento por produto e participação no total do mês (vem dos webhooks Greenn/Eduzz/Voomp).</p>
      <div class="kpis" id="prodTiles"></div>
    </div>
    <div class="card">
      <h2>Investido × Faturado por produto — <span id="mesTit2"></span></h2>
      <p class="desc">Investimento (Meta) e faturamento de cada produto no mês, com ROI, ROAS e lucro. "Recorrência Pós" é faturamento sem tráfego (parcelas de contratos antigos), por isso aparece sem investimento.</p>
      <div style="overflow-x:auto"><table id="tblProdMes"></table></div>
    </div>
  </div>

  <!-- ================= VIEW ANO ================= -->
  <div id="viewAno" class="hide">
    <div class="kpis" id="kpisAno"></div>
    <div class="card">
      <h2>Visão geral do ano — mês a mês</h2>
      <p class="desc">O investimento entra sozinho da Meta. A <b>receita</b> já vem preenchida com as vendas pagas do <b>Greenn</b> (valor líquido) — ROI, ROAS e lucro calculam na hora. Você pode editar qualquer mês (ex.: somar Eduzz/Voomp); o que digitar fica salvo no seu navegador e vence o valor do Greenn.</p>
      <div class="toolbar">
        <label>Imposto sobre investimento: <input class="rev tax" id="taxRate" type="number" step="0.01" value="13.83"> %</label>
        <button class="btn" id="expBtn">⬇ Baixar receita (backup)</button>
        <button class="btn" id="impBtn">⬆ Restaurar receita</button>
        <input type="file" id="impFile" accept="application/json" style="display:none">
      </div>
      <div style="overflow-x:auto"><table id="tblGeral"></table></div>
    </div>
    <div class="card">
      <h2>Investimento × Receita por produto — ano</h2>
      <p class="desc">Total do ano: receita (Greenn) e investimento por produto, com ROI, ROAS e lucro de cada um.</p>
      <div style="overflow-x:auto"><table id="tblProdAno"></table></div>
    </div>
    <div class="card">
      <h2>Investimento por mês e produto</h2>
      <p class="desc">Barras empilhadas — cada cor é um produto.</p>
      <div class="legend" id="legendAno"></div>
      <svg id="cMonthly" viewBox="0 0 900 380" role="img"></svg>
    </div>
    <div class="card">
      <h2>Investimento diário (ano)</h2>
      <p class="desc">Área empilhada por produto ao longo de 2026.</p>
      <svg id="cDaily" viewBox="0 0 900 340" role="img"></svg>
    </div>
    <div class="card">
      <h2>Total por produto no ano</h2>
      <svg id="cProd" viewBox="0 0 900 300" role="img"></svg>
    </div>
    <div class="note-outros" id="noteOutros"></div>
  </div>

  <p class="foot">
    Investimento = valor bruto da Meta; "Invest. c/ imposto" aplica a alíquota (padrão 13,83%). ROI = (Receita − Invest. c/ imposto) / Invest. c/ imposto · ROAS = Receita / Invest. c/ imposto.<br>
    "Outros" = campanhas fora dos 6 produtos (Binaurais, Workshop, eventos, testes). Investimento atualiza sozinho todo dia; a receita fica salva no seu navegador — use "Baixar receita" para backup.
  </p>
</div>
<div class="tt" id="tt"></div>
<script>
const DATA = __DATA__;
const PRODUCTS = DATA.products;
const COLORVAR = {"Pós-Graduação":"--s1","Recorrência Pós":"--s7","TEA":"--s2","tDCS":"--s3","Vagal":"--s4","Lançamento Vagal":"--s8","App":"--s5","Fotobio":"--s9","Impulsionamento Estratégia Instagram":"--s6","Outros":"--sOut"};
const SHORT = {"Pós-Graduação":"Pós-Graduação","Recorrência Pós":"Recorrência Pós","TEA":"TEA","tDCS":"tDCS","Vagal":"Vagal","Lançamento Vagal":"Lanç. Vagal","App":"App","Fotobio":"Fotobio","Impulsionamento Estratégia Instagram":"Impulsionamento","Outros":"Outros"};
const MES = {"2026-01":"Janeiro","2026-02":"Fevereiro","2026-03":"Março","2026-04":"Abril","2026-05":"Maio","2026-06":"Junho","2026-07":"Julho","2026-08":"Agosto","2026-09":"Setembro","2026-10":"Outubro","2026-11":"Novembro","2026-12":"Dezembro"};
const MESC = {"2026-01":"Jan","2026-02":"Fev","2026-03":"Mar","2026-04":"Abr","2026-05":"Mai","2026-06":"Jun","2026-07":"Jul","2026-08":"Ago","2026-09":"Set","2026-10":"Out","2026-11":"Nov","2026-12":"Dez"};
const cssv=v=>getComputedStyle(document.documentElement).getPropertyValue(v).trim();
const col=p=>cssv(COLORVAR[p]);
const brl=n=>"R$ "+Number(n||0).toLocaleString("pt-BR",{minimumFractionDigits:2,maximumFractionDigits:2});
const brlk=n=>"R$ "+Number(n||0).toLocaleString("pt-BR",{maximumFractionDigits:0});
const SVGNS="http://www.w3.org/2000/svg";
const el=(t,a={})=>{const e=document.createElementNS(SVGNS,t);for(const k in a)e.setAttribute(k,a[k]);return e;};
const tt=document.getElementById("tt");
let hidden=new Set(), hiddenMes=new Set(), curView="mes", selMonth=DATA.curMonth;

const LS="brainpro_receita_2026";
function loadRev(){try{return JSON.parse(localStorage.getItem(LS)||"{}")}catch(e){return {}}}
function saveRev(o){try{localStorage.setItem(LS,JSON.stringify(o))}catch(e){}}
let REV=loadRev();
const RDEF=DATA.receitaDefault||{};              /* receita SEM TAXAS (liquido, apos comissoes) */
const RBRUTO=DATA.receitaBruto||{};              /* faturamento BRUTO (cheio, antes das comissoes) */
const RPROD=DATA.receitaProduto||{};
/* faturamento bruto do mes: usa o bruto informado; senao cai no valor efetivo (liquido) */
function brutoVal(m){return RBRUTO[m]!=null?(+RBRUTO[m]||0):revVal(m);}
function taxRate(){const v=parseFloat(document.getElementById("taxRate").value);return isNaN(v)?0:v/100;}
function parseNum(s){return parseFloat(String(s).replace(/\./g,'').replace(',','.').trim())||0;}
/* valor efetivo da receita do mes: o que voce digitou vence; senao usa o real do Greenn */
function revVal(m){return REV[m]!=null?parseNum(REV[m]):(+RDEF[m]||0);}
function revShow(m){return REV[m]!=null?REV[m]:(RDEF[m]!=null?(+RDEF[m]).toLocaleString('pt-BR',{minimumFractionDigits:2,maximumFractionDigits:2}):"");}
function revIsAuto(m){return REV[m]==null&&RDEF[m]!=null;}
/* mapeia as classes de receita (Greenn/webhooks) para os produtos do dashboard */
const REV2P={tDCS:"tDCS",Vagal:"Vagal",Pos:"Pós-Graduação",NeuroApp:"App",TEA:"TEA",Outros:"Outros",
  "Pós-Graduação":"Pós-Graduação","Recorrência Pós":"Recorrência Pós","Aplicativo":"App","App":"App",
  "Lançamento Vagal":"Lançamento Vagal","Fotobio":"Fotobio"};
function revProdMonth(m){const o={};const src=RPROD[m]||{};for(const k in src){const p=REV2P[k]||"Outros";o[p]=(o[p]||0)+(+src[k]||0);}return o;}
function revProdYear(){const o={};for(const m in RPROD){const r=revProdMonth(m);for(const p in r)o[p]=(o[p]||0)+r[p];}return o;}
function prodRoiRows(invByProd,recByProd){const tax=taxRate();
  const set=new Set([...Object.keys(invByProd),...Object.keys(recByProd)]);
  const order=PRODUCTS.filter(p=>set.has(p));
  return order.map(p=>{const inv=+invByProd[p]||0,invT=inv*(1+tax),rec=+recByProd[p]||0;
    return {p,inv,invT,rec,roi:invT>0?(rec-invT)/invT:null,roas:invT>0?rec/invT:null,lucro:rec-invT};});}
function prodTable(id,rows,showRoas){const t=document.getElementById(id);if(!t)return;
  const head=`<thead><tr><th>Produto</th><th>Investimento</th><th>Invest. c/ imp.</th><th>Receita</th><th>ROI</th>${showRoas?"<th>ROAS</th>":""}<th>Lucro</th></tr></thead>`;
  let sInv=0,sInvT=0,sRec=0;
  const body=rows.map(r=>{sInv+=r.inv;sInvT+=r.invT;sRec+=r.rec;
    const roi=r.rec>0&&r.roi!=null?`<span class="${r.roi>=0?'pos':'neg'}">${(r.roi*100).toFixed(1)}%</span>`:"—";
    const roas=r.rec>0&&r.roas!=null?r.roas.toFixed(2)+"x":"—";
    const lucro=r.rec>0?`<span class="${r.lucro>=0?'pos':'neg'}">${brlk(r.lucro)}</span>`:(r.inv>0?`<span class="neg">${brlk(r.lucro)}</span>`:"—");
    return `<tr><td>${SHORT[r.p]||r.p}</td><td>${brlk(r.inv)}</td><td>${brlk(r.invT)}</td><td>${r.rec>0?brlk(r.rec):"—"}</td><td>${roi}</td>${showRoas?`<td>${roas}</td>`:""}<td>${lucro}</td></tr>`;}).join("");
  const tax=taxRate(),sRoi=sInvT>0?(sRec-sInvT)/sInvT:null,sRoas=sInvT>0?sRec/sInvT:null,sLuc=sRec-sInvT;
  const froi=sRec>0&&sRoi!=null?`<span class="${sRoi>=0?'pos':'neg'}">${(sRoi*100).toFixed(1)}%</span>`:"—";
  const foot=`<tfoot><tr><td>Total</td><td>${brlk(sInv)}</td><td>${brlk(sInvT)}</td><td>${sRec>0?brlk(sRec):"—"}</td><td>${froi}</td>${showRoas?`<td>${sRec>0&&sRoas!=null?sRoas.toFixed(2)+"x":"—"}</td>`:""}<td>${sRec>0?`<span class="${sLuc>=0?'pos':'neg'}">${brlk(sLuc)}</span>`:"—"}</td></tr></tfoot>`;
  t.innerHTML=head+"<tbody>"+(body||`<tr><td colspan="7" style="text-align:center;color:var(--ink2)">Sem dados</td></tr>`)+"</tbody>"+foot;}
function prodMesTable(){const r=DATA.monthly.find(x=>x.mes===selMonth)||{};const inv={};PRODUCTS.forEach(p=>{if(r[p]>0)inv[p]=r[p];});
  prodTable("tblProdMes",prodRoiRows(inv,revProdMonth(selMonth)),true);
  const el2=document.getElementById("mesTit2");if(el2)el2.textContent=MES[selMonth]+" 2026";}
function prodAnoTable(){
  const pa=DATA.produtoAno||{};
  if(Object.keys(pa).length){const tax=taxRate();
    const rows=Object.keys(pa).sort((a,b)=>(+pa[b].fat||0)-(+pa[a].fat||0)).map(p=>{
      const inv=+pa[p].inv||0,invT=inv*(1+tax),rec=+pa[p].fat||0;
      return {p,inv,invT,rec,roi:invT>0?(rec-invT)/invT:null,roas:invT>0?rec/invT:null,lucro:rec-invT};});
    prodTable("tblProdAno",rows,true);return;}
  const inv={};PRODUCTS.forEach(p=>{if(DATA.totals[p]>0)inv[p]=DATA.totals[p];});
  prodTable("tblProdAno",prodRoiRows(inv,revProdYear()),true);}

function showTT(html,x,y){tt.innerHTML=html;tt.style.opacity=1;let nx=x+14,ny=y+14;const r=tt.getBoundingClientRect();
  if(nx+r.width>window.innerWidth-8)nx=x-r.width-14;if(ny+r.height>window.innerHeight-8)ny=y-r.height-14;
  tt.style.left=nx+"px";tt.style.top=ny+"px";}
const hideTT=()=>tt.style.opacity=0;
function niceTicks(max,count){const raw=(max||1)/count;const mag=Math.pow(10,Math.floor(Math.log10(raw||1)));
  let norm=raw/mag,step;if(norm<1.5)step=1;else if(norm<3)step=2;else if(norm<7)step=5;else step=10;
  step*=mag;const top=Math.ceil((max||1)/step)*step;const out=[];for(let v=0;v<=top+1e-6;v+=step)out.push(Math.round(v));return out;}

function computeMonth(mk){
  const r=DATA.monthly.find(x=>x.mes===mk)||{total:0};
  const inv=r.total,tax=taxRate(),invT=inv*(1+tax),rec=revVal(mk);
  return {inv,invT,rec,roi:invT>0?(rec-invT)/invT:null,roas:invT>0?rec/invT:null,lucro:rec-invT,row:r};
}
function yearTotals(){let inv=0,invT=0,rec=0;DATA.monthly.forEach(r=>{const c=computeMonth(r.mes);inv+=c.inv;invT+=c.invT;rec+=c.rec;});
  return {inv,invT,rec,roi:invT>0?(rec-invT)/invT:null,roas:invT>0?rec/invT:null,lucro:rec-invT};}

/* ===== KPIs ===== */
function kpiCard(l,v,n,c){return `<div class="kpi"><div class="lab">${l}</div><div class="val ${c||''}">${v}</div><div class="note">${n}</div></div>`;}
function kpisMes(){
  const c=computeMonth(selMonth);
  const roi=c.roi==null?"—":(c.roi*100).toFixed(1)+"%", roas=c.roas==null?"—":c.roas.toFixed(2)+"x";
  document.getElementById("kpisMes").innerHTML=[
    kpiCard("Investimento",brl(c.inv),"c/ imposto "+brl(c.invT),""),
    kpiCard("Receita",brl(c.rec),c.rec>0?"faturamento informado":"digite abaixo",""),
    kpiCard("ROI",c.rec>0?roi:"—","sobre invest. c/ imposto",c.rec>0&&c.roi!=null?(c.roi>=0?"pos":"neg"):""),
    kpiCard("ROAS",c.rec>0?roas:"—","receita ÷ invest. c/ imp.",""),
    kpiCard("Lucro",c.rec>0?brl(c.lucro):"—","receita − invest. c/ imp.",c.rec>0?(c.lucro>=0?"pos":"neg"):""),
  ].join("");
}
function kpisAno(){
  const t=yearTotals(),k=DATA.kpis;
  const roi=t.roi==null?"—":(t.roi*100).toFixed(1)+"%",roas=t.roas==null?"—":t.roas.toFixed(2)+"x";
  document.getElementById("kpisAno").innerHTML=[
    kpiCard("Investimento 2026",brl(t.inv),k.dias+" dias · média "+brl(k.media_diaria)+"/dia",""),
    kpiCard("Receita lançada",brl(t.rec),t.rec>0?"faturamento informado":"digite na tabela",""),
    kpiCard("ROI",t.rec>0?roi:"—","sobre invest. c/ imposto",t.rec>0&&t.roi!=null?(t.roi>=0?"pos":"neg"):""),
    kpiCard("ROAS",t.rec>0?roas:"—","receita ÷ invest. c/ imp.",""),
    kpiCard("Lucro",t.rec>0?brl(t.lucro):"—","receita − invest. c/ imp.",t.rec>0?(t.lucro>=0?"pos":"neg"):""),
  ].join("");
}

/* ===== MÊS: seletor, receita ===== */
function fillMonthSel(){
  const s=document.getElementById("monthSel");
  const withData=DATA.monthly.filter(r=>r.total>0).map(r=>r.mes);
  const list=withData.length?withData:["2026-01"];
  s.innerHTML=list.map(m=>`<option value="${m}"${m===selMonth?" selected":""}>${MES[m]} 2026</option>`).join("");
  if(!list.includes(selMonth)){selMonth=list[list.length-1];s.value=selMonth;}
}
function syncRevMes(){
  const inp=document.getElementById("revMes");
  inp.value=revShow(selMonth);
  document.getElementById("revMesHint").textContent=revIsAuto(selMonth)
    ?"(Greenn líquido · "+MES[selMonth]+" · edite se quiser somar Eduzz/Voomp)"
    :"(mês de "+MES[selMonth]+")";
}

/* ===== charts MÊS ===== */
function prodMes(){
  const svg=document.getElementById("cProdMes");svg.innerHTML="";
  const r=DATA.monthly.find(x=>x.mes===selMonth)||{};
  const list=PRODUCTS.map(p=>[p,r[p]||0]).filter(d=>d[1]>0).sort((a,b)=>b[1]-a[1]);
  const W=900,H=Math.max(120,60+list.length*40),mL=150,mR=90,mT=8,mB=8,pw=W-mL-mR,ph=H-mT-mB;
  svg.setAttribute("viewBox",`0 0 ${W} ${H}`);
  if(!list.length){const t=el("text",{x:W/2,y:H/2,class:"axl","text-anchor":"middle"});t.textContent="Sem investimento neste mês";svg.appendChild(t);return;}
  const maxV=Math.max(...list.map(d=>d[1]),1),band=ph/list.length,bh=Math.min(30,band*0.6);
  list.forEach((d,i)=>{const [p,v]=d,cy=mT+band*i+band/2,w=(v/maxV)*pw;
    const lab=el("text",{x:mL-10,y:cy+4,class:"axl","text-anchor":"end"});lab.textContent=SHORT[p];svg.appendChild(lab);
    const rect=el("rect",{x:mL,y:cy-bh/2,width:Math.max(w,2),height:bh,rx:4,fill:col(p)});rect.style.cursor="pointer";
    const tot=(DATA.monthly.find(x=>x.mes===selMonth)||{}).total||1;
    rect.addEventListener("mousemove",e=>showTT(`<div class="th">${SHORT[p]}</div><div class="row"><span class="k">Investimento</span><span>${brl(v)}</span></div><div class="row"><span class="k">% do mês</span><span>${(100*v/tot).toFixed(1)}%</span></div>`,e.clientX,e.clientY));
    rect.addEventListener("mouseleave",hideTT);svg.appendChild(rect);
    const val=el("text",{x:mL+w+8,y:cy+4,class:"ax","text-anchor":"start"});val.textContent=brlk(v);svg.appendChild(val);});
}
function dailyMes(){
  const svg=document.getElementById("cDailyMes");svg.innerHTML="";
  const rowsAll=DATA.daily.filter(r=>r.data.slice(0,7)===selMonth);
  const act=PRODUCTS.filter(p=>!hiddenMes.has(p));
  const W=900,H=320,mL=64,mR=16,mT=12,mB=34,pw=W-mL-mR,ph=H-mT-mB;
  if(!rowsAll.length){const t=el("text",{x:W/2,y:H/2,class:"axl","text-anchor":"middle"});t.textContent="Sem dados diários neste mês";svg.appendChild(t);return;}
  const maxV=Math.max(...rowsAll.map(r=>act.reduce((s,p)=>s+r[p],0)),1);
  const ticks=niceTicks(maxV,4),top=ticks[ticks.length-1],y=v=>mT+ph-(v/top)*ph;
  const n=rowsAll.length,band=pw/n,bw=Math.min(26,band*0.7);
  ticks.forEach(t=>{svg.appendChild(el("line",{x1:mL,x2:W-mR,y1:y(t),y2:y(t),class:"gl"}));
    const tx=el("text",{x:mL-8,y:y(t)+3.5,class:"ax","text-anchor":"end"});tx.textContent=brlk(t);svg.appendChild(tx);});
  svg.appendChild(el("line",{x1:mL,x2:W-mR,y1:y(0),y2:y(0),class:"bl"}));
  rowsAll.forEach((r,i)=>{const cx=mL+band*i+band/2,x=cx-bw/2;let acc=0;
    act.forEach(p=>{const v=r[p];if(v<=0)return;const h=(v/top)*ph;
      const rect=el("rect",{x:x,y:y(acc+v),width:bw,height:Math.max(h-1.5,0),rx:2,fill:col(p)});rect.style.cursor="pointer";
      rect.addEventListener("mousemove",e=>showTT(dayTT(r,act),e.clientX,e.clientY));rect.addEventListener("mouseleave",hideTT);
      svg.appendChild(rect);acc+=v;});
    if(i%Math.ceil(n/12)===0||i===n-1){const tx=el("text",{x:cx,y:H-mB+20,class:"ax","text-anchor":"middle"});tx.textContent=r.data.slice(8);svg.appendChild(tx);}});
}
function dayTT(r,act){const [Y,M,D]=r.data.split("-");
  let rows=act.filter(p=>r[p]>0).sort((a,b)=>r[b]-r[a]).map(p=>`<div class="row"><span class="k"><i style="background:${col(p)}"></i>${SHORT[p]}</span><span>${brl(r[p])}</span></div>`).join("");
  const tot=act.reduce((s,p)=>s+r[p],0);
  return `<div class="th">${D}/${M}/${Y}</div>${rows||'<div class="row"><span class="k">sem gasto</span></div>'}<div class="row" style="margin-top:5px;border-top:1px solid var(--grid);padding-top:5px"><span class="k">Total</span><span><b>${brl(tot)}</b></span></div>`;}

/* ===== legends ===== */
function legendMes(){const lg=document.getElementById("legendMes");lg.innerHTML="";
  PRODUCTS.forEach(p=>{const d=document.createElement("div");d.className="lg"+(hiddenMes.has(p)?" off":"");
    d.innerHTML=`<span class="sw" style="background:${col(p)}"></span>${SHORT[p]}`;
    d.onclick=()=>{hiddenMes.has(p)?hiddenMes.delete(p):hiddenMes.add(p);legendMes();dailyMes();};lg.appendChild(d);});}
function legendAno(){const lg=document.getElementById("legendAno");lg.innerHTML="";
  PRODUCTS.forEach(p=>{const d=document.createElement("div");d.className="lg"+(hidden.has(p)?" off":"");
    d.innerHTML=`<span class="sw" style="background:${col(p)}"></span>${SHORT[p]}`;
    d.onclick=()=>{hidden.has(p)?hidden.delete(p):hidden.add(p);legendAno();drawAno();};lg.appendChild(d);});}
const activeAno=()=>PRODUCTS.filter(p=>!hidden.has(p));

/* ===== ANO: tabela geral ===== */
function tblGeral(){
  const t=document.getElementById("tblGeral");
  const head=`<thead><tr><th>Mês</th><th>Investimento</th><th>Invest. c/ imp.</th><th>Receita</th><th>ROI</th><th>ROAS</th><th>Lucro</th></tr></thead>`;
  let body="<tbody>";
  DATA.monthly.forEach(r=>{const c=computeMonth(r.mes),hasInv=c.inv>0;
    const roi=c.rec>0&&c.roi!=null?`<span class="${c.roi>=0?'pos':'neg'}">${(c.roi*100).toFixed(1)}%</span>`:"—";
    const roas=c.rec>0&&c.roas!=null?c.roas.toFixed(2)+"x":"—";
    const lucro=c.rec>0?`<span class="${c.lucro>=0?'pos':'neg'}">${brlk(c.lucro)}</span>`:"—";
    body+=`<tr><td>${MESC[r.mes]}</td><td>${hasInv?brlk(c.inv):"—"}</td><td>${hasInv?brlk(c.invT):"—"}</td>`+
      `<td><input class="rev" data-m="${r.mes}" inputmode="decimal" value="${revShow(r.mes)}" placeholder="0"></td>`+
      `<td>${roi}</td><td>${roas}</td><td>${lucro}</td></tr>`;});
  body+="</tbody>";
  const T=yearTotals();
  const froi=T.rec>0&&T.roi!=null?`<span class="${T.roi>=0?'pos':'neg'}">${(T.roi*100).toFixed(1)}%</span>`:"—";
  const foot=`<tfoot><tr><td>Total · Ano</td><td>${brlk(T.inv)}</td><td>${brlk(T.invT)}</td><td>${brlk(T.rec)}</td><td>${froi}</td><td>${T.rec>0&&T.roas!=null?T.roas.toFixed(2)+"x":"—"}</td><td>${T.rec>0?brlk(T.lucro):"—"}</td></tr></tfoot>`;
  t.innerHTML=head+body+foot;
  t.querySelectorAll("input.rev").forEach(inp=>inp.addEventListener("input",()=>{
    const m=inp.dataset.m,v=inp.value.trim();
    if(v==="")delete REV[m];else REV[m]=parseNum(v);
    saveRev(REV);recalcAll();}));
}
/* atualiza numeros derivados sem recriar inputs (nao perde foco) */
function recalcAll(){
  kpisAno();
  if(curView==="mes")drawMes();else prodAnoTable();
  const tf=document.querySelector("#tblGeral tfoot");
  if(tf){const T=yearTotals();const froi=T.rec>0&&T.roi!=null?`<span class="${T.roi>=0?'pos':'neg'}">${(T.roi*100).toFixed(1)}%</span>`:"—";
    tf.innerHTML=`<tr><td>Total · Ano</td><td>${brlk(T.inv)}</td><td>${brlk(T.invT)}</td><td>${brlk(T.rec)}</td><td>${froi}</td><td>${T.rec>0&&T.roas!=null?T.roas.toFixed(2)+"x":"—"}</td><td>${T.rec>0?brlk(T.lucro):"—"}</td></tr>`;}
  document.querySelectorAll("#tblGeral tbody tr").forEach(tr=>{const inp=tr.querySelector("input.rev");if(!inp)return;
    const c=computeMonth(inp.dataset.m),tds=tr.querySelectorAll("td");
    tds[4].innerHTML=c.rec>0&&c.roi!=null?`<span class="${c.roi>=0?'pos':'neg'}">${(c.roi*100).toFixed(1)}%</span>`:"—";
    tds[5].innerHTML=c.rec>0&&c.roas!=null?c.roas.toFixed(2)+"x":"—";
    tds[6].innerHTML=c.rec>0?`<span class="${c.lucro>=0?'pos':'neg'}">${brlk(c.lucro)}</span>`:"—";});
}

/* ===== ANO charts ===== */
function monthly(){
  const svg=document.getElementById("cMonthly");svg.innerHTML="";
  const W=900,H=380,mL=64,mR=16,mT=14,mB=40,pw=W-mL-mR,ph=H-mT-mB;
  const rows=DATA.monthly.filter(r=>r.total>0);
  const maxV=Math.max(...rows.map(r=>activeAno().reduce((s,p)=>s+r[p],0)),1);
  const ticks=niceTicks(maxV,5),top=ticks[ticks.length-1],y=v=>mT+ph-(v/top)*ph;
  ticks.forEach(t=>{svg.appendChild(el("line",{x1:mL,x2:W-mR,y1:y(t),y2:y(t),class:"gl"}));
    const tx=el("text",{x:mL-8,y:y(t)+3.5,class:"ax","text-anchor":"end"});tx.textContent=brlk(t);svg.appendChild(tx);});
  svg.appendChild(el("line",{x1:mL,x2:W-mR,y1:y(0),y2:y(0),class:"bl"}));
  const n=rows.length,band=pw/Math.max(n,1),bw=Math.min(64,band*0.62);
  rows.forEach((r,i)=>{const cx=mL+band*i+band/2,x=cx-bw/2;let acc=0;
    activeAno().forEach(p=>{const v=r[p];if(v<=0)return;const h=(v/top)*ph;
      const rect=el("rect",{x:x,y:y(acc+v),width:bw,height:Math.max(h-2,0),rx:3,fill:col(p)});rect.style.cursor="pointer";
      rect.addEventListener("mousemove",e=>showTT(monthTT(r),e.clientX,e.clientY));rect.addEventListener("mouseleave",hideTT);
      svg.appendChild(rect);acc+=v;});
    const tx=el("text",{x:cx,y:H-mB+22,class:"axl","text-anchor":"middle"});tx.textContent=MESC[r.mes];svg.appendChild(tx);
    const tot=el("text",{x:cx,y:y(acc)-7,class:"ax","text-anchor":"middle"});tot.textContent=brlk(acc);tot.style.fontWeight=600;svg.appendChild(tot);});
}
function monthTT(r){let rows=activeAno().filter(p=>r[p]>0).sort((a,b)=>r[b]-r[a]).map(p=>`<div class="row"><span class="k"><i style="background:${col(p)}"></i>${SHORT[p]}</span><span>${brl(r[p])}</span></div>`).join("");
  const tot=activeAno().reduce((s,p)=>s+r[p],0);
  return `<div class="th">${MES[r.mes]} 2026</div>${rows}<div class="row" style="margin-top:5px;border-top:1px solid var(--grid);padding-top:5px"><span class="k">Total</span><span><b>${brl(tot)}</b></span></div>`;}
function daily(){
  const svg=document.getElementById("cDaily");svg.innerHTML="";
  const W=900,H=340,mL=64,mR=16,mT=12,mB=34,pw=W-mL-mR,ph=H-mT-mB;
  const rows=DATA.daily,n=rows.length;if(!n)return;
  const maxV=Math.max(...rows.map(r=>activeAno().reduce((s,p)=>s+r[p],0)),1);
  const ticks=niceTicks(maxV,4),top=ticks[ticks.length-1],x=i=>mL+(pw*(n<=1?0:i/(n-1))),y=v=>mT+ph-(v/top)*ph;
  ticks.forEach(t=>{svg.appendChild(el("line",{x1:mL,x2:W-mR,y1:y(t),y2:y(t),class:"gl"}));
    const tx=el("text",{x:mL-8,y:y(t)+3.5,class:"ax","text-anchor":"end"});tx.textContent=brlk(t);svg.appendChild(tx);});
  let base=new Array(n).fill(0);
  activeAno().forEach(p=>{const tl=rows.map((r,i)=>base[i]+r[p]);let dd="M"+x(0)+","+y(base[0]);
    for(let i=0;i<n;i++)dd+=" L"+x(i).toFixed(1)+","+y(tl[i]).toFixed(1);
    for(let i=n-1;i>=0;i--)dd+=" L"+x(i).toFixed(1)+","+y(base[i]).toFixed(1);
    dd+=" Z";svg.appendChild(el("path",{d:dd,fill:col(p),"fill-opacity":.9}));base=tl;});
  svg.appendChild(el("line",{x1:mL,x2:W-mR,y1:y(0),y2:y(0),class:"bl"}));
  let seen={};rows.forEach((r,i)=>{const m=r.data.slice(0,7);if(!seen[m]){seen[m]=1;
    const tx=el("text",{x:x(i),y:H-mB+20,class:"axl","text-anchor":"middle"});tx.textContent=MESC[m];svg.appendChild(tx);}});
  const hover=el("line",{x1:0,x2:0,y1:mT,y2:mT+ph,stroke:"var(--axis)","stroke-width":1,opacity:0});svg.appendChild(hover);
  const cap=el("rect",{x:mL,y:mT,width:pw,height:ph,fill:"transparent"});cap.style.cursor="crosshair";
  cap.addEventListener("mousemove",e=>{const pt=svg.getBoundingClientRect();const rel=(e.clientX-pt.left)/pt.width*W;
    let i=Math.round((rel-mL)/pw*(n-1));i=Math.max(0,Math.min(n-1,i));
    hover.setAttribute("x1",x(i));hover.setAttribute("x2",x(i));hover.setAttribute("opacity",1);
    showTT(dayTT(rows[i],activeAno()),e.clientX,e.clientY);});
  cap.addEventListener("mouseleave",()=>{hover.setAttribute("opacity",0);hideTT();});svg.appendChild(cap);
}
function prod(){
  const svg=document.getElementById("cProd");svg.innerHTML="";
  const W=900,H=300,mL=150,mR=90,mT=8,mB=8,pw=W-mL-mR,ph=H-mT-mB;
  const list=PRODUCTS.map(p=>[p,DATA.totals[p]]).filter(d=>d[1]>0).sort((a,b)=>b[1]-a[1]);
  const maxV=Math.max(...list.map(d=>d[1]),1),band=ph/Math.max(list.length,1),bh=Math.min(30,band*0.6);
  list.forEach((d,i)=>{const [p,v]=d,cy=mT+band*i+band/2,w=(v/maxV)*pw;
    const lab=el("text",{x:mL-10,y:cy+4,class:"axl","text-anchor":"end"});lab.textContent=SHORT[p];svg.appendChild(lab);
    const rect=el("rect",{x:mL,y:cy-bh/2,width:Math.max(w,2),height:bh,rx:4,fill:col(p)});rect.style.cursor="pointer";
    rect.addEventListener("mousemove",e=>showTT(`<div class="th">${SHORT[p]}</div><div class="row"><span class="k">Investimento</span><span>${brl(v)}</span></div><div class="row"><span class="k">% do total</span><span>${(100*v/DATA.grand).toFixed(1)}%</span></div>`,e.clientX,e.clientY));
    rect.addEventListener("mouseleave",hideTT);svg.appendChild(rect);
    const val=el("text",{x:mL+w+8,y:cy+4,class:"ax","text-anchor":"start"});val.textContent=brlk(v);svg.appendChild(val);});
}
function noteOutros(){document.getElementById("noteOutros").innerHTML=`<b>Sobre "Outros" (${brl(DATA.totals.Outros)}):</b> campanhas fora dos 6 produtos — Binaurais, Workshop, eventos e testes de VSL. Separadas para não inflar os produtos.`;}

/* ===== NOVO MÊS: Corrida da Meta · Faturamento ===== */
const LSMETA="brainpro_meta_2026";
function loadMetas(){try{return JSON.parse(localStorage.getItem(LSMETA)||"{}")}catch(e){return{}}}
function saveMetas(o){try{localStorage.setItem(LSMETA,JSON.stringify(o))}catch(e){}}
let METAS=loadMetas();
const RDIA=DATA.receitaDia||{};
const METADEF=+DATA.metaDefault||250000, SUPERDEF=+DATA.supermetaDefault||300000;
const CG="#0ca30c", CA="#f5a623";
function metaVal(m){return METAS[m]&&METAS[m].meta!=null?+METAS[m].meta:METADEF;}
function superVal(m){return METAS[m]&&METAS[m].sup!=null?+METAS[m].sup:SUPERDEF;}
function daysInMonth(m){return new Date(+m.slice(0,4),+m.slice(5,7),0).getDate();}
function fatDias(m){const o=[];for(const d in RDIA)if(d.slice(0,7)===m)o.push([+d.slice(8,10),+RDIA[d]||0]);o.sort((a,b)=>a[0]-b[0]);return o;}
function curDay(m){const now=new Date(),y=+m.slice(0,4),mo=+m.slice(5,7),dim=daysInMonth(m);
  if(now.getFullYear()===y&&now.getMonth()+1===mo)return Math.min(now.getDate(),dim);
  if(now.getFullYear()>y||(now.getFullYear()===y&&now.getMonth()+1>mo))return dim;
  const fd=fatDias(m);return fd.length?fd[fd.length-1][0]:1;}
function invMesTotal(m){const r=DATA.monthly.find(x=>x.mes===m);return r?r.total:0;}

function statusPill(m){
  const meta=metaVal(m),fat=revVal(m),dim=daysInMonth(m),d=curDay(m),pace=meta*d/dim,delta=fat-pace,ok=delta>=0;
  const e=document.getElementById("statusPill");
  e.className="statuspill "+(ok?"sp-ok":"sp-late");
  e.textContent="● "+(ok?"No ritmo":"Atrás")+" · "+(ok?"+":"−")+brlk(Math.abs(delta));
}
function mesKpis(m){
  const meta=metaVal(m),sup=superVal(m),fat=brutoVal(m),liq=revVal(m),dim=daysInMonth(m),d=curDay(m);
  const inv=invMesTotal(m),invT=inv*(1+taxRate()),lucro=liq-invT;
  const rest=Math.max(0,dim-d),restD=Math.max(1,rest),fMeta=Math.max(0,meta-fat),fSup=Math.max(0,sup-fat);
  document.getElementById("mesKpis").innerHTML=[
    kpiCard("Faturamento bruto",brlk(fat),"faturamento cheio · até dia "+d,""),
    kpiCard("Faturamento s/ taxas",brlk(liq),"sem taxas de plataforma",""),
    kpiCard("Lucro",brlk(lucro),"sem taxas · sem tráfego",lucro>=0?"pos":"neg"),
    kpiCard("Meta do mês",brlk(meta),(meta>0?(100*fat/meta).toFixed(0):0)+"% atingido",fat>=meta&&meta>0?"pos":""),
    kpiCard("Super meta",brlk(sup),(sup>0?(100*fat/sup).toFixed(0):0)+"% atingido",fat>=sup&&sup>0?"pos":""),
    kpiCard("Falta p/ a meta",brlk(fMeta),fMeta<=0?"meta batida! 🎉":"de "+brlk(meta),fMeta<=0?"pos":""),
    kpiCard("Falta p/ super meta",brlk(fSup),fSup<=0?"super batida! 🎉":"de "+brlk(sup),fSup<=0?"pos":""),
    kpiCard("Dias restantes",String(rest),"de "+dim+" dias no mês",""),
  ].join("");
}
function chartCorrida(m){
  const svg=document.getElementById("cCorrida");svg.innerHTML="";
  const W=900,H=380,mL=64,mR=22,mT=16,mB=34,pw=W-mL-mR,ph=H-mT-mB;
  const dim=daysInMonth(m),meta=metaVal(m),sup=superVal(m),d=curDay(m);
  const fd=fatDias(m);let running=0;const cum={};fd.forEach(p=>{running+=p[1];cum[p[0]]=running;});
  const totFat=running;
  const ticks=niceTicks(Math.max(sup,meta,totFat,1),5),topV=ticks[ticks.length-1];
  const x=day=>mL+pw*((day-1)/Math.max(dim-1,1)),y=v=>mT+ph-(v/topV)*ph;
  ticks.forEach(t=>{svg.appendChild(el("line",{x1:mL,x2:W-mR,y1:y(t),y2:y(t),class:"gl"}));
    const tx=el("text",{x:mL-8,y:y(t)+3.5,class:"ax","text-anchor":"end"});tx.textContent=brlk(t);svg.appendChild(tx);});
  svg.appendChild(el("line",{x1:mL,x2:W-mR,y1:y(sup),y2:y(sup),stroke:cssv("--s7"),"stroke-width":1.5,"stroke-dasharray":"2 4"}));
  const sl=el("text",{x:mL+4,y:y(sup)-6,class:"axl"});sl.textContent="Super meta ("+brlk(sup)+")";sl.style.fill=cssv("--s7");svg.appendChild(sl);
  svg.appendChild(el("line",{x1:x(1),x2:x(dim),y1:y(meta/dim),y2:y(meta),stroke:cssv("--muted"),"stroke-width":1.5,"stroke-dasharray":"6 5"}));
  const ml=el("text",{x:x(dim)-2,y:y(meta)-6,class:"axl","text-anchor":"end"});ml.textContent="Meta ("+brlk(meta)+")";svg.appendChild(ml);
  let run=0;const pts=[];for(let dd=1;dd<=d;dd++){if(cum[dd]!=null)run=cum[dd];pts.push([dd,run]);}
  if(pts.length){
    const area="M"+x(pts[0][0]).toFixed(1)+","+y(0).toFixed(1)+" "+pts.map(p=>"L"+x(p[0]).toFixed(1)+","+y(p[1]).toFixed(1)).join(" ")+" L"+x(pts[pts.length-1][0]).toFixed(1)+","+y(0).toFixed(1)+" Z";
    svg.appendChild(el("path",{d:area,fill:cssv("--s1"),"fill-opacity":.13}));
    const line="M"+pts.map(p=>x(p[0]).toFixed(1)+","+y(p[1]).toFixed(1)).join(" L");
    svg.appendChild(el("path",{d:line,fill:"none",stroke:cssv("--s1"),"stroke-width":2.5}));
    const last=pts[pts.length-1],tl=el("text",{x:x(last[0])+6,y:y(last[1])-7,class:"ax"});tl.textContent=brlk(last[1]);tl.style.fontWeight=700;tl.style.fill=cssv("--s1");svg.appendChild(tl);
  }
  for(let dd=1;dd<=dim;dd+=(dim>20?5:2)){const tx=el("text",{x:x(dd),y:H-mB+20,class:"axl","text-anchor":"middle"});tx.textContent=String(dd);svg.appendChild(tx);}
  svg.appendChild(el("line",{x1:mL,x2:W-mR,y1:y(0),y2:y(0),class:"bl"}));
}
function chartFatDia(m){
  const svg=document.getElementById("cFatDia");svg.innerHTML="";
  const W=900,H=320,mL=64,mR=22,mT=16,mB=34,pw=W-mL-mR,ph=H-mT-mB;
  const dim=daysInMonth(m),meta=metaVal(m),metaDia=meta/dim,map={};fatDias(m).forEach(p=>map[p[0]]=p[1]);
  const ticks=niceTicks(Math.max(metaDia,...Object.values(map),1),4),top=ticks[ticks.length-1],y=v=>mT+ph-(v/top)*ph;
  ticks.forEach(t=>{svg.appendChild(el("line",{x1:mL,x2:W-mR,y1:y(t),y2:y(t),class:"gl"}));
    const tx=el("text",{x:mL-8,y:y(t)+3.5,class:"ax","text-anchor":"end"});tx.textContent=brlk(t);svg.appendChild(tx);});
  const band=pw/dim,bw=Math.min(22,band*0.66);
  for(let dd=1;dd<=dim;dd++){const v=map[dd]||0;if(v<=0)continue;const cx=mL+band*(dd-0.5),h=(v/top)*ph,color=v>=metaDia?CG:CA;
    const rect=el("rect",{x:cx-bw/2,y:y(v),width:bw,height:Math.max(h,1),rx:3,fill:color});rect.style.cursor="pointer";
    rect.addEventListener("mousemove",e=>showTT('<div class="th">Dia '+dd+'</div><div class="row"><span class="k">Faturado</span><span>'+brl(v)+'</span></div><div class="row"><span class="k">Meta/dia</span><span>'+brl(metaDia)+'</span></div>',e.clientX,e.clientY));
    rect.addEventListener("mouseleave",hideTT);svg.appendChild(rect);}
  svg.appendChild(el("line",{x1:mL,x2:W-mR,y1:y(metaDia),y2:y(metaDia),stroke:cssv("--muted"),"stroke-width":1.5,"stroke-dasharray":"6 5"}));
  const ml=el("text",{x:W-mR,y:y(metaDia)-6,class:"axl","text-anchor":"end"});ml.textContent="Meta do dia ("+brl(metaDia)+")";svg.appendChild(ml);
  for(let dd=1;dd<=dim;dd+=(dim>20?5:2)){const tx=el("text",{x:mL+band*(dd-0.5),y:H-mB+20,class:"axl","text-anchor":"middle"});tx.textContent=String(dd);svg.appendChild(tx);}
  svg.appendChild(el("line",{x1:mL,x2:W-mR,y1:y(0),y2:y(0),class:"bl"}));
}
function trafKpis(m){
  const inv=invMesTotal(m),tax=taxRate(),invT=inv*(1+tax),fat=revVal(m);
  const roi=invT>0?(fat-invT)/invT:null,roas=invT>0?fat/invT:null,lucro=fat-invT;
  document.getElementById("trafKpis").innerHTML=[
    kpiCard("Investimento (mês)",brl(inv),"tráfego Meta Ads",""),
    kpiCard("Invest. c/ imposto",brl(invT),"alíquota "+(tax*100).toFixed(2).replace(".",",")+"%",""),
    kpiCard("ROI",roi!=null?(roi*100).toFixed(0)+"%":"—","faturado ÷ invest.",roi!=null?(roi>=0?"pos":"neg"):""),
    kpiCard("ROAS",roas!=null?roas.toFixed(2)+"x":"—","retorno s/ anúncio",""),
    kpiCard("Lucro",brl(lucro),"faturado − invest. c/ imp",fat>0?(lucro>=0?"pos":"neg"):""),
  ].join("");
  const t2=document.getElementById("mesTitTraf");if(t2)t2.textContent=MES[m]+" 2026";
}
const PLAT={"Pós-Graduação":"Voomp / Eduzz","tDCS":"Eduzz","Recorrência Pós":"recebida","Vagal":"Eduzz / Greenn","Lançamento Vagal":"Greenn R$497","Aplicativo":"Greenn","App":"Greenn","Fotobio":"Greenn","TEA":"—","Impulsionamento Estratégia Instagram":"orgânico","Outros":"Neuromodulação"};
const TILECOL=["--s1","--s2","--s3","--s4","--s5","--s7","--s6","--s8","--s9","--sOut"];
function prodTiles(m){
  const rp=RPROD[m]||{},fat=revVal(m)||Object.values(rp).reduce((s,v)=>s+(+v||0),0);
  const order=Object.keys(rp).filter(k=>rp[k]>0).sort((a,b)=>rp[b]-rp[a]);
  const html=order.map((p,i)=>{const v=+rp[p],pct=fat>0?(100*v/fat).toFixed(0):0,c=cssv(TILECOL[i%TILECOL.length]);
    return '<div class="kpi"><div class="lab" style="display:flex;align-items:center;gap:6px"><i style="width:9px;height:9px;border-radius:2px;background:'+c+';display:inline-block"></i>'+p+'</div><div class="val">'+brlk(v)+'</div><div class="note">'+(PLAT[p]||"")+' · '+pct+'% do faturado</div></div>';}).join("");
  document.getElementById("prodTiles").innerHTML=html||'<div class="kpi"><div class="note">Sem receita por produto ainda — vai chegar pelos webhooks.</div></div>';
}
function syncMetaInputs(){document.getElementById("metaInp").value=metaVal(selMonth);document.getElementById("superInp").value=superVal(selMonth);}

/* ===== render ===== */
function drawMes(){fillMonthSel();syncMetaInputs();statusPill(selMonth);mesKpis(selMonth);chartCorrida(selMonth);chartFatDia(selMonth);trafKpis(selMonth);legendMes();dailyMes();prodTiles(selMonth);prodMesTable();}
function drawAno(){monthly();daily();prod();}
function renderMes(){drawMes();}
function renderAno(){kpisAno();tblGeral();prodAnoTable();legendAno();drawAno();noteOutros();}

function switchView(v){curView=v;
  document.getElementById("viewMes").classList.toggle("hide",v!=="mes");
  document.getElementById("viewAno").classList.toggle("hide",v!=="ano");
  document.getElementById("tabMes").classList.toggle("active",v==="mes");
  document.getElementById("tabAno").classList.toggle("active",v==="ano");
  if(v==="mes")renderMes();else renderAno();}

document.getElementById("tabMes").onclick=()=>switchView("mes");
document.getElementById("tabAno").onclick=()=>switchView("ano");
document.getElementById("monthSel").onchange=e=>{selMonth=e.target.value;renderMes();};
document.getElementById("metaInp").addEventListener("input",e=>{const v=parseNum(e.target.value);
  METAS[selMonth]=METAS[selMonth]||{};METAS[selMonth].meta=v||0;saveMetas(METAS);statusPill(selMonth);mesKpis(selMonth);chartCorrida(selMonth);chartFatDia(selMonth);trafKpis(selMonth);});
document.getElementById("superInp").addEventListener("input",e=>{const v=parseNum(e.target.value);
  METAS[selMonth]=METAS[selMonth]||{};METAS[selMonth].sup=v||0;saveMetas(METAS);statusPill(selMonth);mesKpis(selMonth);chartCorrida(selMonth);});
document.getElementById("taxRate").addEventListener("input",()=>{recalcAll();});
document.getElementById("themeBtn").onclick=()=>{const r=document.documentElement;
  r.setAttribute("data-theme",r.getAttribute("data-theme")==="dark"?"light":"dark");
  if(curView==="mes")drawMes();else drawAno();};
document.getElementById("expBtn").onclick=()=>{const blob=new Blob([JSON.stringify({receita:REV,imposto:document.getElementById("taxRate").value},null,2)],{type:"application/json"});
  const a=document.createElement("a");a.href=URL.createObjectURL(blob);a.download="receita_brainpro_2026.json";a.click();};
document.getElementById("impBtn").onclick=()=>document.getElementById("impFile").click();
document.getElementById("impFile").onchange=e=>{const f=e.target.files[0];if(!f)return;const rd=new FileReader();
  rd.onload=()=>{try{const o=JSON.parse(rd.result);if(o.receita){REV=o.receita;saveRev(REV);}if(o.imposto)document.getElementById("taxRate").value=o.imposto;switchView(curView);}catch(err){alert("Arquivo inválido");}};rd.readAsText(f);};

/* ===== Receita AO VIVO (webhooks Greenn/Eduzz/Voomp via Apps Script) ===== */
function liveRevenue(){
  const url=DATA.webappUrl;
  if(!url) return;                       // ainda não configurado -> usa receita embutida
  const cb="__rev_"+Math.floor(performance.now());
  const s=document.createElement("script");
  const timer=setTimeout(()=>{try{delete window[cb];s.remove();}catch(e){}},12000);
  window[cb]=function(res){
    clearTimeout(timer);
    try{
      if(res&&res.por_mes_total&&Object.keys(res.por_mes_total).length){
        for(const m in res.por_mes_total) RDEF[m]=res.por_mes_total[m];
        if(res.por_mes_produto) for(const m in res.por_mes_produto) RPROD[m]=res.por_mes_produto[m];
        const badge=document.getElementById("upd");
        if(badge&&res.atualizado) badge.textContent="receita ao vivo · "+res.atualizado;
        switchView(curView);            // re-renderiza com os números ao vivo
      }
    }catch(e){}
    try{delete window[cb];s.remove();}catch(e){}
  };
  s.src=url+(url.indexOf("?")>-1?"&":"?")+"callback="+cb+"&_="+Math.floor(performance.now());
  s.onerror=function(){clearTimeout(timer);try{delete window[cb];s.remove();}catch(e){}};
  document.body.appendChild(s);
}
function boot(){document.getElementById("upd").textContent="atualizado em "+(DATA.atualizado?DATA.atualizado.split("-").reverse().join("/"):"—");
  if(window.matchMedia&&window.matchMedia("(prefers-color-scheme: dark)").matches)document.documentElement.setAttribute("data-theme","dark");
  switchView("mes");
  liveRevenue();}
boot();
</script>
</body>
</html>'''

if __name__ == "__main__":
    import sys
    build(sys.argv[1] if len(sys.argv) > 1 else "data.json",
          sys.argv[2] if len(sys.argv) > 2 else "index.html")
