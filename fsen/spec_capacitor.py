"""Especificação técnica DETALHADA dos capacitores do filtro senoidal – padrão para QUALQUER fornecedor (v1.9.9).

Mesmo princípio da ET do indutor: cada requisito com o PORQUÊ, figura da corrente real no capacitor, dados que o
fornecedor deve declarar, ensaios, critérios de aceitação e a regra de NÃO aceitar substituto de correção de fator de
potência (IEC 60831) – erro comum de distribuidor que não conhece filtro senoidal.
"""
import math


def requisitos(proj, cat, ped, q):
    from .dimensionamento import limites_capacitor
    b = proj.banco
    capd = next((c for c in cat.get("capacitores", []) if c["id"] == b.cap_id), {}) or dict(uf=b.uf_unit, v_ac=b.v_unit)
    lc = limites_capacitor(capd, cat)
    e = getattr(proj, "estresse_capacitor", {}) or {}
    pts = getattr(proj, "pontos", []) or []
    dvdt = max([p.get("dvdt_saida_v_us", 0) for p in pts] or [0])
    ipk_nec = b.uf_unit * dvdt                                   # A (µF × V/µs)
    i_rms = float(b.i_unit_rms or e.get("irms", 0))
    i_fund = float(b.i_unit_fund or 0)
    i_hf = math.sqrt(max(i_rms ** 2 - i_fund ** 2, 0))
    vpk = float(e.get("vpk", 0) or 0)
    v_rms = float(b.v_cap_rms or 0)
    est = int(capd.get("estoque", 0) or 0)
    n_nec = b.n_total * q
    return dict(b=b, capd=capd, lc=lc, e=e, dvdt=dvdt, ipk_nec=ipk_nec, i_rms=i_rms, i_fund=i_fund, i_hf=i_hf, vpk=vpk, v_rms=v_rms,
                imax_req=max(1.5 * i_rms, i_rms + 2), vpk_req=vpk * 1.10, v_req=max(v_rms * 1.10, float(b.v_unit)),
                t_hot=float(e.get("t_hotspot_c", 0) or 0), vida=float(e.get("vida_h", 0) or 0), perdas=float(e.get("perdas_w", 0) or 0),
                n_nec=n_nec, est=est, n_comp=max(0, n_nec - est), fs=float(proj.fs_hz),
                hf_pct=(100 * i_hf / i_rms if i_rms else 0))


