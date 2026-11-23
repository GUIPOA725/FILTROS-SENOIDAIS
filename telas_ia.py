"""Telas do Assistente IA (perguntar ou mandar fazer) e da Biblioteca de componentes compartilhada – v1.26.0."""
import os

import streamlit as st

from fsen import agente as AG
from fsen import biblioteca_componentes as BC
from fsen import memoria as ME

EXEMPLOS = ["faça um banco sintonizado com os dados da pasta G:\\...\\Cliente X\\dados e salve em G:\\...\\PROJETOS",
            "faça o filtro senoidal da pasta C:\\Users\\...\\Downloads\\pedido_motor, componentes Schneider",
            "por que o painel ficou com 2200 mm de altura?", "quantos capacitores por estágio a plataforma usa e por quê?"]


def tela_assistente(tipo_filtro, pasta_saida, provedor=None, contexto=None):
    st.title("🤖 Assistente IA – pergunte ou mande fazer")
    st.caption("Escreva como num chat. **Pergunta** → ele responde com o histórico e as regras do projeto. **Pedido de execução** → ele lê a "
               "pasta, roda o projeto inteiro e salva onde você mandar; se faltar uma decisão sua, ele pergunta. Tudo fica registrado no "
               "Drive (MEMORIA_IA) para a equipe e para o engenheiro responsável.")
    with st.expander("Exemplos do que escrever"):
        for e in EXEMPLOS:
            st.markdown(f"- `{e}`")
        st.markdown(f"Se você não disser onde salvar, uso a pasta de saída da barra lateral: `{pasta_saida}`.")
    hist = st.session_state.setdefault("ag_hist", [])
    est = st.session_state.setdefault("ag_estado", {})
    for quem, txt in hist:
        st.chat_message("user" if quem == "voce" else "assistant").markdown(txt)
    if est.get("pendente"):
        st.info("⏳ Há um pedido aguardando sua resposta (acima). Responda, ou escreva **cancelar** para desistir dele.")
    msg = st.chat_input("Pergunte ou mande fazer… (ex.: faça um banco dessintonizado com os dados da pasta … e salve em …)")
    if not msg:
        return
    hist.append(("voce", msg))
    st.chat_message("user").markdown(msg)
    if msg.strip().lower() in ("cancelar", "cancela", "desistir"):
        est.clear()
        resp = "Pedido cancelado. Nada foi rodado."
        ME.registrar_uso("comando", msg, resp)
    else:
        caixa = st.chat_message("assistant")
        linha = caixa.empty()
        registro = []

        def _log(m):
            registro.append(str(m))
            linha.code("\n".join(registro[-12:]))
        with st.spinner("Trabalhando… (um projeto completo leva de 5 a 20 minutos – não feche a janela)"):
            r = AG.conversar(msg, est, provedor=provedor, pasta_saida_padrao=pasta_saida, tipo_tela=tipo_filtro, contexto=contexto, log=_log)
        resp = r["resposta"]
        linha.empty()
    hist.append(("ia", resp))
    st.rerun()


