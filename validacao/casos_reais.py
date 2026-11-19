"""Validação da plataforma FSEN contra os filtros senoidais já fabricados pela Electric Service
(pastas 6 - FILTRO SENOIDAL LC / 7 - FILTRO SENOIDAL LCL). Para cada caso:
  (a) dimensionamento automático da plataforma com os mesmos dados de entrada;
  (b) simulação do filtro que foi realmente fabricado (projeto_manual), com os mesmos critérios.
"""
import json, math, sys, time, pickle, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fsen.modelos import Pedido
from fsen.dimensionamento import carregar_catalogo, dimensionar, projeto_manual

# real = filtro fabricado / proposto pelo Guilherme (planilha "Filtro Senoidal LC_Ver_1.x")
CASOS = [
    dict(id="IHR-2022", cliente="New Technologies IHR (Randon) 2022 – MM440", status="fabricado, em operação (OK do cliente 17/11/22), medido",
         tensao_v=380, motor_kw=11.6, corrente_a=22, insp_i_ind=28, inversor="GENERICO", fs_khz=4.0,
         real=dict(L1_uH=1586, cap_id="TDK_PEC_20u_480", ligacao="Estrela", n_por_ramo=1, uk=6.0, fr=890, venda=4324, custo=1937)),
    dict(id="IHR-30A", cliente="SENAI S.Leopoldo / IHR 30 A / Gelluns 20 CV", status="fabricado (3 clientes), medido e termografado",
         tensao_v=380, motor_kw=16, corrente_a=30, insp_i_ind=38, inversor="GENERICO", fs_khz=6.0,
         real=dict(L1_uH=958, cap_id="TDK_PEC_20u_480", ligacao="Estrela", n_por_ramo=2, uk=5.0, fr=820, venda=6280, custo=2964)),
    dict(id="INSTALL-10A", cliente="Install Instalação 10 A 415 V", status="cotado (Cootrans ORC 0045/23)",
         tensao_v=415, motor_kw=5.8, corrente_a=10, insp_i_ind=10, inversor="GENERICO", fs_khz=4.0,
         real=dict(L1_uH=3783, cap_id="TDK_PEC_10u_480", ligacao="Estrela", n_por_ramo=1, uk=6.0, fr=830, venda=4324, custo=1937)),
    dict(id="INSTALL-20A", cliente="Install Instalação 20 A 415 V", status="cotado (Cootrans ORC 0045/23)",
         tensao_v=415, motor_kw=11.6, corrente_a=20, insp_i_ind=20, inversor="GENERICO", fs_khz=4.0,
         real=dict(L1_uH=1891, cap_id="TDK_PEC_20u_480", ligacao="Estrela", n_por_ramo=1, uk=6.0, fr=900, venda=4324, custo=1937)),
    dict(id="AB-48A", cliente="AB-Powertrain 48 A 380 V", status="cotado/fabricado (20 µF delta, uk 5,5 %)",
         tensao_v=380, motor_kw=25.3, corrente_a=48, insp_i_ind=48, inversor="GENERICO", fs_khz=4.0,
         real=dict(L1_uH=666, cap_id="TDK_PEC_20u_480", ligacao="Delta", n_por_ramo=1, uk=5.5, fr=None, venda=7195, custo=3787)),
    dict(id="GRATT-59A", cliente="GRATT 40 CV 59 A 380 V", status="cotado",
         tensao_v=380, motor_kw=29.4, corrente_a=59, insp_i_ind=59, inversor="GENERICO", fs_khz=4.0,
         real=dict(L1_uH=597, cap_id="TDK_PEC_20u_480", ligacao="Estrela", n_por_ramo=3, uk=6.0, fr=900, venda=9061, custo=4769)),
    dict(id="GRATT-105A", cliente="GRATT 75 CV 105 A 380 V", status="cotado",
         tensao_v=380, motor_kw=55, corrente_a=105, insp_i_ind=105, inversor="GENERICO", fs_khz=4.0,
         real=dict(L1_uH=333, cap_id="TDK_PEC_20u_480", ligacao="Estrela", n_por_ramo=5, uk=6.0, fr=900, venda=13986, custo=7361)),
    dict(id="FRANKLIN-120A", cliente="Franklin Electric 120 A 380 V", status="dimensionado (planilha)",
         tensao_v=380, motor_kw=63, corrente_a=120, insp_i_ind=120, inversor="GENERICO", fs_khz=4.0,
         real=dict(L1_uH=291, cap_id="TDK_PEC_20u_480", ligacao="Delta", n_por_ramo=2, uk=6.0, fr=850, venda=None, custo=None)),
    dict(id="ASA-255A", cliente="ASA – ATV61HC13N4 255 A 380 V", status="cotado (Cootrans ORC 0136/23: 137 µH 306 A)",
         tensao_v=380, motor_kw=134, corrente_a=255, insp_i_ind=306, inversor="GENERICO", fs_khz=4.0,
         real=dict(L1_uH=137, cap_id="TDK_PEC_20u_480", ligacao="Delta", n_por_ramo=4, uk=6.0, fr=900, venda=13180, custo=6590)),
    # referência de mercado (catálogo Schaffner FN5040, tabela da planilha "dados reator")
    dict(id="FN5040-24", cliente="Schaffner FN5040-24 (catálogo)", status="produto de catálogo, LC sem amortecimento",
         tensao_v=380, motor_kw=11, corrente_a=24, insp_i_ind=24, inversor="GENERICO", fs_khz=4.0,
         real=dict(L1_uH=2400, cap_id="TDK_PEC_10u_480", ligacao="Estrela", n_por_ramo=1, uk=None, fr=1027, venda=None, custo=None)),
    dict(id="FN5040-75", cliente="Schaffner FN5040-75 (catálogo)", status="produto de catálogo, LC sem amortecimento",
         tensao_v=380, motor_kw=37, corrente_a=75, insp_i_ind=75, inversor="GENERICO", fs_khz=4.0,
         real=dict(L1_uH=750, cap_id="TDK_PEC_30u_480", ligacao="Estrela", n_por_ramo=1, uk=None, fr=1061, venda=None, custo=None)),
]