def grafico_corrente(proj, cat, arquivo_png):
    """Corrente REAL em um capacitor (fundamental + alta frequência) – para o fornecedor ver o que o capacitor sofre."""
    import os
    import numpy as np
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from .dimensionamento import avaliar, pontos_operacao
    from .modelos import Pedido
    from .simulacao import simular
    ped = Pedido.from_dict(proj.pedido) if isinstance(proj.pedido, dict) else proj.pedido
    b = proj.banco
    cap = next((c for c in cat["capacitores"] if c["id"] == b.cap_id), None) or dict(id=b.cap_id, uf=b.uf_unit, v_ac=b.v_unit, preco=0)
    vdc = 1.35 * ped.tensao_v
    L2 = proj.l2.l_uh * 1e-6 if proj.l2 else 0.0
    p, _, _ = avaliar(ped, cat, proj.l1.l_uh * 1e-6, cap, (b.ligacao, b.n_por_ramo, b.c_y_uf * 1e-6), proj.fs_hz, vdc,
                      L2=L2, pts_por_portadora=24)
    op = pontos_operacao(ped, vdc, proj.fs_hz)[0]["op"]
    r = simular(p, op, pts_por_portadora=120, ciclos_analise=2)
    tt = np.asarray(r.t)
    t = tt * 1e3
    if b.ligacao == "Delta":
        v = np.asarray(r.vc_ab, float)
        dtp = float(tt[1] - tt[0])
        i_ramo = (p.C_y / 3.0) * (np.roll(v, -1) - np.roll(v, 1)) / (2 * dtp)
    else:
        i_ramo = np.asarray(r.icap_y, float)
    ic = i_ramo / max(b.n_por_ramo, 1)
    n = len(ic)
    F = np.fft.rfft(ic) / n
    fund = 2 * np.abs(F[2]) * np.cos(2 * np.pi * op.f1 * tt + np.angle(F[2]))
    j = int(np.argmax(np.abs(ic[: n // 2])))
    t0 = max(0.0, t[j] - 0.5)
    sel = (t >= t0) & (t <= t0 + 1.0)
    fig, ax = plt.subplots(2, 1, figsize=(11, 7.5))
    ax[0].plot(t, ic, color="#c0392b", lw=0.6, label="Corrente REAL em 1 capacitor (fundamental + alta frequência)")
    ax[0].plot(t, fund, color="#1b4f9c", lw=1.4, ls="--", label=f"Só a fundamental ({op.f1:g} Hz) – o que um capacitor de correção de FP veria")
    ax[0].axvspan(t0, t0 + 1.0, color="#f1c40f", alpha=0.35, label="Trecho ampliado abaixo (1 ms)")
    ax[0].set_ylabel("Corrente (A)")
    ax[0].set_title(f"① Corrente em um capacitor do filtro – {op.f1:g} Hz de saída, chaveamento {proj.fs_hz / 1000:g} kHz "
                    f"({b.n_por_ramo} capacitor(es) por ramo, ligação {b.ligacao})", fontsize=10.5)
    ax[0].legend(loc="lower left", fontsize=8, framealpha=0.95)
    ax[1].plot(t[sel], ic[sel], color="#c0392b", lw=1.0)
    ax[1].plot(t[sel], fund[sel], color="#1b4f9c", lw=1.4, ls="--")
    ax[1].set_ylabel("Corrente (A)")
    ax[1].set_xlabel("t (ms)")
    ax[1].set_title("② ZOOM de 1 ms: a componente de alta frequência DOMINA – é ela que aquece o capacitor (ESR) e exige "
                    "corrente de pico (Î) alta", fontsize=10)
    for a_ in ax:
        a_.grid(alpha=0.3)
    fig.text(0.5, 0.005, "Num capacitor de correção de fator de potência a corrente é praticamente senoidal de 60 Hz. No filtro senoidal o "
             "capacitor absorve a ondulação de alta frequência do inversor.", ha="center", fontsize=8.5, style="italic")
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    os.makedirs(os.path.dirname(arquivo_png) or ".", exist_ok=True)
    fig.savefig(arquivo_png, dpi=130)
    plt.close(fig)
    return arquivo_png


def escrever_et(d, proj, cat, ped, q, _kv, _tabela, _bullets, _f, figura=None):
    from docx.shared import Cm
    R = requisitos(proj, cat, ped, q)
    b, lc, capd = R["b"], R["lc"], R["capd"]
    d.add_heading("1. Aplicação", 1)
    d.add_paragraph(f"Capacitores monofásicos do filtro senoidal LC na saída de inversor PWM ({ped.get('inversor') or 'a definir'}, "
                    f"chaveamento {R['fs'] / 1000:g} kHz), ligados em {b.ligacao.lower()} ({b.n_por_ramo} por ramo, {b.n_total} por "
                    f"filtro). Item de referência: {b.pn} ({b.fabricante} – {b.linha}).")
    d.add_paragraph("Cada requisito vem com o motivo. Substituições só com aprovação por escrito da Electric Service, "
                    "com o datasheet do substituto.")

    d.add_heading("2. Por que NÃO serve capacitor de correção de fator de potência", 1)
    _bullets(d, [
        f"A corrente no capacitor do filtro não é só 60 Hz: além da fundamental ({R['i_fund']:.1f} A) ele absorve a ondulação de "
        f"alta frequência do inversor ({R['i_hf']:.1f} A RMS em {R['fs'] / 1000:g} kHz e múltiplos), totalizando {R['i_rms']:.1f} A RMS – "
        f"{R['hf_pct']:.0f} % da corrente é de alta frequência.",
        "Capacitores de correção de FP (IEC 60831) são projetados para tensão senoidal com poucas harmônicas: a resistência interna "
        "(ESR) e as conexões internas aquecem com a corrente de alta frequência e a vida útil cai rapidamente.",
        "Capacitores para eletrônica de potência / filtro AC (IEC 61071) declaram a corrente RMS máxima (Imax), a corrente de pico "
        "repetitiva (Î) e a ESR – exatamente os limites que importam aqui.",
        f"A tensão de pico soma a fundamental com a ondulação ({R['vpk']:.0f} V de pico estimados): o capacitor precisa da tensão "
        "de pico recorrente (Û/UN) declarada.",
        "Por isso: NÃO aceitar substituto \"equivalente\" de correção de FP, mesmo com a mesma capacitância e tensão."])
    if figura:
        try:
            d.add_picture(figura, width=Cm(16.5))
            d.add_paragraph("Figura – corrente simulada pela plataforma em um capacitor deste projeto: ① 2 ciclos (tracejado: só a "
                            "fundamental); ② zoom de 1 ms mostrando a componente de alta frequência.")
        except Exception:
            pass

    d.add_heading("3. Características exigidas – e por quê", 1)
    _tabela(d, ["Item", "Valor exigido", "Por quê"], [
        ("Tipo", "Monofásico MKP (polipropileno metalizado, autorregenerativo) para eletrônica de potência / filtro AC",
         "Suporta corrente de alta frequência e recupera pequenas falhas do dielétrico."),
        ("Norma", f"{lc['norma_txt']} (IEC 61071)", "Norma de capacitores para eletrônica de potência; IEC 60831 (correção de FP) NÃO atende."),
        ("Código de referência", f"{b.pn} ({b.fabricante})", "Item validado em campo e na simulação."),
        ("Capacitância", f"{b.uf_unit:g} µF ±5 %", "Define a ressonância do filtro junto com o indutor."),
        ("Tensão nominal (URMS)", f"≥ {b.v_unit:g} V RMS (operação {R['v_rms']:.0f} V RMS)", "Margem para rede +10 %."),
        ("Tensão de pico recorrente (UN/Û)", f"≥ {max(R['vpk_req'], lc['vpk']):.0f} V pico (operação ≈ {R['vpk']:.0f} V)",
         "A ondulação soma ao pico da fundamental."),
        ("Corrente RMS máxima (Imax)", f"≥ {max(R['imax_req'], lc['imax']):.1f} A RMS (operação {R['i_rms']:.1f} A, sendo "
                                       f"{R['i_hf']:.1f} A de alta frequência)", "Aquecimento pela ESR; margem para tolerâncias e envelhecimento."),
        ("Corrente de pico repetitiva (Î)", f"≥ {max(R['ipk_nec'] * 1.5, capd.get('ipk_a', 0) or 0):.0f} A "
                                            f"(dv/dt de operação {R['dvdt']:.1f} V/µs × {b.uf_unit:g} µF = {R['ipk_nec']:.0f} A)",
         "Bordas rápidas de tensão forçam picos de corrente nas metalizações."),
        ("ESR / tan δ", f"Declarar ESR na frequência de chaveamento (referência {capd.get('esr_mohm', '–')} mΩ)",
         "Com a ESR a plataforma calcula as perdas e o ponto quente."),
        ("Ponto quente / ambiente", f"Ponto quente máx. ≥ {lc['t_hot']:g} °C; ambiente até 55 °C no painel; estimado {R['t_hot']:.0f} °C",
         "Vida do filme de polipropileno dobra a cada ~7 °C a menos."),
        ("Vida útil", f"Declarar vida (h) na temperatura de ponto quente; estimado {R['vida']:,.0f} h".replace(",", "."),
         "Filtros trabalham 24 h em bombeamento."),
        ("Proteção", "Dispositivo de sobrepressão (desconexão interna) obrigatório", "Falha segura no fim de vida, sem explosão."),
        ("Descarga", f"Resistor de descarga ({b.r_descarga_mohm * 1000:.0f} kΩ) interno ou externo", "Segurança na manutenção (IEC 61071 / NR-10)."),
        ("Isolação terminais–caixa", f"≥ {capd.get('ui_kv', 3):g} kV", "Caixa metálica aterrada no painel."),
        ("Lote / data", "Data de fabricação ≤ 12 meses; mesmo lote por filtro", "Capacitância casada entre fases; estoque antigo perde vida."),
        ("Quantidade", f"{R['n_nec']} peças ({b.n_total} por filtro × {q})" + (f" – {R['est']} em estoque, comprar {R['n_comp']}" if R['est'] else ""), "")],
        [3.6, 7.0, 6.4], 8)

    d.add_heading("4. Dados que o fornecedor deve DECLARAR", 1)
    _tabela(d, ["Dado", "Unidade", "Por quê"], [
        ("Código completo e fabricante", "–", "Rastreabilidade; evitar substituição"), ("Norma do produto", "–", "IEC 61071 obrigatório"),
        ("Capacitância e tolerância", "µF / %", "Ressonância"), ("URMS e UN (pico recorrente)", "V", "Tensão de pico"),
        ("Imax RMS (e a que temperatura)", "A", "Aquecimento"), ("Î pico repetitivo e surto", "A", "dv/dt"),
        ("ESR a 10 kHz (ou na fs) e tan δ", "mΩ / –", "Perdas e ponto quente"), ("Ponto quente máx. e vida", "°C / h", "Vida útil"),
        ("Dispositivo de sobrepressão", "sim/não", "Segurança"), ("Data de fabricação do lote", "–", "Vida em estoque"),
        ("Preço, prazo, garantia", "–", "")], [7.5, 2.5, 7])

    d.add_heading("5. Ensaios e recebimento", 1)
    _bullets(d, ["Certificado do fabricante por lote: capacitância, tan δ, ensaio de tensão entre terminais e terminais–caixa (rotina IEC 61071).",
                 "No recebimento (Electric): medir a capacitância de cada peça (±5 %) e conferir código, data e lote na placa.",
                 "Datasheet atualizado do item fornecido anexado à nota."])
    d.add_heading("6. Critérios de aceitação", 1)
    _bullets(d, [f"Código {b.pn} ou substituto aprovado por escrito; norma IEC 61071.",
                 "Imax, UN e Î do datasheet ≥ os valores do item 3.",
                 "Capacitância medida dentro de ±5 %; dispersão entre peças do mesmo filtro ≤ 3 %.",
                 "Data de fabricação ≤ 12 meses.",
                 "Capacitor de correção de FP (IEC 60831) ou sem dispositivo de sobrepressão: REJEIÇÃO, com troca por conta do fornecedor."])
    return R


def corpo_email(proj, cat, ped, q, ola, ref_fornecedor=None):
    R = requisitos(proj, cat, ped, q)
    b, lc = R["b"], R["lc"]
    qtd = (f"{R['n_comp']} peças (necessidade {R['n_nec']}; {R['est']} em estoque)" if R["est"] else
           f"{R['n_nec']} peças (+ 2 de reserva, se o preço for o mesmo)")
    return (f"{ola}\n\nPreciso de cotação dos capacitores abaixo para filtro senoidal (ET detalhada em anexo):\n\n"
            f"- Código: {b.pn} ({b.fabricante} – {b.linha})\n"
            f"- {b.uf_unit:g} µF ±5 % / {b.v_unit:g} V RMS, monofásico MKP, {lc['norma_txt']}\n"
            f"- Quantidade: {qtd}\n\n"
            "IMPORTANTE – APLICAÇÃO EM FILTRO SENOIDAL (não é correção de fator de potência)\n"
            f"Cada capacitor conduz {R['i_rms']:.1f} A RMS, dos quais {R['i_hf']:.1f} A são de alta frequência ({R['fs'] / 1000:g} kHz e "
            f"múltiplos), com pico de tensão de ≈ {R['vpk']:.0f} V. Por isso preciso de capacitor de eletrônica de potência (IEC 61071) com:\n"
            f"- Imax ≥ {max(R['imax_req'], lc['imax']):.1f} A RMS\n"
            f"- UN (pico recorrente) ≥ {max(R['vpk_req'], lc['vpk']):.0f} V\n"
            f"- Î ≥ {max(R['ipk_nec'] * 1.5, R['capd'].get('ipk_a', 0) or 0):.0f} A\n"
            "- dispositivo de sobrepressão, ESR declarada, data de fabricação ≤ 12 meses\n\n"
            "Não posso aceitar substituto de correção de fator de potência (IEC 60831), mesmo com a mesma capacitância e tensão: "
            "ele aquece com a corrente de alta frequência e a vida útil cai. Se o item não estiver disponível, favor enviar o "
            "datasheet do substituto ANTES de faturar.\n\n"
            "Favor informar preço unitário, prazo/estoque, data de fabricação do lote e enviar o datasheet e o certificado do lote."
            + (f"\n\nReferência: {ref_fornecedor}." if ref_fornecedor else ""))