def tela_biblioteca():
    st.title("📚 Biblioteca de componentes da equipe (Drive)")
    st.caption("Um único lugar para os componentes que a equipe cadastrar. **Pesquise antes de criar.** Componente novo entra como "
               "**A CONFERIR** e só vale para todos depois da aprovação do engenheiro responsável.")
    q = st.text_input("Pesquisar componente, projeto ou painel", key="bc_q", placeholder="ex.: siemens contator 3RT · sintonizado 30 kvar · capacitor 525",
                      help="Procura no catálogo da plataforma, na biblioteca do Drive, nas pastas de PROJETOS e nos painéis aprovados. "
                           "Todas as palavras têm que aparecer.")
    if q:
        ach = BC.pesquisar(q, incluir_projetos=True)
        if not ach:
            st.warning("Nada encontrado. Se o componente não existe mesmo, cadastre abaixo (com a fonte do catálogo do fabricante).")
        else:
            st.dataframe([{"Status": d.get("status"), "Grupo": d.get("grupo"), "Fabricante/Cliente": d.get("fabricante"), "Código / nome": d.get("codigo") or d.get("nome"),
                           "Medidas (mm)": " × ".join(f"{k}{v:g}" for k, v in (d.get("medidas_mm") or {}).items()), "Fonte / pasta": d.get("fonte")}
                          for d in ach], use_container_width=True, hide_index=True)
    st.subheader("Cadastrar componente novo (entra como A CONFERIR)")
    c1, c2, c3 = st.columns(3)
    grupo = c1.selectbox("Grupo do componente", BC.GRUPOS, key="bc_grupo", help="Tipo do componente. Define onde ele pode ser usado no painel 3D/2D e na lista.")
    fab = c2.text_input("Fabricante", key="bc_fab", help="Marca do componente (Siemens, WEG, ABB, Schneider, Epcos/TDK…).")
    cod = c3.text_input("Código de catálogo", key="bc_cod", help="Código de compra exato do fabricante (o que vai na cotação). A plataforma não aceita dois componentes com o mesmo código.")
    nome = st.text_input("Descrição do componente", key="bc_nome", help="Descrição curta: tipo, corrente/potência, tensão. Ex.: Contatora 3RT2046 95 A AC-3, bobina 220 V.")
    fonte = st.text_input("Fonte dos dados (catálogo / página do fabricante)", key="bc_fonte",
                          help="OBRIGATÓRIO: de onde saíram o código e as medidas (link da página do produto ou nome/edição do catálogo). Sem fonte não entra.")
    m1, m2, m3, m4 = st.columns(4)
    L = m1.number_input("Largura (mm)", 0.0, 3000.0, 0.0, key="bc_L", help="Largura do componente pelo desenho dimensional do catálogo. Para capacitor cilíndrico deixe 0 e use o diâmetro.")
    A = m2.number_input("Altura (mm)", 0.0, 3000.0, 0.0, key="bc_A", help="Altura do componente (para capacitor cilíndrico: altura da lata sem o borne).")
    P = m3.number_input("Profundidade (mm)", 0.0, 3000.0, 0.0, key="bc_P", help="Profundidade a partir da placa de montagem.")
    D = m4.number_input("Diâmetro (mm) – só cilíndrico", 0.0, 1000.0, 0.0, key="bc_D", help="Diâmetro da lata do capacitor cilíndrico. Deixe 0 para componentes em caixa.")
    obs = st.text_input("Observação para o engenheiro", key="bc_obs", help="Opcional: em que projeto vai usar, distância mínima de montagem, torque, seção máxima do borne.")
    if st.button("Enviar para a biblioteca (A CONFERIR)", key="bc_enviar", help="Grava a ficha no Drive. Ela já pode ser usada, mas sai marcada 'a conferir' até o engenheiro aprovar."):
        try:
            med = dict(D=D, A=A) if D else dict(L=L, A=A, P=P)
            arq = BC.propor(grupo, nome, fab, cod, fonte, med, observacao=obs)
            st.success(f"Ficha gravada: {os.path.basename(arq)} – aguardando a aprovação do engenheiro.")
        except Exception as ex:
            st.error(str(ex))
    pend = BC.listar("A_CONFERIR")
    st.subheader(f"Aguardando aprovação ({len(pend)})")
    pode = BC.pode_aprovar()
    if not pode:
        st.caption("Só o engenheiro responsável aprova. Você pode usar o componente, mas o projeto sai com ele marcado 'a conferir'.")
    for i, d in enumerate(pend):
        with st.expander(f"{d.get('fabricante')} {d.get('codigo')} – {d.get('nome')} (por {d.get('proposto_por')}, {d.get('proposto_em')})"):
            st.write({k: d.get(k) for k in ("grupo", "medidas_mm", "fonte", "observacao")})
            if pode:
                a1, a2 = st.columns(2)
                if a1.button("✅ Aprovar para todos", key=f"bc_ap_{i}", help="Confirma que código, medidas e fonte conferem com o catálogo. Passa a valer para toda a equipe."):
                    BC.aprovar(d["_arquivo"])
                    st.rerun()
                mot = a2.text_input("Motivo da recusa", key=f"bc_mot_{i}", help="Explique o que está errado (código, medida, fonte) para quem cadastrou corrigir.")
                if a2.button("❌ Recusar", key=f"bc_rc_{i}", help="Tira a ficha da fila e guarda em 'recusados' com o motivo.") and mot:
                    BC.recusar(d["_arquivo"], mot)
                    st.rerun()
    apr = BC.listar("APROVADO")
    with st.expander(f"Aprovados ({len(apr)})"):
        st.dataframe([{"Grupo": d.get("grupo"), "Fabricante": d.get("fabricante"), "Código": d.get("codigo"), "Descrição": d.get("nome"),
                       "Aprovado por": d.get("aprovado_por"), "Em": d.get("aprovado_em")} for d in apr], use_container_width=True, hide_index=True)