def pedido(c):
    kw = c["motor_kw"]
    return Pedido.from_dict(dict(cliente=c["cliente"], tensao_v=c["tensao_v"], corrente_a=c["corrente_a"], motor_kw=kw,
                                 motor_cv=round(kw / 0.736, 1), motor_corrente_a=c["corrente_a"], motor_fp=0.8,
                                 f_saida_min_hz=30, f_saida_max_hz=60, inversor=c["inversor"], fs_khz=c["fs_khz"],
                                 inversor_corrente_a=c["corrente_a"], cabo_m=30, topologia="LC"))


def resumo(pr):
    b = pr.banco
    pts = {p["nome"]: p for p in pr.pontos}
    falhas = [v.item + ": " + v.valor + " (lim " + v.limite + ")" for v in pr.verificacoes if not v.ok and v.critico]
    alertas = [v.item + ": " + v.valor for v in pr.verificacoes if not v.ok and not v.critico]
    thd = max(p.get("thd_v_motor_pct", p.get("thd_v_saida_pct", 0)) for p in pr.pontos)
    return dict(topologia=getattr(pr, "topologia", "LC"), L1_uH=round(pr.l1.l_uh), uk=round(pr.l1.uk_pct, 2), fr=round(pr.fr_hz),
                cap=f"{b.n_total}× {b.uf_unit:g} µF {b.ligacao} ({b.n_por_ramo}/ramo)", C_y_uF=round(b.c_y_uf, 1),
                i_cap_unit=round(b.i_unit_rms, 2), v_cap=round(b.v_cap_rms), thd_max=round(thd, 2),
                ripple_pp_pct=round(100 * pr.l1.ripple_pp_a / pr.pedido["corrente_a"], 1) if pr.pedido["corrente_a"] else None,
                perdas_L_w=round(pr.l1.perdas_w), massa_L_kg=round(pr.l1.massa_kg, 1),
                custo_comp=round(pr.custo_componentes) if pr.custo_componentes else None,
                amort=(pr.amortecimento.tipo if pr.amortecimento else "nenhum"),
                aprovado=pr.aprovado, falhas=falhas, alertas=alertas)


if __name__ == "__main__":
    so = sys.argv[1:]
    cat = carregar_catalogo()
    out = {}
    for c in CASOS:
        if so and c["id"] not in so:
            continue
        t = time.time()
        ped = pedido(c)
        r = c["real"]
        real = projeto_manual(ped, cat, c["fs_khz"], r["L1_uH"], r["cap_id"], r["ligacao"], r["n_por_ramo"])
        auto = dimensionar(ped, cat, log=lambda m: None)
        out[c["id"]] = dict(caso=c, real=resumo(real), auto=resumo(auto))
        print(c["id"], f"{time.time()-t:.0f}s", json.dumps(out[c["id"]]["real"], ensure_ascii=False), "\n   AUTO",
              json.dumps(out[c["id"]]["auto"], ensure_ascii=False), flush=True)
    nome = "resultado_" + ("_".join(so) if so else "todos") + ".json"
    json.dump(out, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), nome), "w"), ensure_ascii=False, indent=1)
