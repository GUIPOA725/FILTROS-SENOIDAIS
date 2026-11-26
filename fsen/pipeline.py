"""Fluxo completo: pedido -> dimensionamento -> simulação -> desenhos -> documentos -> custos -> histórico."""
from __future__ import annotations
import os
import math
import re
import json
import shutil
import datetime as _dt

from .modelos import Pedido
from .dimensionamento import dimensionar, carregar_catalogo, _json_default
from .mecanica import projetar_arranjo
from .custos import montar_bom, formar_preco
from .graficos import gerar_todos
from .desenhos import gerar_desenhos, proj_codigo
from . import documentos as D
from . import historico as H

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def pasta_cliente(nome: str) -> str:
    """Nome legível da pasta do cliente: sem sufixos societários e caracteres inválidos no Windows."""
    n = re.sub(r"\(.*?\)", " ", nome or "")
    n = re.sub(r"\b(LTDA|LTDA\.|S/?A|S\.A\.|EIRELI|ME|EPP|REVENDA)\b\.?", " ", n, flags=re.I)
    n = re.sub(r'[<>:"/\\|?*]', " ", n)
    n = re.sub(r"\s+", " ", n).strip(" .-_–—")
    return n[:60] or "Cliente sem nome"


def _norm(t):
    import unicodedata
    t = unicodedata.normalize("NFKD", t or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]", "", t)


def _achar_pasta_cliente(pasta_base, cliente):
    """Reaproveita a pasta do cliente que já existe (ignora acentos, maiúsculas e pontuação)."""
    alvo = pasta_cliente(cliente)
    try:
        n = _norm(alvo)
        for d in os.listdir(pasta_base):
            if os.path.isdir(os.path.join(pasta_base, d)) and (_norm(d) == n or (len(n) > 5 and (_norm(d).startswith(n) or n.startswith(_norm(d))) and len(_norm(d)) > 5)):
                return d
    except FileNotFoundError:
        pass
    return alvo


def _slug(s):
    s = re.sub(r"[^\w\s-]", "", s or "", flags=re.U).strip()
    return re.sub(r"\s+", "_", s)[:40] or "cliente"


def _estudo_camadas(proj, cat, ind_pre, construcao_gap, condutor_ind, log):
    """Refaz o projeto do indutor com 1, 2 e 3 camadas (mesmas regras) – compara massa, perdas, elevação e dimensões."""
    from . import ind_projeto as IP
    out = []
    n0 = ind_pre["fio"]["n_cam"]
    _c0 = IP.CAMADAS_FIO
    for n in (1, 2, 3):
        try:
            if n == n0:
                d = ind_pre
            else:
                IP.CAMADAS_FIO = (n,)
                d = IP.projetar(proj, cat, log=lambda m: None, construcao=construcao_gap, condutor=condutor_ind)
            f = d["fio"]
            out.append(dict(n_cam=n, escolhido=(n == n0), N=d["N"], n_ax=f["n_ax"], barra=f"{f['t']*1e3:.1f}×{f['h']*1e3:.1f}",
                            coluna=f"{d['a']*1e3:.0f}×{d['b']*1e3:.0f}", janela=f"{d['ww']*1e3:.0f}×{d['hw']*1e3:.0f}",
                            massa_kg=round(d["massa_kg"]["total"], 1), perdas_w=round(d["perdas"]["total"], 0),
                            elev_k=round(d["termico"]["elev_bobina_K"], 0), dims_mm=d["dims_mm"], avisos=len(d.get("avisos") or []),
                            saidas="em cima e embaixo" if n % 2 else "as duas em cima", custo=round(float(d.get("custo") or 0), 0)))
            log(f"   Estudo de camadas: {n} camada(s) → {out[-1]['massa_kg']} kg, {out[-1]['perdas_w']} W, {out[-1]['elev_k']} K")
        except Exception as e:
            out.append(dict(n_cam=n, erro=f"{type(e).__name__}: {e}"))
            log(f"   Estudo de camadas: {n} camada(s) sem solução ({type(e).__name__})")
        finally:
            IP.CAMADAS_FIO = _c0
    return out


