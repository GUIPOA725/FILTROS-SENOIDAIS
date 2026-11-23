"""Assistente que RESPONDE e EXECUTA (REQ-IA-010, v1.26.0).

O operador escreve em português, como num chat:
   "faça um banco sintonizado com os dados da pasta G:\\...\\Cliente X e salve em G:\\...\\PROJETOS"
   "por que o painel ficou com 2200 mm?"
A IA (a mesma configurada na plataforma – Claude pela assinatura, API ou IA local) classifica o texto:
  • PERGUNTA  → responde usando a memória do projeto (fsen/memoria.py), as dicas das telas e o registro de uso da equipe;
  • COMANDO   → o agente lê a pasta, monta o pedido, roda o projeto inteiro pelo MESMO pipeline das telas e salva onde foi pedido.
Decisão que é do operador (pasta que falta, dado que o cliente não informou, tipo de filtro ambíguo) → o agente PERGUNTA e espera.
Autorização do engenheiro (22/11/2026): pedido de execução é para executar. Limites: o agente só roda o que a plataforma já faz –
não altera código, não apaga nada, não instala nada, não digita senhas; mudanças no programa são só com o engenheiro.
Tudo (pergunta, comando, resultado, erro) é registrado no Drive (memoria.registrar_uso).
"""
from __future__ import annotations

import json
import os
import re
import traceback

from . import memoria as ME

EXT_OK = (".pdf", ".docx", ".doc", ".xlsx", ".xls", ".xlsm", ".csv", ".txt", ".png", ".jpg", ".jpeg", ".eml", ".msg")
FILTROS = {"senoidal": "filtro senoidal (saída de inversor)", "dessintonizado": "banco de capacitores dessintonizado",
           "sintonizado": "filtro harmônico sintonizado"}

INSTR_CLASSIFICAR = """Você é o assistente da Plataforma FSEN (Electric Service). Leia a mensagem do operador e devolva SOMENTE um JSON, sem texto
em volta, com estas chaves:
{"intencao": "executar" ou "pergunta",
 "filtro": "senoidal" | "dessintonizado" | "sintonizado" | "",
 "pasta_entrada": "caminho completo da pasta com os dados do cliente, exatamente como escrito, ou vazio",
 "pasta_saida": "caminho completo onde salvar o resultado, ou vazio",
 "marca": "marca dos componentes pedida (ABB, Schneider, Siemens, WEG, Padrão Electric) ou vazio",
 "observacoes": "tudo o mais que o operador pediu sobre o projeto (potência, tensão, nº de estágios, ordens, cliente...), em texto",
 "continuar": true se o operador está respondendo sim/continuar/pode seguir a uma pergunta anterior, senão false}
"executar" = ele quer que a plataforma FAÇA um projeto (fazer, gerar, rodar, dimensionar, criar filtro/banco). Dúvida, explicação,
'como faço', 'por que deu' = "pergunta". "banco de capacitores"/"dessintonizado"/"anti-ressonante" = dessintonizado; "sintonizado",
"filtro de 5ª/7ª", "filtro harmônico passivo" = sintonizado; "senoidal", "sine wave", "saída de inversor", "dV/dt" = senoidal."""

INSTR_RESPONDER = """Você é o assistente da Plataforma FSEN da Electric Service (filtros senoidais, bancos dessintonizados e filtros sintonizados).
Quem pergunta é um colega que usa a plataforma mas não a desenvolveu. Responda em português, direto e prático (até ~12 linhas):
onde clicar, o que o valor significa, qual é a regra do engenheiro responsável (Guilherme) e por quê. Use a MEMÓRIA DO PROJETO
abaixo como verdade sobre as regras e decisões; se a resposta não estiver nela nem nas dicas, diga que não sabe e que a dúvida
ficou registrada para o engenheiro. Não invente campos, normas ou números. Se o colega pedir mudança no programa, explique que
só o engenheiro altera o código e que o pedido ficou registrado. Lembre que ele pode MANDAR FAZER: 'faça um <tipo de filtro> com
os dados da pasta <caminho> e salve em <caminho>'."""