def _verificacao_indutor(ind, proj, pasta_eng, cod, verificar, log, arqs, cat=None):
    """v1.11.8: planilha de resultados medidos, script FEMM e (se o NGSolve estiver instalado) a comparação com outro software."""
    try:
        from . import calibracao as CAL, ind_verificacao as V
        arqs["indutor_planilha_medidos"] = CAL.planilha(ind, os.path.join(pasta_eng, f"Resultados_Medidos_Indutor_{cod}.xlsx"), cod)
        arqs["indutor_femm"] = V.femm_lua(ind, os.path.join(pasta_eng, f"Verificacao_FEMM_{cod}.lua"))
        est = getattr(proj, "_estudo_camadas", None)
        if est:
            json.dump(est, open(os.path.join(pasta_eng, "estudo_camadas_indutor.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        if verificar and V.disponivel():
            log("   Indutor: verificação independente no NGSolve (2D + 3D, alguns minutos)...")
            cmp = V.comparar(ind, log=log)
            cmp["estudo_camadas"] = est
            if cmp.get("ng_L3d") is not None:              # v1.28.0 (REQ-SEN-022): equaliza as 3 fases pelo 3D independente
                try:
                    aj = V.ajuste_gap_3d(ind, cmp["ng_L3d"])
                    if aj:
                        ind["ajuste_gap_3d"] = aj
                        ind["gaps"] = aj["gaps"]
                        ind["L3d_ng_previsto"] = aj["L3_ng_previsto"]
                        cmp["ajuste_gap_3d"] = aj
                        cmp["L_alvo"] = float(ind["requisitos"]["L"])
                        _ngp = ind["ng"]                # (Python 3.11: sem aspas iguais aninhadas em f-string)
                        _gp = ", ".join(f"{g / _ngp * 1e3:.2f}" for g in aj["gaps"])
                        _gp0 = ", ".join(f"{g / _ngp * 1e3:.2f}" for g in aj["gaps_antes"])
                        txt = (f"Entreferro ajustado pela verificação 3D independente: por peça {_gp} mm "
                               f"(antes {_gp0} mm); L 3D "
                               f"{', '.join(f'{x * 1e6:.1f}' for x in aj['L3_ng_antes'])} → {', '.join(f'{x * 1e6:.1f}' for x in aj['L3_ng_previsto'])} µH, "
                               f"desequilíbrio {aj['deseq_antes_pct']:.1f} % → {aj['deseq_previsto_pct']:.1f} %. Confirmar na 1ª peça (ajuste por calço, tabela 3.3 do protocolo).")
                        log("   Indutor: " + txt)
                        ind.setdefault("avisos", []).append(txt)
                except Exception as _ea:
                    log(f"   (ajuste do entreferro pelo 3D não calculado: {type(_ea).__name__}: {_ea})")
            V.salvar_cmp(cmp, os.path.join(pasta_eng, "verificacao_indutor.json"))
            arqs["indutor_verificacao"] = V.relatorio(ind, cmp, os.path.join(pasta_eng, f"Verificacao_Independente_Indutor_{cod}.pdf"))
            _lc = V.linhas_comparacao(cmp)
            if cmp.get("ajuste_gap_3d"):                   # depois do ajuste valem as linhas "APÓS o ajuste"
                _lc = [l for l in _lc if not (l[0].startswith("L 3D fase") and "APÓS" not in l[0]) and not l[0].startswith("Desequilíbrio entre")]
            nok = sum(1 for l in _lc if l[-1] != "OK")
            log(f"   Indutor: verificação independente concluída – {('todas as grandezas dentro do critério' if nok == 0 else f'{nok} fora do critério')}")
            if nok:
                proj.avisos = list(getattr(proj, "avisos", []) or []) + [
                    f"Verificação independente do indutor (NGSolve): {nok} grandeza(s) fora do critério – ver Verificacao_Independente_Indutor."]
        elif verificar:
            log("   (verificação independente: NGSolve não instalado – pip install ngsolve)")
        if verificar and cat is not None:                  # v1.12.0: análise avançada (formas de onda do circuito, 3D, térmico)
            try:
                from . import ind_avancado as AV
                log("   Indutor: análise avançada – formas de onda do circuito, núcleo no tempo, 3D, mapa térmico...")
                av = AV.avaliar(ind, proj, cat, log=log, fazer_3d=V.disponivel())
                figs = AV.figuras(av, pasta_eng, cod)
                AV.salvar(av, os.path.join(pasta_eng, "avancado_indutor.json"))
                arqs["indutor_avancado"] = AV.relatorio(ind, av, os.path.join(pasta_eng, f"Analise_Avancada_Indutor_{cod}.pdf"), figs)
                ind["avancado"] = dict(perdas=av["perdas"], termico={k: v for k, v in av["termico"].items() if k != "iteracoes"})
                tf = AV.adotar_pior(ind, av)               # v1.26.4 (REQ-GER-014): resultado final = o mais severo
                _tc = float(ind["requisitos"].get("classe_cliente_C") or 0)
                if _tc and tf["ponto_quente_C"] > _tc and tf["limite_C"] > _tc:      # v1.27.1 (REQ-SEN-021)
                    proj.avisos = list(getattr(proj, "avisos", []) or []) + [
                        f"Indutor em classe H (padrão Electric para filtro senoidal): ponto quente {tf['ponto_quente_C']:.0f} °C, acima dos "
                        f"{_tc:.0f} °C da classe pedida pelo cliente e dentro dos {tf['limite_C']:.0f} °C da classe H. Informar na proposta "
                        "que a isolação ofertada é classe H (superior à solicitada) e obter o aceite do cliente por escrito."]
                if tf["status"] != "APROVADO":
                    proj.avisos = list(getattr(proj, "avisos", []) or []) + [
                        f"Indutor – térmica {tf['status']}: ponto quente {tf['ponto_quente_C']:.0f} °C (pior entre projeto e análise avançada) × "
                        f"limite {tf['limite_C']:.0f} °C da classe pedida (folga {tf['margem_K']:.0f} K; mínimo {tf['margem_min_K']:.0f} K)."]
                for a_ in av.get("avisos", []):
                    proj.avisos = list(getattr(proj, "avisos", []) or []) + [f"Indutor (análise avançada): {a_}"]
            except Exception as e:
                log(f"   (análise avançada do indutor não concluída: {type(e).__name__}: {e})")
    except Exception as e:
        log(f"   (verificação do indutor não concluída: {type(e).__name__}: {e})")


def processar(ped: Pedido, pasta_base: str = None, cat=None, registrar=True, zipar=True, log=print, projeto=None, topologias=None, capacitores=None,
              ligacoes=None, prioridade="custo", queda_max=None, corrente_base="carga", construcao_gap="culatra_fio", condutor_ind="barra_cu",
              verificar_ind=True, estudo_camadas=False, leitura_fonte=None):
    """projeto: um Projeto já pronto (ex.: ajuste manual). Se None, roda a otimização global."""
    cat = cat or carregar_catalogo()
    pasta_base = pasta_base or os.path.join(RAIZ, "saidas")
    t0 = _dt.datetime.now()
    log("1/7 Dimensionando e otimizando (L, C, amortecimento)...")
    import copy as _copy
    ped = _copy.deepcopy(ped)                       # v1.11: não altera o pedido da tela (a corrente é redefinida pela carga)
    if projeto is not None:
        proj = projeto
        cat = getattr(projeto, "_cat", cat)
        _cc0 = getattr(projeto, "corrente_dimensionamento", None) or {}
        if _cc0.get("base") == "carga":             # ajuste manual: mantém a corrente térmica definida pela carga
            if getattr(ped, "corrente_cliente_a", None) in (None, 0, 0.0):
                ped.corrente_cliente_a = float(_cc0.get("i_cliente_a") or ped.corrente_a)
            ped.corrente_a = float(_cc0["i_term_a"])
        if not getattr(proj, "_sims", None):
            from .dimensionamento import projeto_manual, config_de_projeto
            cfg = config_de_projeto(proj)
            proj2 = projeto_manual(ped, cat, **cfg)
            proj2._otimizacao = getattr(proj, "_otimizacao", None)
            proj = proj2
        try:                                    # v1.11: mantém a base de corrente no ajuste manual
            from . import corrente_carga as CC
            _cc0 = getattr(projeto, "corrente_dimensionamento", None) or {}
            if _cc0.get("base") == "carga" or getattr(ped, "corrente_cliente_a", None):
                _cc = CC.exata_do_projeto(ped, cat, proj)
                _cc["i_term_a"] = float(ped.corrente_a)
                proj.corrente_dimensionamento = _cc
            elif _cc0:
                proj.corrente_dimensionamento = _cc0
        except Exception as e:
            log(f"   (base de corrente não recalculada: {e})")
    def _dim():
        proj = dimensionar(ped, cat, log=log, topologias=topologias, capacitores=capacitores, ligacoes=ligacoes)
        if prioridade == "mercado" and proj.topologia == "LC" and not proj.l2:
            # v1.9.11: indutor na faixa de mercado (MTE 8–10 %) e MENOS capacitores, aprovado e robusto (L ±10 %, C ±5 %)
            try:
                from . import ponto_otimo as PO
                from .dimensionamento import projeto_manual
                log("   Prioridade 'indutor de mercado / menos capacitores': varrendo opções...")
                _caps = capacitores or None
                _ops = PO.otimizar_mercado(ped, cat, proj.fs_hz / 1000, caps=_caps, ligacoes=tuple(ligacoes or ("Delta", "Estrela")))
                if _ops:
                    o = _ops[0]
                    _otim = getattr(proj, "_otimizacao", None)
                    proj = projeto_manual(ped, cat, proj.fs_hz / 1000, o["L_uh"], o["cap_id"], o["ligacao"], o["n_por_ramo"])
                    proj._otimizacao = _otim
                    proj.avisos = [a for a in (getattr(proj, "avisos", []) or []) if "definida manualmente" not in a] + [
                        f"Configuração escolhida pela prioridade 'indutor de mercado / menos capacitores' (uk {o['uk_pct']} %, "
                        f"{o['n_caps']} capacitores, robusta a L ±10 % e C ±5 %)."]
                    log(f"   → {o['L_uh']:.0f} µH + {o['n_caps']} × {o['cap_id']} ({o['ligacao']})")
                else:
                    log("   Nenhuma opção de mercado robusta – mantida a otimização por custo")
            except Exception as e:
                log(f"   (prioridade de mercado não aplicada: {e})")
        elif prioridade == "min_caps" and proj.topologia == "LC" and not proj.l2:
            # v1.9.13: capacitor FORÇADO (estoque) e o MÍNIMO de capacitores, compensando no indutor, com queda máxima
            try:
                from . import opcoes_caps as OC
                from .dimensionamento import projeto_manual
                _caps = list(capacitores or [proj.banco.cap_id])
                _ligs = tuple(ligacoes or ("Delta", "Estrela"))
                _qm = float(queda_max or OC.QUEDA_MAX_PADRAO)
                log(f"   Prioridade 'mínimo de capacitores': {', '.join(_caps)} ({', '.join(_ligs)}), queda ≤ {_qm:g} % – varrendo casos...")
                _est = OC.varrer(ped, cat, proj.fs_hz / 1000, _caps, _ligs, queda_max=_qm, log=log)
                o = _est["recomendada"]
                if o:
                    _otim = getattr(proj, "_otimizacao", None)
                    proj = projeto_manual(ped, cat, proj.fs_hz / 1000, o["L_uh"], o["cap_id"], o["ligacao"], o["n_por_ramo"])
                    proj._otimizacao = _otim
                    proj.avisos = [a for a in (getattr(proj, "avisos", []) or []) if "definida manualmente" not in a] + [
                        f"Configuração escolhida pela prioridade 'mínimo de capacitores' com capacitor forçado ({o['cap_id']}): "
                        f"{o['n_caps']} capacitores, queda {o['queda']} % (≤ {_qm:g} %), robusta a L ±10 % e C ±5 %."]
                    log(f"   → {o['L_uh']:.0f} µH + {o['n_caps']} × {o['cap_id']} ({o['ligacao']})")
                else:
                    log("   Nenhum caso válido com o capacitor forçado – mantida a otimização por custo")
                proj.estudo_opcoes = _est
            except Exception as e:
                log(f"   (prioridade 'mínimo de capacitores' não aplicada: {type(e).__name__}: {e})")
        return proj

    if projeto is None:
        # v1.11: corrente definida pela Electric a partir da carga ("o cobre vai pela carga, o ferro vai pelo inversor")
        from . import corrente_carga as CC
        if getattr(ped, "corrente_cliente_a", None) in (None, 0, 0.0):
            ped.corrente_cliente_a = float(ped.corrente_a or 0)
        cc = None
        if corrente_base == "carga":
            cc = CC.calcular(ped, cat)
            if cc["base"] == "carga":
                ped.corrente_a = cc["i_term_a"]
                log(f"   Corrente térmica pela carga (1ª passada): {cc['i_term_a']:.0f} A "
                    f"(cliente pediu {ped.corrente_cliente_a:g} A; inversor {ped.inversor_corrente_a or '-'} A)")
        proj = _dim()
        if corrente_base == "carga" and cc and cc["base"] == "carga":
            cc = CC.exata_do_projeto(ped, cat, proj)
            if cc["i_term_a"] > ped.corrente_a or cc["i_term_a"] < ped.corrente_a * 0.97:   # placa nunca abaixo da exata
                log(f"   Corrente recalculada com o banco e o ripple simulados: {cc['i_term_a']:.0f} A – redimensionando...")
                ped.corrente_a = cc["i_term_a"]
                proj = _dim()
                cc = CC.exata_do_projeto(ped, cat, proj)
            cc["i_term_a"] = float(ped.corrente_a)        # placa = a corrente usada no dimensionamento
            log(f"   Corrente térmica de projeto: {ped.corrente_a:.0f} A | Isat ≥ {cc['isat_a']:.0f} A pico | "
                f"sobrecarga do inversor {cc['iovl_a']:.0f} A pico")
            for n in cc.get("notas", []):
                log("   ! " + n)
        elif cc is None:
            cc = dict(base="cliente", i_term_a=float(ped.corrente_a), i_cliente_a=float(ped.corrente_cliente_a or 0),
                      i_inversor_a=float(ped.inversor_corrente_a or 0), componentes=[],
                      notas=["Opção 'usar a corrente informada pelo cliente' marcada."])
        proj.corrente_dimensionamento = cc
        if isinstance(proj.pedido, dict):
            proj.pedido["corrente_cliente_a"] = ped.corrente_cliente_a
        proj.avisos = list(getattr(proj, "avisos", []) or []) + [n for n in cc.get("notas", [])]
    cod = proj_codigo(proj)
    sufixo = f"_AJUSTE-MANUAL-{t0:%H%M}" if projeto is not None else ""
    # uma pasta por cliente; dentro, um projeto por solicitação: PROJETOS\<Cliente>\<data>_<código>
    pasta = os.path.join(pasta_base, _achar_pasta_cliente(pasta_base, ped.cliente), f"{t0:%Y-%m-%d}_{cod}{sufixo}")
    if os.path.exists(pasta) and not sufixo:          # mesma solicitação reprocessada no mesmo dia: não sobrescreve
        pasta += f"_{t0:%H%M}"
    sub = {k: os.path.join(pasta, k) for k in ("01_Engenharia", "02_Cliente", "03_Fornecedores", "04_Montadora", "05_Desenhos", "graficos")}
    for p in sub.values():
        os.makedirs(p, exist_ok=True)
    similares = H.buscar_similares(ped.tensao_v, ped.corrente_a, proj.topologia)
    ind_pre = None
    if proj.topologia == "LC" and not proj.l2 and (cat.get("indutor_fem") or {}).get("habilitado", True):
        try:                                        # v1.11.1: indutor por FEM ANTES do painel – o painel usa as dimensões reais
            from . import ind_projeto as IP
            _nome_c = {"culatra_fio": ("2 por coluna nas culatras + barra retangular de cobre única por espira" if condutor_ind == "barra_cu"
                                       else "2 por coluna nas culatras + fio/barra retangular (busca livre)"),
                       "culatra": "2 por coluna nas culatras + folha (não recomendado)"}.get(construcao_gap, "distribuídos (multigap) + folha")
            log(f"   Indutor: projeto de referência por elementos finitos – entreferros {_nome_c} (alguns minutos)...")
            # v1.26.4 (REQ-SEN-020): a meta de elevação agora respeita a classe PEDIDA pelo cliente com 10 K de folga. Se a barra
            # única não tiver solução, tenta condutores em paralelo; só depois abre mão da folga – e AVISA (nunca em silêncio).
            _t_cli = IP._temp_classe_cliente((proj.pedido if isinstance(proj.pedido, dict) else proj.pedido.__dict__).get("classe_temp"))
            _alvo_sem_folga = max(_t_cli - 50.0 - IP.PONTO_QUENTE_ACRESCIMO_K, 40.0)
            _tent = [(condutor_ind, None, None)]
            if construcao_gap == "culatra_fio" and condutor_ind != "livre":
                _tent.append(("livre", None, "barra única sem solução com a folga térmica – usado fio/barra em paralelo (transposto)"))
            _tent.append((condutor_ind, _alvo_sem_folga, f"sem solução com 10 K de folga – projetado SEM a folga (meta {_alvo_sem_folga:.0f} K): "
                          "ponto quente no limite da classe pedida; avaliar classe superior com o cliente ou indutor maior"))
            if construcao_gap == "culatra_fio" and condutor_ind != "livre":
                _tent.append(("livre", _alvo_sem_folga, f"sem solução com 10 K de folga – fio/barra em paralelo e SEM a folga (meta {_alvo_sem_folga:.0f} K)"))
            ind_pre, _err = None, None
            for _cnd, _alvo, _nota in _tent:
                IP.ALVO_ELEV_EXT = _alvo
                try:
                    ind_pre = IP.projetar(proj, cat, log=log, construcao=construcao_gap, condutor=_cnd)
                except RuntimeError as _e1:
                    _err = _e1
                    log(f"   Indutor ({_cnd}{'' if _alvo is None else f', meta {_alvo:.0f} K'}): {_e1} – tentando a próxima opção")
                    continue
                finally:
                    IP.ALVO_ELEV_EXT = None
                condutor_ind = _cnd
                if _nota:
                    proj.avisos = list(getattr(proj, "avisos", []) or []) + [f"Indutor: {_nota}."]
                    log(f"   Indutor: {_nota}")
                break
            if ind_pre is None:
                raise _err or RuntimeError("indutor sem solução")
            _tfp = None
            if verificar_ind:                       # v1.26.4 (REQ-GER-014): fecha a térmica com a análise avançada ANTES do painel
                try:
                    from .pipeline_banco import _fechar_termica
                    from . import ind_avancado as _AVp

                    def _refazer(alvo):
                        IP.ALVO_ELEV_EXT = alvo
                        try:
                            return IP.projetar(proj, cat, log=lambda *_a: None, construcao=construcao_gap, condutor=condutor_ind)
                        finally:
                            IP.ALVO_ELEV_EXT = None
                    log("   Indutor: fechamento térmico com a análise avançada (formas de onda do circuito + mapa térmico)...")
                    ind_pre = _fechar_termica(ind_pre, None, _refazer, log, proj=proj, cat=cat)
                    _tfp = ind_pre.get("termico_final")
                except Exception as _ext:
                    log(f"   (fechamento térmico do indutor não concluído: {type(_ext).__name__}: {_ext})")
            _p_est = float(proj.l1.perdas_w or 0)
            _r = ind_pre["requisitos"]
            _p_lim = float(ind_pre["perdas"]["total"]) * 1.15
            if _r.get("P_max"):
                _p_lim = min(_p_lim, float(_r["P_max"]) * float(_r.get("k_Pmax") or 1))
            _p_lim = max(_p_lim, float(ind_pre["perdas"]["total"]), float((_tfp or {}).get("perdas_W") or 0))
            _dm = ind_pre["dims_mm"]
            proj.l1.perdas_w = round(_p_lim, 0)                 # TETO garantido (cálculo + 15 %) – não é "estimativa"
            proj._ind_perdas_calc_w = round(float((_tfp or {}).get("perdas_W") or ind_pre["perdas"]["total"]), 0)
            proj.l1.dim_mm = [int(math.ceil(_dm["largura"] / 10) * 10), int(math.ceil(_dm["altura"] / 10) * 10),
                              int(math.ceil(_dm["profundidade"] / 10) * 10)]
            proj.l1.massa_kg = round(float(ind_pre["massa_kg"]["total"]), 0)
            proj._ind_fem_termico = dict(elev=float((_tfp or {}).get("elev_K") or ind_pre["termico"]["elev_bobina_K"]),
                                         p=float((_tfp or {}).get("perdas_W") or ind_pre["perdas"]["total"]),
                                         limite_c=float(ind_pre["termico"]["limite_temp_C"]),
                                         metodo=(_tfp or {}).get("metodo") or "método de projeto")
            proj._ind_chapa = dict(nome=ind_pre["chapa_dados"]["nome"], esp=float(ind_pre["chapa_dados"]["esp_mm"]),
                                   massa_nucleo=float(ind_pre["massa_kg"]["nucleo"]))
            proj.avisos = list(getattr(proj, "avisos", []) or []) + [
                f"Painel dimensionado com o indutor do projeto por elementos finitos: {proj.l1.dim_mm[0]}×{proj.l1.dim_mm[1]}×"
                f"{proj.l1.dim_mm[2]} mm, {proj.l1.massa_kg:.0f} kg e perdas = limite contratual {proj.l1.perdas_w:.0f} W "
                f"(FEM {ind_pre['perdas']['total']:.0f} W + 15 %, teto de mercado); a estimativa simplificada era {_p_est:.0f} W."]
            log(f"   Painel usará o indutor FEM: {proj.l1.dim_mm} mm, {proj.l1.massa_kg:.0f} kg, perdas (limite) {proj.l1.perdas_w:.0f} W")
            if estudo_camadas and ind_pre.get("fio"):           # v1.11.8: variações de nº de camadas (saídas em cima/embaixo)
                proj._estudo_camadas = _estudo_camadas(proj, cat, ind_pre, construcao_gap, condutor_ind, log)
        except Exception as e:
            log(f"   (projeto do indutor por elementos finitos não concluído: {type(e).__name__}: {e})")
    log("2/7 Arranjo mecânico, térmica e cabos...")
    arr = projetar_arranjo(proj, cat)
    from .termico import aplicar_termico
    arr, _term = aplicar_termico(proj, arr, cat)
    log("   Dados faltantes: análise de sensibilidade das premissas...")
    try:
        from . import dados_faltantes as DF
        _ped_obj = Pedido.from_dict(proj.pedido) if isinstance(proj.pedido, dict) else proj.pedido
        _ped_obj.informados = ped.informados
        proj.dados_faltantes = DF.analisar(proj, cat, _ped_obj, log=log)
        log(f"   {len(proj.dados_faltantes['itens'])} itens a confirmar com o cliente "
            f"({proj.dados_faltantes['n_criticos']} críticos)")
    except Exception as e:
        proj.dados_faltantes = None
        log(f"   Dados faltantes: análise não concluída ({e})")
    log("3/7 Lista de material e preço...")
    itens = montar_bom(proj, arr, cat)
    orc = formar_preco(proj, itens, cat)
    log("4/7 Gráficos de simulação e da otimização...")
    graf = gerar_todos(proj, sub["graficos"])
    from .graficos import grafico_termico
    graf["termico"] = grafico_termico(proj, arr, sub["graficos"])
    df_opt = getattr(proj, "_otimizacao", None)
    if df_opt is not None and len(df_opt):
        from .graficos import grafico_pareto
        graf["pareto"] = grafico_pareto(df_opt, sub["graficos"])
        try:        # v1.32.0 (REQ-SEN-026, auditoria A&W A7): a tabela traz a configuração FINAL, os flags e o critério de desempate
            import pandas as _pd
            _d = df_opt.copy()
            if "robusto" in _d.columns:
                _d["robusto"] = _d["robusto"].map(lambda x: "não avaliado (fora das 10 de maior nota)" if x is None or x != x
                                                  else ("sim" if bool(x) else "não"))
            _lf = float(proj.l1.l_uh)
            _m = _pd.Series([False] * len(_d), index=_d.index)
            if "L1_uH" in _d.columns and "ligacao" in _d.columns:
                _m = ((_d["L1_uH"].astype(float) - _lf).abs() <= max(3.0, 0.02 * _lf)) & (_d["ligacao"] == proj.banco.ligacao)
                if "n_por_ramo" in _d.columns:
                    _m &= _d["n_por_ramo"].astype(float) == float(proj.banco.n_por_ramo)
            _d.insert(0, "escolhida", _m.map(lambda x: "SIM" if x else ""))
            _vt = next((v for v in proj.verificacoes if str(v.item).startswith("THD total no motor @")), None)
            _fin = {"escolhida": "FINAL (simulação fina)", "L1_uH": round(_lf, 1), "ligacao": proj.banco.ligacao,
                    "n_por_ramo": proj.banco.n_por_ramo, "C_y_uF": proj.banco.c_y_uf, "fr_Hz": round(proj.fr_hz),
                    "fs_khz": proj.fs_hz / 1000, "thd_pct": max(p["thd_v_saida_pct"] for p in proj.pontos),
                    "viavel": bool(proj.aprovado),
                    "obs": ("configuração final após a simulação fina e o ajuste do indutor (L de catálogo/FEM); "
                            f"THD total no motor {_vt.valor if _vt else '-'}; critério de escolha: maior nota ponderada entre as viáveis "
                            "e robustas (pesos em catalogo.yaml → otimizacao.pesos); desempate: menor custo, depois menor nº de capacitores")}
            _d = _pd.concat([_pd.DataFrame([_fin]), _d], ignore_index=True)
            _d.to_excel(os.path.join(sub["01_Engenharia"], f"{cod}_Otimizacao_todas_configuracoes.xlsx"), index=False)
        except Exception as _e:
            log(f"   Otimização: tabela com a final não gerada ({_e}) – gravando a original")
            df_opt.to_excel(os.path.join(sub["01_Engenharia"], f"{cod}_Otimizacao_todas_configuracoes.xlsx"), index=False)
    _atp_dupla_checagem(proj, cat, sub["01_Engenharia"], cod, log)
    log("5/7 Desenhos 2D/3D e diagrama elétrico...")
    pdf_des, pngs = gerar_desenhos(proj, arr, cat, sub["05_Desenhos"])
    esq_sen = {}
    try:        # v1.16.1: esquema elétrico no modelo QElectroTech + lista DE/PARA + etiquetas (fios, componentes, cabos)
        from .eplan import senoidal_qet as SQ
        from .versao import info as _vinfo
        desq = os.path.join(sub["05_Desenhos"], "1_Esquema_Eletrico")
        esq_sen = SQ.gerar(proj, arr, desq, cod, f"FSEN v{_vinfo().get('versao', '')}", log=log)
        for k_ in ("pdf", "qet", "dxf", "etq_xlsx", "etq_pdf"):
            shutil.copy(esq_sen[k_], sub["04_Montadora"])
    except Exception as e:
        log(f"   (esquema elétrico / etiquetas não gerados: {type(e).__name__}: {e})")
    log("6/7 Documentos (memorial, proposta, ETs, montagem, planilha)...")
    arqs = {
        "memorial": D.memorial(proj, arr, orc, graf, pngs, cat, sub["01_Engenharia"]),
        "planilha": D.planilha_custos(proj, arr, orc, cat, sub["01_Engenharia"]),
        "proposta": D.proposta(proj, arr, orc, cat, sub["02_Cliente"]),
        "folha_dados": D.folha_dados(proj, arr, cat, sub["02_Cliente"], pngs),
        "desenhos_pdf": pdf_des,
    }
    for k_ in ("pdf", "qet", "dxf", "etq_xlsx", "etq_pdf"):
        if esq_sen.get(k_):
            arqs[f"esquema_{k_}"] = esq_sen[k_]
    try:                                            # v1.9.11: estudo de ponto ótimo de mercado + robustez + referências
        from . import ponto_otimo as PO
        proj.estudo_mercado = PO.estudo(proj, cat, log=log)
        arqs["estudo_ponto_otimo"] = PO.gerar_docx(proj, cat, proj.estudo_mercado, sub["01_Engenharia"], D._novo, D._tabela, D._bullets)
        log("   Estudo de ponto ótimo e robustez gerado (01_Engenharia)")
    except Exception as e:
        log(f"   (estudo de ponto ótimo não gerado: {type(e).__name__}: {e})")
    if getattr(proj, "estudo_opcoes", None):
        try:
            from . import opcoes_caps as OC
            arqs["estudo_opcoes"] = OC.gerar_docx(proj, cat, proj.estudo_opcoes, sub["01_Engenharia"], D._novo, D._tabela, D._bullets)
            log("   Estudo de opções – mínimo de capacitores gerado (01_Engenharia)")
        except Exception as e:
            log(f"   (estudo de opções não gerado: {type(e).__name__}: {e})")
    ets = D.et_fornecedores(proj, arr, orc, cat, sub["03_Fornecedores"], pdf_des)
    for k, (doc, mail) in ets.items():
        arqs[f"et_{k}"] = doc
        if mail:
            arqs[f"email_{k}"] = mail
    ind = None
    if proj.topologia == "LC" and not proj.l2 and (cat.get("indutor_fem") or {}).get("habilitado", True):
        try:                                        # v1.10.0: projeto de referência do indutor por elementos finitos
            from . import ind_projeto as IP, ind_desenhos as IDS, auditoria as AUD
            from .versao import info as _vi
            ind = ind_pre
            if ind is None:
                raise RuntimeError("projeto FEM do indutor indisponível")
            ind["corrente_dimensionamento"] = getattr(proj, "corrente_dimensionamento", None) or {}
            # v1.28.0: a verificação independente roda ANTES dos desenhos e do memorial – se ela ajustar o entreferro da coluna
            # central, desenho, CAD e memorial já saem com o valor ajustado
            _verificacao_indutor(ind, proj, sub["01_Engenharia"], cod, verificar_ind, log, arqs, cat=cat)
            IDS.imagens_campo(ind, os.path.join(sub["01_Engenharia"], "Indutor_campo_FEM.png"))
            _inf = dict(titulo=f"Indutor trifásico p/ filtro senoidal – {proj.l1.l_uh:.0f} µH / {proj.l1.i_nom_a:.0f} A – {cod}",
                        linha2=f"Classe {ind['requisitos']['classe']} (sistema) | {ind['chapa_dados']['nome'][:48]} | {IP.descr_condutor(ind, curto=True)}",
                        cod=cod, data=f"{t0:%d/%m/%Y}", versao=f"FSEN v{_vi().get('versao')}")
            arqs["indutor_desenhos"] = IDS.gerar_pdf(ind, os.path.join(sub["03_Fornecedores"], f"Projeto_Referencia_Indutor_{cod}.pdf"),
                                                     _inf, png_dir=sub["01_Engenharia"])
            try:                                    # v1.10.4: CAD editável (STEP 3D + DXF 2D)
                from . import ind_cad as ICAD
                arqs["indutor_step"] = ICAD.gerar_step(ind, os.path.join(sub["03_Fornecedores"], f"Indutor_3D_{cod}.step"),
                                                       f"INDUTOR_{cod}")
                arqs["indutor_dxf"] = ICAD.gerar_dxf(ind, os.path.join(sub["03_Fornecedores"], f"Indutor_2D_{cod}.dxf"), _inf)
            except Exception as _e:
                log(f"   (CAD do indutor não gerado: {type(_e).__name__}: {_e})")
            arqs["indutor_memorial"] = AUD.memorial_indutor(ind, os.path.join(sub["03_Fornecedores"], f"Memorial_Indutor_{cod}.pdf"),
                                                            _inf["titulo"])
            with open(os.path.join(sub["01_Engenharia"], "indutor_projeto.json"), "w", encoding="utf-8") as f:
                json.dump({k: v for k, v in ind.items() if k not in ("campo_pico",)}, f, ensure_ascii=False, indent=1, default=_json_default)
            if True:                                # v1.31.0 (REQ-DOC-020): este texto vai para a ET (Word), não para o e-mail
                if True:
                    proj._txt_ref_indutor = (
                            "PROJETO DE REFERÊNCIA DO INDUTOR\n"
                            f"Seguem também o Projeto de Referência (desenhos com vistas, cortes, 3D e lista de materiais), os arquivos CAD "
                            f"editáveis (3D em STEP e 2D em DXF, escala 1:1) e o Memorial de "
                            f"cálculo por elementos finitos ({os.path.basename(arqs['indutor_desenhos'])}, {os.path.basename(arqs['indutor_memorial'])}). "
                            f"Ele foi calculado com as correntes e tensões reais do filtro: {ind['N']} espiras de {IP.descr_condutor(ind, curto=True)}, {ind['ng']} entreferros por "
                            f"coluna, bobina a {ind['c']*1e3:.0f} mm do núcleo, chapa {ind['chapa_dados']['esp_mm']} mm, sistema de isolação classe "
                            f"{ind['requisitos']['classe']}. Vocês podem adaptar ao padrão de fabricação de vocês – peço só que declarem as "
                            "diferenças (chapa, espiras, entreferros, condutor, isolação) para conferirmos.\n")
                    _fh = None
            try:                                    # v1.26.4 (REQ-REA-018): indutor salvo na biblioteca como proposta
                from . import biblioteca_reatores as _BRs
                _arq_b = _BRs.propor_senoidal(ind, cod, getattr(ped, "cliente", "") or "", pasta=pasta)
                log(f"   Indutor salvo na biblioteca de reatores como proposta (aguarda aprovação do engenheiro): {os.path.basename(_arq_b)}")
            except Exception as _exb:
                log(f"   (indutor não salvo na biblioteca: {type(_exb).__name__}: {_exb})")
            log(f"   Indutor: {ind['N']} espiras, {ind['ng']} entreferros/coluna, perdas ≈ {ind['perdas']['total']:.0f} W, "
                f"elevação ≈ {ind['termico']['elev_bobina_K']:.0f} K, massa ≈ {ind['massa_kg']['total']:.0f} kg")
        except Exception as e:
            log(f"   (projeto do indutor por elementos finitos não concluído: {type(e).__name__}: {e})")
    if proj.topologia == "LC" and not proj.l2:
        try:                                        # v1.11: protocolo do protótipo, questionário ao fabricante, fornecedores (interno)
            from . import doc_indutor_fornecedor as DIF
            arqs["indutor_protocolo"] = DIF.protocolo_prototipo(proj, cat, ind, sub["03_Fornecedores"], cod, D._novo, D._tabela, D._bullets)
            arqs["indutor_questionario"] = DIF.questionario_fabricante(proj, cat, sub["03_Fornecedores"], cod, D._novo, D._tabela, D._bullets)
            arqs["fornecedores_interno"] = DIF.fornecedores_interno(sub["01_Engenharia"], cod)
            if ind:                                 # v1.11.7: anexo técnico (mercado, literatura, normas, fabricação)
                try:
                    from . import doc_referencias_indutor as DRI
                    arqs["indutor_anexo_tecnico"] = DRI.gerar(ind, proj, os.path.join(
                        sub["03_Fornecedores"], f"Anexo_Tecnico_Referencias_Indutor_{cod}.pdf"), eng_dir=sub["01_Engenharia"])
                except Exception as _e:
                    log(f"   (anexo técnico do indutor não gerado: {type(_e).__name__}: {_e})")
            _anexos = sorted(f for f in os.listdir(sub["03_Fornecedores"])
                             if re.search(r"Indutor", f, re.I) and not f.startswith("Email_") and not f.endswith(".json"))
            proj._txt_extra_indutor = DIF.texto_email_extra(proj, ind, _anexos)   # v1.31.0: vai para a ET (Word)
            log("   Indutor: protocolo de ensaio do protótipo e questionário ao fabricante gerados (03_Fornecedores/1_Indutor)")
        except Exception as e:
            log(f"   (protocolo/questionário do indutor não gerados: {type(e).__name__}: {e})")
    try:                                            # v1.31.0 (REQ-DOC-020): ET completa no Word + e-mail curto, com os anexos reais
        D.finalizar_cotacoes(proj, cat, sub["03_Fornecedores"], cod)
        log("   Cotações: ET (Word) completas e e-mails curtos para indutor e capacitores")
    except Exception as _exf:
        log(f"   (finalização das ETs de cotação falhou: {type(_exf).__name__}: {_exf})")
    arqs["rfq_montagem"], arqs["email_montagem"] = D.rfq_montagem(proj, arr, orc, cat, sub["04_Montadora"])
    arqs["caderno_montagem"] = D.caderno_montagem(proj, arr, orc, cat, sub["04_Montadora"], pngs)
    shutil.copy(pdf_des, sub["04_Montadora"])
    # relatório técnico final (padrão RTM da Electric) – resultados Python + ATP + limites dos componentes
    try:
        from . import relatorio_final as RF
        _da = getattr(proj, "dupla_checagem_atp", None) or {}
        _atp = [dict(ponto=x["ponto"], tabela=x["tabela"]) for x in (_da.get("resultados") or [])] or None
        arqs["relatorio_final"] = RF.gerar(proj, {"arranjo": arr.to_dict()}, pasta, cat, atp=_atp,
                                           vistas_dir=os.path.join(sub["01_Engenharia"], "ATP"), log=log)
        log("   Relatório técnico final (RTM) gerado em 02_Cliente")
    except Exception as e:
        log(f"   (relatório técnico final não gerado: {type(e).__name__}: {e})")
    try:                                            # v1.10.0: relatório de auditoria (uso interno)
        from . import auditoria as AUD
        arqs["auditoria"] = AUD.gerar(proj, arr, orc, cat, pasta, ind=ind, graficos=graf, log=log)
    except Exception as e:
        log(f"   (relatório de auditoria não gerado: {type(e).__name__}: {e})")
    # resposta ao cliente
    email_cli = _email_cliente(proj, orc, cat)
    with open(os.path.join(sub["02_Cliente"], "Email_Resposta_Cliente.txt"), "w", encoding="utf-8") as f:
        f.write(email_cli)
    arqs["email_cliente"] = os.path.join(sub["02_Cliente"], "Email_Resposta_Cliente.txt")
    if getattr(proj, "dados_faltantes", None) and proj.dados_faltantes["itens"]:
        from . import dados_faltantes as DF
        txt = DF.email_cliente(proj.dados_faltantes, proj, cat)
        arqs["email_dados"] = os.path.join(sub["02_Cliente"], "Email_Solicitacao_Dados_Tecnicos.txt")
        with open(arqs["email_dados"], "w", encoding="utf-8") as f:
            f.write(txt)
        arqs["questionario"] = DF.questionario_docx(proj.dados_faltantes, proj, cat,
                                                    os.path.join(sub["02_Cliente"], f"{cod}_Questionario_Tecnico.docx"))
        arqs["sensibilidade"] = DF.salvar_sensibilidade(proj.dados_faltantes,
                                                        os.path.join(sub["01_Engenharia"], f"{cod}_Sensibilidade_Dados_Faltantes.xlsx"))
    try:                                            # v1.23.2: mesmo padrão do banco – folha de dados + verificação de normas com Check
        from . import normas_senoidal as NS
        from .versao import info as _vin
        arqs["normas"], _ = NS.gerar_pdf(proj, arr, cod, os.path.join(sub["01_Engenharia"], "5_Normas_Folha_de_Dados"),
                                         versao=f"FSEN v{_vin().get('versao')}", log=log)
        shutil.copy(arqs["normas"], os.path.join(sub["02_Cliente"], os.path.basename(arqs["normas"])))
    except Exception as e:
        log(f"   (folha de dados / verificação de normas não gerada: {type(e).__name__}: {e})")
    # dados brutos
    ped.salvar(os.path.join(pasta, "pedido.json"))
    proj.salvar(os.path.join(sub["01_Engenharia"], "projeto.json"))
    with open(os.path.join(sub["01_Engenharia"], "arranjo_orcamento.json"), "w", encoding="utf-8") as f:
        json.dump({"arranjo": arr.to_dict(), "orcamento": orc.to_dict(), "similares": similares}, f, ensure_ascii=False, indent=2,
                  default=_json_default)
    try:                                            # v1.30.0 (REQ-SEN-024): comparação com os players mundiais (planilha + resumo)
        from . import players as _PL
        proj.players = _PL.de_projeto(proj, arr)
        arqs["players"] = _PL.salvar_xlsx(proj.players, os.path.join(sub["01_Engenharia"], f"Players_Mercado_Filtro_{cod}.xlsx"), cod)
        log(f"   Players mundiais: {len(proj.players['linhas'])} modelos vizinhos de {len(proj.players['fontes'])} fabricantes")
    except Exception as e:
        log(f"   (comparação com players não feita: {type(e).__name__}: {e})")
    try:                                            # v1.33.0 (REQ-INV-010): dados do inversor do MANUAL do fabricante (fonte/página/link)
        from . import inversor_manual as _IM
        _ineed = min(ped.corrente_a, (ped.motor_corrente_a or ped.corrente_a) * max(ped.fator_servico or 1.0, 1.0))
        proj.inversor_manual = _IM.gerar(ped, proj.fs_hz, sub["01_Engenharia"], cod, i_necessaria=_ineed, log=log)
        arqs["inversor_manual"] = proj.inversor_manual["arquivo"]
    except Exception as e:
        log(f"   (relatório do manual do inversor não feito: {type(e).__name__}: {e})")
    try:                                            # v1.34.0 (REQ-INV-011): motor e cabo pelos manuais/catálogos do fabricante
        from . import manuais_motor_cabo as _MC
        from .documentos import garantias as _gar
        proj.motor_cabo_manual = _MC.gerar(ped, proj, cat, sub["01_Engenharia"], cod, garantias=_gar(proj, cat), log=log)
        arqs["motor_cabo_manual"] = proj.motor_cabo_manual["arquivo"]
        from .dimensionamento import Verificacao as _V
        for _a, _b, _c, _d in proj.motor_cabo_manual["linhas"]:
            proj.verificacoes.append(_V(_a, _b, _c, _d == "OK", "manual/catálogo do fabricante – 01_Engenharia/7_Manuais_Tecnicos (REQ-INV-011)",
                                        critico=(_d == "REPROVADO")))
    except Exception as e:
        log(f"   (relatório de motor/cabo pelos manuais não feito: {type(e).__name__}: {e})")
    resumo = resumo_texto(proj, arr, orc, similares, pasta)
    with open(os.path.join(pasta, "RESUMO.md"), "w", encoding="utf-8") as f:
        f.write(resumo)
    try:                                            # v1.10.2: subpastas por tipo de documento / fornecedor
        from .organizar import organizar
        organizar(pasta, arqs, log)
    except Exception as e:
        log(f"   (organização em subpastas não aplicada: {e})")
    try:                                            # v1.27.0 (REQ-GER-016): nível de maturidade + pasta de evidências
        from . import maturidade as _MAT
        _av = _MAT.iniciar(pasta, cod, "Filtro senoidal", getattr(ped, "cliente", "") or "", log)
        with open(os.path.join(pasta, "RESUMO.md"), "a", encoding="utf-8") as f:
            f.write("\n".join(_MAT.md(_av)) + "\n")
    except Exception as e:
        log(f"   (maturidade do projeto não registrada: {type(e).__name__}: {e})")
    from .versao import carimbar_pasta
    carimbar_pasta(pasta, log)
    try:                                            # v1.19.0: relatório consolidado (tudo num PDF só) na raiz do projeto
        from . import consolidado as CONS
        from .versao import info as _vic
        _lt = dict(fonte=leitura_fonte or "", observacoes=getattr(ped, "observacoes", "") or "",
                   lacunas=list(getattr(ped, "lacunas", []) or []))
        arqs["consolidado"] = CONS.gerar(pasta, cod, f"Filtro senoidal – {proj.topologia if hasattr(proj, 'topologia') else ''} "
                                         f"{ped.corrente_a:g} A / {ped.tensao_v:g} V", f"FSEN v{_vic().get('versao')}",
                                         cliente=ped.cliente, projeto=getattr(ped, "projeto", "") or "", tipo="Filtro senoidal (saída de inversor)",
                                         leitura=_lt, log=log)
    except Exception as e:
        log(f"   (relatório consolidado não gerado: {type(e).__name__}: {e})")
    log("7/7 Registrando no histórico...")
    if registrar:
        H.registrar_projeto(proj, arr, orc, pasta)
    z = None
    if zipar:
        z = shutil.make_archive(pasta, "zip", pasta)
    log(f"Concluído em {(_dt.datetime.now() - t0).total_seconds():.1f} s → {pasta}")
    _op = None
    if getattr(proj, "estudo_opcoes", None):
        from . import opcoes_caps as OC
        _op = OC.tabela_ui(proj.estudo_opcoes)
    return dict(projeto=proj, arranjo=arr, orcamento=orc, pasta=pasta, zip=z, arquivos=arqs, graficos=graf, resumo=resumo,
                similares=similares, opcoes=_op)


def _atp_dupla_checagem(proj, cat, pasta_eng, cod, log):
    """Gera os decks .atp; se o ATP estiver instalado neste PC, roda em segundo plano e compara com o Python.
    SEMPRE registra o que aconteceu (rodou/convergiu, não instalado, falhou) em proj.dupla_checagem_atp e ATP/status_atp.json."""
    import time as _time
    from . import atp as A
    cfg = cat.get("atp", {})
    pasta_atp = os.path.join(pasta_eng, "ATP")
    st = dict(status="desabilitado", msg="Dupla checagem ATP desabilitada no catálogo (atp: habilitado: false).",
              hora=_dt.datetime.now().strftime("%d/%m/%Y %H:%M:%S"))
    proj.dupla_checagem_atp = st
    if not cfg.get("habilitado", True):
        return _salvar_status_atp(pasta_atp, st)
    t0 = _time.time()
    try:
        tp = A.achar_tpbig(cat)
        trab = os.path.join(cfg.get("pasta_trabalho", A.PASTA_TRABALHO_PADRAO), cod) if tp else pasta_atp
        casos = A.preparar_casos(proj, cat, trab)
        st.update(casos=[dict(nome=c["nome"], ponto=c["ponto"]) for c in casos], tpbig=tp,
                  atpdraw=[os.path.basename(c["atpdraw"]) for c in casos if c.get("atpdraw")])
        if not tp:
            if trab != pasta_atp:
                shutil.copytree(trab, pasta_atp, dirs_exist_ok=True)
            st.update(status="nao_instalado", msg="ATP (tpbig.exe) não encontrado neste computador – só os decks .atp foram gerados.")
            log("   ATP não encontrado neste computador – decks .atp gerados para rodar depois")
            st["vistas"] = _vistas(proj, casos, None, None, pasta_atp, log)
            return _salvar_status_atp(pasta_atp, st)
        log("   ATP: rodando a dupla checagem em segundo plano...")
        for c in casos:
            r = A.rodar_atp(os.path.join(trab, c["nome"] + ".atp"), tp)
            if not r["ok"]:
                st.update(status="falhou", msg=f"ATP falhou em {c['ponto']}: {r['msg'][-300:]}")
                log("   " + st["msg"])
                return _salvar_status_atp(pasta_atp, st)
        res = A.comparar_casos(casos, trab)
        os.makedirs(pasta_atp, exist_ok=True)
        A.salvar_relatorio(res, os.path.join(pasta_atp, f"{cod}_Comparacao_Python_x_ATP.xlsx"))
        pngs = [A.grafico_comparacao(c, trab, os.path.join(pasta_atp, f"comparacao_{c['nome']}.png")) for c in casos]
        for f in os.listdir(trab):
            if f.endswith((".atp", ".lis", ".bat", ".pl4", ".xml")):
                shutil.copy(os.path.join(trab, f), pasta_atp)
        conv = all(l["convergiu"] for x in res for l in x["tabela"])
        div = [f"{x['ponto'].replace('Operação ', '')}: {l['grandeza']} (Py {l['python']:g} × ATP {l['atp']:g} {l['unidade']}, {l['dif_pct']:+.0f} %)"
               for x in res for l in x["tabela"] if not l["convergiu"]]
        st.update(status="rodou", convergiu=conv, segundos=round(_time.time() - t0, 1), divergencias=div,
                  # v1.28.0 (REQ-SEN-022, auditoria §8): dizer o que a dupla checagem NÃO cobre – é teste do solver com o MESMO modelo
                  msg=("ATP rodou e CONVERGIU com o Python em todos os pontos (teste do solver com o mesmo modelo: PWM ideal sem tempo "
                       "morto, capacitor sem ESR, barramento CC ideal – não substitui a medição em campo nem a análise de ressonância)" if conv else
                       "ATP rodou e há DIVERGÊNCIA com o Python em " + "; ".join(div[:3])),
                  resultados=[dict(ponto=x["ponto"], tabela=x["tabela"]) for x in res], graficos=pngs,
                  vistas=_vistas(proj, casos, res, trab, pasta_atp, log))
        proj.dupla_checagem_atp = dict(st, resultados=res)
        log(f"   ATP × Python: {'CONVERGIU' if conv else 'DIVERGÊNCIA – revisar'}")
        try:
            st["mat_python"] = [os.path.basename(x) for x in A.exportar_python_mat(casos, pasta_atp)]
        except Exception as e:
            log(f"   (.mat do Python para o PlotXY não gerado: {e})")
        if cfg.get("abrir_ao_terminar", False) and os.name == "nt":
            ab = A.abrir_no_windows(pasta_atp, casos[0]["nome"], cat)
            st["aberto"] = ab
            log(f"   Abrindo no PlotXY: {ab['plotxy'] or '-'} | ATPDraw: {ab['atpdraw'] or '-'}")
    except Exception as e:  # a dupla checagem nunca bloqueia a emissão
        st.update(status="falhou", msg=f"Dupla checagem não concluída: {type(e).__name__}: {e}")
        log(f"   ATP: dupla checagem não concluída ({e})")
    return _salvar_status_atp(pasta_atp, st)


def _vistas(proj, casos, res, pasta_pl4, pasta_atp, log):
    """Rede elétrica com os valores dos dois programas, ondas lado a lado e espectro Python × ATP (um conjunto por ponto)."""
    try:
        from .vista_simulacao import gerar_vistas
        v = gerar_vistas(proj, casos, res, pasta_pl4, pasta_atp)
        return [{k: (os.path.basename(x) if k != "ponto" else x) for k, x in d.items()} for d in v]
    except Exception as e:
        log(f"   (vistas Python × ATP não geradas: {e})")
        return []


def _salvar_status_atp(pasta_atp, st):
    try:
        os.makedirs(pasta_atp, exist_ok=True)
        with open(os.path.join(pasta_atp, "status_atp.json"), "w", encoding="utf-8") as f:
            json.dump({k: v for k, v in st.items() if k != "resultados" or isinstance(v, list)}, f, ensure_ascii=False, indent=1,
                      default=str)
    except Exception:
        pass


def texto_atp(st):
    """Bloco do RESUMO com o resultado do ATP (sempre aparece, mesmo quando o ATP não rodou)."""
    if not st:
        return ["## Dupla checagem no ATP", "- ⚠️ sem registro (projeto gerado por versão antiga)", ""]
    ic = {"rodou": "✅" if st.get("convergiu") else "❌", "nao_instalado": "⚠️", "falhou": "❌", "desabilitado": "⚠️"}.get(st["status"], "⚠️")
    L = ["## Dupla checagem no ATP", f"- {ic} {st['msg']} ({st.get('hora', '')}"
         + (f", {st['segundos']} s" if st.get("segundos") else "") + ")"]
    if st.get("tpbig"):
        L.append(f"- Programa: `{st['tpbig']}`")
    for x in st.get("resultados") or []:
        L.append(f"- **{x['ponto']}** – Python × ATP:")
        for l in x["tabela"]:
            L.append(f"  - {'✅' if l['convergiu'] else '❌'} {l['grandeza']}: Python {l['python']:g} | ATP {l['atp']:g} {l['unidade']} "
                     f"(dif. {l['dif_pct']:+.1f} %, tolerância ±{l['tolerancia_pct']:g} %"
                     + (f" ou ±0,5 ponto percentual – diferença {abs(l['atp'] - l['python']):.2f} pp" if "THD" in l["grandeza"]
                        and abs(l["dif_pct"]) > l["tolerancia_pct"] else "") + ")")
    L.append("")
    return L


def _email_cliente(proj, orc, cat):
    ped = proj.pedido
    emp = cat["empresa"]
    com = cat["comercial"]
    rs = lambda x: f"R$ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return (f"Para: {ped.get('email_contato') or ''}\nAssunto: RE: {ped.get('referencia') or 'Cotação filtro senoidal'} – Proposta {proj_codigo(proj)}\n\n"
            f"Olá {(ped.get('contato') or '').split(' ')[0]},\n\n"
            f"Segue nossa proposta para {orc.quantidade} filtro(s) senoidal(is) {proj.topologia} {ped['corrente_a']:g} A / {ped['tensao_v']:g} V, "
            f"dimensionado(s) e simulado(s) para a aplicação informada ({ped.get('inversor')}, motor {ped.get('motor_cv') or ''} cv):\n\n"
            f"- Preço unitário: {rs(orc.preco_unit)} (impostos inclusos)\n- Total: {rs(orc.preco_total)}\n"
            f"- NCM: {com['ncm_sugerido']} | Frete: FOB Porto Alegre/RS | Prazo: {com['prazo_entrega']}\n"
            f"- Validade: {com['validade_dias']} dias | Pagamento: {com['pagamento']} | Garantia: {com['garantia']}\n\n"
            f"Atendimento técnico: Vpico garantido < {D.vpk_garantia(proj):.0f} V no pior caso (≤ {ped.get('vpk_max_v') or '-'} V), "
            f"dv/dt {max(p['dvdt_saida_v_us'] for p in proj.pontos):.1f} V/µs (≤ {ped.get('dvdt_max_v_us') or '-'} V/µs), "
            f"THD de tensão {max(p['thd_v_saida_pct'] for p in proj.pontos):.1f} %, isolação 1,1 kV, sistema de isolação classe H (180 °C – igual ou superior à classe solicitada).\n"
            f"Importante (requisito do fornecimento): o inversor deve operar com frequência de chaveamento FIXA de {proj.fs_hz / 1000:g} kHz, "
            f"com a redução automática por temperatura DESABILITADA (no ABB ACS580: 97.01 e 97.02 = {proj.fs_hz / 1000:g} kHz). Com frequência "
            "menor o filtro não atende a especificação. A parametrização é conferida no comissionamento.\n\n"
            "Anexos: proposta, folha de dados, memorial de cálculo e desenho dimensional.\n\n"
            f"Atenciosamente,\n{emp['responsavel']}\n{emp['nome']}\n{emp['email']} | {emp['telefone']}\n")


def resumo_texto(proj, arr, orc, similares, pasta):
    from . import checagem as _CK
    ped = proj.pedido
    b = proj.banco
    am = proj.amortecimento
    rs = lambda x: f"R$ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    from .versao import assinatura
    lin = [f"# {proj_codigo(proj)} – {ped['cliente']}", "", f"*{assinatura()}*", "",
           f"**Status:** {'✅ APROVADO' if proj.aprovado else '❌ REPROVADO'}  |  {ped['quantidade']} pç  |  fs fixa {proj.fs_hz / 1000:g} kHz", "",
           "## Solução", f"- L1 = **{proj.l1.l_uh:.0f} µH/fase** (uk {proj.l1.uk_pct:.1f} %), {proj.l1.i_nom_a:.0f} A, Isat ≥ {proj.l1.i_sat_a:.0f} A",
           f"- Capacitores: **{b.n_total} × {b.uf_unit:g} µF {b.v_unit:g} V** ({b.fabricante}) em **{b.ligacao}**, {b.n_por_ramo}/ramo → {b.c_y_uf:g} µF Y",
           f"- fr = **{proj.fr_hz:.0f} Hz**" + (f"; amortecimento {am.r_ramo_ohm:.3f} Ω / {am.p_nominal_w:g} W por ramo" if am else "; sem resistor de amortecimento"),
           f"- Caixa {arr.caixa_id}, perdas {arr.perda_total_w:.0f} W, {arr.n_ventiladores} ventiladores, massa ≈ {arr.massa_total_kg:.0f} kg", "",
           "## Verificações (check)", "", "| Verificação | Valor | Limite | Utilização | Check |", "|---|---|---|---|---|"] + [
               (lambda c, u: f"| {v.item.replace('|', '/')} | {v.valor} | {v.limite} | {'–' if u is None else f'{u:.0f} %'} | {_CK.texto(c)} |")(
                   *_CK.de_verificacao(v.ok, v.critico, v.valor, v.limite)) for v in proj.verificacoes] + ["",
               "Check: APROVADO (< 90 % do limite), ATENÇÃO (90–100 % ou aviso), REPROVADO (acima do limite obrigatório)."] + [
           ""] + texto_atp(getattr(proj, "dupla_checagem_atp", None)) + ["## Comercial", f"- Custo por filtro: {rs(orc.custo_unit_total)}  (material {rs(orc.custo_material)} + montagem {rs(orc.custo_montagem)})",
           f"- Preço unitário: **{rs(orc.preco_unit)}** | total {rs(orc.preco_total)} (impostos {orc.impostos_pct:g} %, margem {orc.margem_pct:g} %)", ""]
    if getattr(proj, "players", None):                       # v1.30.0 (REQ-SEN-024)
        try:
            from . import players as _PL
            lin += _PL.linhas_md(proj.players)
        except Exception:
            pass
    if proj.avisos:
        lin += ["## Avisos"] + [f"- {a}" for a in proj.avisos] + [""]
    if ped.get("lacunas"):
        lin += ["## Premissas (dados que faltaram no pedido)"] + [f"- {a}" for a in ped["lacunas"]] + [""]
    df_ = getattr(proj, "dados_faltantes", None)
    if df_ and df_["itens"]:
        lin += [f"## Dados a confirmar com o cliente ({df_['n_criticos']} críticos) – ver 02_Cliente/Email_Solicitacao_Dados_Tecnicos.txt"]
        for it in df_["itens"]:
            rep = [c["cenario"] for c in it.get("cenarios", []) if not c["aprovado"]]
            lin.append(f"- **{it['prioridade']}** {it['pergunta']}" + (f" – reprova com: {', '.join(rep)}" if rep else ""))
        lin.append("")
    if similares:
        lin += ["## Projetos anteriores semelhantes"] + [
            f"- {s.get('cliente')} – {s.get('corrente_a')} A {s.get('tensao_v') or ''} V {s.get('topologia') or ''} ({s.get('fonte')})" for s in similares] + [""]
    lin += ["## Pastas", "- 01_Engenharia: memorial de cálculo, planilha BOM/custos/preço, projeto.json",
            "- 02_Cliente: proposta, folha de dados, e-mail de resposta",
            "- 03_Fornecedores: ET + e-mail por fornecedor (indutor, capacitores, resistores, caixa, cabos/misc.)",
            "- 04_Montadora: RFQ de montagem, caderno de montagem, desenhos, e-mail",
            "- 05_Desenhos: PDF A3 (vistas, cortes, 3D, diagrama, cabos)"]
    return "\n".join(lin)