# ----------------------------------------------------------------------------------------------------------------- IA (texto livre)
def ia_texto(prompt, provedor=None, timeout=240):
    """Resposta em texto pela IA configurada (Claude Code / API Anthropic / OpenAI-compatível local). Levanta exceção se não houver IA."""
    from .leitor_ia import config_ia, status_provedores, _claude_cli, carregar_chaves
    cfg = config_ia()
    provedor = provedor or cfg.get("provedor_padrao", "claude")
    if not status_provedores().get(provedor, {}).get("pronto"):
        raise RuntimeError("IA não configurada neste computador")
    pc = cfg["provedores"][provedor]
    if pc["tipo"] == "claude_code":
        import subprocess
        import tempfile
        r = subprocess.run([_claude_cli(), "-p", "--output-format", "json", "--model", pc["modelo"]], input=prompt, capture_output=True,
                           text=True, encoding="utf-8", timeout=timeout, cwd=tempfile.gettempdir(),
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        return str(json.loads(r.stdout).get("result", "")).strip()
    if pc["tipo"] == "anthropic":
        import anthropic
        carregar_chaves()
        cli = anthropic.Anthropic(api_key=os.environ.get(pc.get("env_chave") or "ANTHROPIC_API_KEY"))
        m = cli.messages.create(model=pc["modelo"], max_tokens=2000, messages=[{"role": "user", "content": prompt}])
        return "".join(getattr(b, "text", "") for b in m.content).strip()
    from openai import OpenAI
    env = pc.get("env_chave") or ""
    cli = OpenAI(base_url=pc["base_url"], api_key=os.environ.get(env, "") if env else "ollama")
    m = cli.chat.completions.create(model=pc["modelo"], temperature=0.1, messages=[{"role": "user", "content": prompt}])
    return m.choices[0].message.content.strip()


# ----------------------------------------------------------------------------------------------------------------- interpretar
RX_PASTA = re.compile(r"([A-Za-z]:\\[^\"'\n\r<>|*?]+?)(?=\s+(?:e\s+|para\s+|salv|grav|com\s+|usando|,|;)|[\"'\n\r]|\s*$)")


def _por_regras(texto):
    t = texto.lower()
    pastas = [p.strip().rstrip(".,; ") for p in RX_PASTA.findall(texto)]
    filtro = ("sintonizado" if re.search(r"\bsintonizad|filtro harm|5ª|7ª|quinta|sétima", t) and "dessint" not in t else
              "dessintonizado" if re.search(r"dessint|banco de cap|anti.?resson", t) else
              "senoidal" if re.search(r"senoidal|sine|inversor|dv/dt", t) else "")
    exe = bool(re.search(r"\b(fa[çc]a|fazer|gere|gerar|rode|rodar|dimension|crie|criar|execut|projete|monte)\b", t)) and (bool(pastas) or bool(filtro))
    marca = next((m for m in ("ABB", "Schneider", "Siemens", "WEG") if m.lower() in t), "")
    return dict(intencao="executar" if exe else "pergunta", filtro=filtro, pasta_entrada=pastas[0] if pastas else "",
                pasta_saida=pastas[1] if len(pastas) > 1 else "", marca=marca, observacoes=texto,
                continuar=bool(re.fullmatch(r"\s*(sim|s|ok|pode|continuar|continue|segue|pode seguir|pode continuar)[.! ]*", t)))


def interpretar(texto, provedor=None, pendente=None):
    """Mensagem do operador → dict(intencao, filtro, pasta_entrada, pasta_saida, marca, observacoes, continuar, _via)."""
    base = _por_regras(texto)
    try:
        ctx = f"\n\nCOMANDO PENDENTE (o operador pode estar completando/respondendo): {json.dumps(pendente, ensure_ascii=False)}" if pendente else ""
        r = ia_texto(f"{INSTR_CLASSIFICAR}{ctx}\n\nMENSAGEM DO OPERADOR:\n{texto}", provedor, timeout=120)
        m = re.search(r"\{.*\}", r, re.S)
        d = json.loads(m.group(0)) if m else {}
        out = {k: (d.get(k) if d.get(k) not in (None, "") else base.get(k)) for k in base}
        out["continuar"] = bool(d.get("continuar")) or base["continuar"]
        out["_via"] = "IA"
    except Exception as ex:
        out = dict(base, _via=f"regras (IA indisponível: {type(ex).__name__})")
    if pendente:                                                  # completa o comando anterior com o que veio agora
        for k in ("filtro", "pasta_entrada", "pasta_saida", "marca"):
            out[k] = out.get(k) or pendente.get(k) or ""
        if out.get("continuar") or any(out.get(k) != pendente.get(k) for k in ("filtro", "pasta_entrada", "pasta_saida", "marca")):
            out["intencao"] = "executar"
            out["observacoes"] = (str(pendente.get("observacoes") or "") + "\n" + str(texto)).strip()
    return out


# ----------------------------------------------------------------------------------------------------------------- responder
def responder(pergunta, tipo_tela="senoidal", contexto=None, provedor=None):
    from . import ajuda as AJ
    try:
        from . import biblioteca_componentes as BC
        bib = BC.resumo_txt()
    except Exception:
        bib = ""
    prompt = (f"{INSTR_RESPONDER}\n\n{ME.contexto_ia()}\n\n{bib}\n\n{AJ._base_conhecimento(tipo_tela)[:9000]}\n\n"
              f"CONTEXTO ATUAL DO USUÁRIO:\n{AJ._contexto_txt(contexto)[:4000]}\n\nPERGUNTA: {pergunta}")
    try:
        resp = ia_texto(prompt, provedor)
    except Exception as ex:
        resp = (f"(Assistente sem IA neste computador: {type(ex).__name__}: {str(ex)[:120]}.) Passe o mouse no **?** dos campos, veja o passo a "
            "passo no botão 🛟 Ajuda, ou mande executar: 'faça um <filtro> com os dados da pasta <caminho> e salve em <caminho>'.")
    ME.registrar_uso("pergunta", pergunta, resp)
    return resp


# ----------------------------------------------------------------------------------------------------------------- executar
def arquivos_da_pasta(pasta, max_arq=40, max_mb=30):
    out = []
    for d, dirs, fs in os.walk(pasta):
        if d[len(pasta):].count(os.sep) >= 2:
            dirs[:] = []
        dirs[:] = [x for x in dirs if not x.startswith((".", "~", "0")) and x.lower() not in ("saidas", "resultado", "resultados")]
        for f in sorted(fs):
            c = os.path.join(d, f)
            if f.lower().endswith(EXT_OK) and not f.startswith("~$"):
                try:
                    if os.path.getsize(c) <= max_mb * 1e6:
                        out.append(c)
                except OSError:
                    pass
    return out[:max_arq]


def _txt_solto(arqs):
    t = []
    for a in arqs:
        if a.lower().endswith((".txt", ".eml")):
            try:
                t.append(open(a, encoding="utf-8", errors="ignore").read()[:8000])
            except OSError:
                pass
    return "\n\n".join(t)


def _perguntas_iniciais(cmd, pasta_saida_padrao):
    q = []
    if not cmd.get("filtro"):
        q.append("Qual tipo de filtro: **senoidal**, **banco dessintonizado** ou **sintonizado**?")
    pe = cmd.get("pasta_entrada") or ""
    if not pe:
        q.append("Em qual **pasta** estão os dados do cliente (e-mail, medições, placa do trafo)? Escreva o caminho completo.")
    elif not os.path.isdir(pe):
        q.append(f"Não achei a pasta `{pe}` neste computador. Confira o caminho (copie da barra de endereço do Explorador de Arquivos).")
    if not (cmd.get("pasta_saida") or pasta_saida_padrao):
        q.append("Em qual pasta devo **salvar** o resultado?")
    return q


def executar(cmd, provedor=None, pasta_saida_padrao=None, log=print, confirmado=False, estado=None):
    """Roda o projeto pedido. Devolve dict(status='pergunta'|'ok'|'erro', mensagem, perguntas, pasta, estado).
    estado = dict guardado entre mensagens (pedido já lido), para não reler a pasta depois de uma pergunta."""
    estado = estado or {}
    perg = _perguntas_iniciais(cmd, pasta_saida_padrao)
    if perg:
        return dict(status="pergunta", perguntas=perg, mensagem="Preciso de uma definição sua antes de começar:", estado=estado)
    saida = cmd.get("pasta_saida") or pasta_saida_padrao
    filtro = cmd["filtro"]
    try:
        os.makedirs(saida, exist_ok=True)
        if estado.get("ped") is None or estado.get("chave") != (filtro, cmd["pasta_entrada"]):
            arqs = arquivos_da_pasta(cmd["pasta_entrada"])
            if not arqs:
                return dict(status="pergunta", estado=estado, mensagem="A pasta está vazia para mim:",
                            perguntas=[f"Não encontrei arquivos legíveis (pdf, docx, xlsx, csv, txt, imagens) em `{cmd['pasta_entrada']}`. "
                                       "Os dados estão em outra pasta?"])
            log(f"Lendo {len(arqs)} arquivo(s) de {cmd['pasta_entrada']}: " + ", ".join(os.path.basename(a) for a in arqs[:12])
                + ("…" if len(arqs) > 12 else ""))
            texto = (str(cmd.get("observacoes") or "") + "\n\n" + _txt_solto(arqs)).strip()
            if filtro == "senoidal":
                from .leitor_ia import ler_pedido
                ped = ler_pedido(texto, arqs, provedor=provedor)
                lac = [n for n, v in (("corrente do filtro", ped.corrente_a), ("tensão", ped.tensao_v), ("cliente", str(ped.cliente or "").strip())) if not v]
                bloqueia = bool(lac)                               # REQ-IA-004: sem valor padrão escondido
                avis = list(getattr(ped, "lacunas", None) or [])
                just = []
            else:
                from . import leitor_banco as LB
                from . import integracao as IN
                dados_ia = LB.ler(texto, arqs, provedor)
                dados, origem, _av = IN.mesclar(qee=None, protecao=None, ia=dados_ia)
                dados["evidencias"] = list(dados_ia.get("evidencias") or [])
                dados["_fonte"] = dados_ia.get("_fonte") or ""
                ped, just, lac = LB.decidir(dados, tipo_forcado=filtro)
                if cmd.get("marca"):
                    from . import fabricantes as FB
                    mk = next((m for m in FB.marcas() if m.lower().split()[0] == str(cmd["marca"]).lower().split()[0]), None)
                    if mk:
                        ped.marca = mk
                    else:
                        lac = list(lac) + [f"Marca '{cmd['marca']}' não está cadastrada na plataforma (há: {', '.join(FB.marcas())}) – "
                                           "vou usar o Padrão Electric, ou cadastre os componentes na Biblioteca de componentes."]
                IN.aplicar_rede(ped, dados)
                ped.origem_dados = {k: v for k, v in origem.items() if not k.startswith("_") and k not in ("evidencias", "lacunas")}
                ped.leitura = dict(fonte=str(dados.get("_fonte") or ""), justificativa=list(just), lacunas=list(lac),
                                   observacoes=str(dados.get("observacoes") or ""), evidencias=list(dados.get("evidencias") or []))
                bloqueia, avis = False, []
                if not str(getattr(ped, "cliente", "") or "").strip():
                    ped.cliente = os.path.basename(cmd["pasta_entrada"].rstrip("\\/")) or "Cliente"
            estado.update(ped=ped, chave=(filtro, cmd["pasta_entrada"]), lac=list(lac), just=list(just), avis=avis, bloqueia=bloqueia)
        ped, lac = estado["ped"], estado.get("lac") or []
        if estado.get("bloqueia"):
            return dict(status="pergunta", estado=dict(estado, ped=None), mensagem="Não encontrei dados obrigatórios no pedido – sem eles não dimensiono:",
                        perguntas=[f"Informe **{x}** (escreva aqui, ex.: 'corrente 120 A, tensão 440 V') ou coloque o documento na pasta." for x in lac])
        if lac and not confirmado:
            return dict(status="pergunta", estado=estado,
                        mensagem="Li a pasta. Antes de rodar, estes pontos ficaram em aberto (vou usar o padrão Electric se você mandar seguir):",
                        perguntas=[str(x) for x in lac[:12]] + ["Responda **continuar** para rodar assim, ou escreva o dado que faltou."],
                        resumo=_resumo_ped(ped, filtro, estado.get("just")))
        log(f"Rodando o projeto ({FILTROS[filtro]}) – pode levar de 5 a 20 minutos…")
        if filtro == "senoidal":
            from .pipeline import processar
            r = processar(ped, saida, log=log, leitura_fonte="Assistente IA (comando do operador)")
        else:
            from . import pipeline_banco as PB
            r = PB.processar_banco(ped, saida, log=log)
        msg = _resumo_resultado(r, filtro)
        ME.registrar_uso("execucao", json.dumps({k: cmd.get(k) for k in ("filtro", "pasta_entrada", "pasta_saida", "marca")}, ensure_ascii=False),
                         msg, extra=dict(pasta=r.get("pasta")))
        return dict(status="ok", mensagem=msg, pasta=r.get("pasta"), estado={})
    except Exception as ex:
        tb = traceback.format_exc()
        ME.registrar_uso("erro", json.dumps({k: cmd.get(k) for k in ("filtro", "pasta_entrada", "pasta_saida")}, ensure_ascii=False),
                         f"{type(ex).__name__}: {ex}", extra=dict(traceback=tb[-3000:]))
        try:
            from . import ajuda as AJ
            AJ.registrar_erro(ex, tela="Assistente IA")
        except Exception:
            pass
        return dict(status="erro", estado={}, mensagem=f"Não consegui concluir: **{type(ex).__name__}: {str(ex)[:300]}**. O erro ficou registrado "
                    "para o engenheiro (Drive › MEMORIA_IA › uso). Você pode tentar pela tela normal (menu Nova solicitação).")


def _resumo_ped(ped, filtro, just=None):
    try:
        if filtro == "senoidal":
            return f"Cliente {ped.cliente} · {ped.corrente_a:g} A · {ped.tensao_v:g} V"
        return (f"Cliente {ped.cliente} · {FILTROS[filtro]} · {sum(ped.estagios_kvar):g} kvar em {len(ped.estagios_kvar)} estágio(s) · "
                f"{ped.tensao_v:g} V · marca {getattr(ped, 'marca', '') or 'Padrão Electric'}" + (("\n" + " ".join(just[:3])) if just else ""))
    except Exception:
        return ""


def _resumo_resultado(r, filtro):
    pasta = r.get("pasta", "")
    lin = [f"✅ **Projeto concluído** ({FILTROS[filtro]}).", f"📂 Pasta: `{pasta}`"]
    try:
        cons = [f for f in os.listdir(pasta) if f.startswith("00_") and f.lower().endswith(".pdf")]
        if cons:
            lin.append(f"📄 Relatório consolidado: `{cons[0]}`")
        res = open(os.path.join(pasta, "RESUMO.md"), encoding="utf-8").read()
        nrep, nat = res.count("REPROVADO"), res.count("ATENÇÃO")
        lin.append(f"Verificações no RESUMO: **{nrep} reprovada(s)**, {nat} em atenção." + (" ⚠️ Veja o RESUMO.md antes de enviar a alguém." if nrep else ""))
    except OSError:
        pass
    return "\n\n".join(lin)


# ----------------------------------------------------------------------------------------------------------------- conversa
def conversar(texto, estado_conversa, provedor=None, pasta_saida_padrao=None, tipo_tela="senoidal", contexto=None, log=print):
    """Uma rodada do chat. estado_conversa: dict persistente (st.session_state). Devolve dict(resposta, executou, pasta)."""
    pend = estado_conversa.get("pendente")
    cmd = interpretar(texto, provedor, pend)
    if cmd["intencao"] != "executar" and not (pend and cmd.get("continuar")):
        return dict(resposta=responder(texto, tipo_tela, contexto, provedor), executou=False)
    ME.registrar_uso("comando", texto, json.dumps({k: cmd.get(k) for k in ("filtro", "pasta_entrada", "pasta_saida", "marca")}, ensure_ascii=False))
    r = executar(cmd, provedor, pasta_saida_padrao, log, confirmado=bool(pend and cmd.get("continuar")), estado=estado_conversa.get("exec"))
    if r["status"] == "pergunta":
        estado_conversa["pendente"], estado_conversa["exec"] = {k: v for k, v in cmd.items() if not k.startswith("_")}, r.get("estado")
        resp = r["mensagem"] + "\n\n" + "\n".join(f"- {q}" for q in r["perguntas"]) + (("\n\n" + r["resumo"]) if r.get("resumo") else "")
        ME.registrar_uso("pergunta_ao_operador", texto, resp)
        return dict(resposta=resp, executou=False)
    estado_conversa.pop("pendente", None)
    estado_conversa.pop("exec", None)
    return dict(resposta=r["mensagem"], executou=r["status"] == "ok", pasta=r.get("pasta"))
