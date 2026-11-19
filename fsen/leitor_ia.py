"""Leitura automática das solicitações (e-mail + anexos PDF/imagem/DOCX) com Claude (API Anthropic).

Uso: defina a variável de ambiente ANTHROPIC_API_KEY. Sem chave, usa o extrator por regras (regex),
que cobre o formato típico das solicitações recebidas.
"""
from __future__ import annotations
import os
import re
import json
import base64
from typing import List, Optional

from .modelos import Pedido

MODELO = os.environ.get("FSEN_MODELO_IA", "claude-sonnet-5-5")

CAMPOS = {
    "cliente": "string", "cnpj": "string", "cidade_uf": "string", "contato": "string", "email_contato": "string",
    "revenda": "boolean", "referencia": "string", "quantidade": "integer", "topologia": "string",
    "tensao_v": "number", "freq_rede_hz": "number", "corrente_a": "number", "f_saida_min_hz": "number",
    "f_saida_max_hz": "number", "inversor": "string", "inversor_corrente_a": "number", "fs_khz": "number",
    "motor_cv": "number", "motor_kw": "number", "motor_corrente_a": "number", "motor_fp": "number", "motor_rpm": "number",
    "motor_polos": "integer", "fator_servico": "number", "aplicacao": "string", "cabo_m": "number", "vpk_max_v": "number",
    "dvdt_max_v_us": "number", "rise_time_min_us": "number", "classe_isolamento_kv": "number", "classe_temp": "string",
    "elevacao_temp": "string", "ip": "string", "observacoes": "string",
    "cabo_secao_mm2": "number", "cabo_paralelos": "integer", "cabo_blindado": "boolean", "cabo_tipo": "string",
    "amb_max_c": "number", "altitude_m": "number", "inversor_controle": "string", "inversor_filtro_emc": "string",
    "aterramento": "string", "motor_para_inversor": "string", "mancal_isolado": "string", "alim_aux_v": "string",
    "dim_max_mm": "string", "entrada_cabos": "string", "carga_tipo": "string", "instalacao": "string",
}

INSTRUCAO = """Você é engenheiro de aplicação de filtros senoidais (LC/LCL) para saída de inversores de frequência.
Extraia da solicitação de cotação (e-mail e anexos) os dados técnicos e comerciais e chame a ferramenta `registrar_pedido`.
Regras:
- Use somente o que está escrito; não invente. Campos ausentes: omita e liste-os em `lacunas` com a premissa sugerida.
- topologia: "LC" salvo se pedirem LCL explicitamente.
- corrente_a = corrente nominal do filtro solicitada; se só houver motor, use corrente do motor × fator de serviço.
- inversor_corrente_a: extraia do modelo quando evidente (ex.: ACS580-01-293A-4 → 293).
- 'ITEM PARA REVENDA' ou razão social com 'REVENDA' → revenda = true.
- Potência em CV vai em motor_cv; kW em motor_kw.
"""


def _ferramenta():
    props = {k: {"type": v} for k, v in CAMPOS.items()}
    props["lacunas"] = {"type": "array", "items": {"type": "string"},
                        "description": "Dados que faltaram e a premissa adotada, ex.: 'freq. de chaveamento não informada – adotar 4 kHz'"}
    return {"name": "registrar_pedido", "description": "Registra os dados extraídos da solicitação de filtro senoidal.",
            "input_schema": {"type": "object", "properties": props, "required": ["corrente_a", "tensao_v"]}}


def _blocos_anexos(anexos: List[str]):
    blocos = []
    for cam in anexos or []:
        ext = os.path.splitext(cam)[1].lower()
        with open(cam, "rb") as f:
            dados = f.read()
        if ext == ".pdf":
            blocos.append({"type": "document", "source": {"type": "base64", "media_type": "application/pdf",
                                                          "data": base64.b64encode(dados).decode()}})
        elif ext in (".png", ".jpg", ".jpeg", ".webp", ".gif"):
            mt = "image/jpeg" if ext in (".jpg", ".jpeg") else f"image/{ext[1:]}"
            blocos.append({"type": "image", "source": {"type": "base64", "media_type": mt, "data": base64.b64encode(dados).decode()}})
        elif ext == ".docx":
            from docx import Document
            txt = "\n".join(p.text for p in Document(cam).paragraphs)
            for t in Document(cam).tables:
                for r in t.rows:
                    txt += "\n" + " | ".join(c.text for c in r.cells)
            blocos.append({"type": "text", "text": f"[Anexo {os.path.basename(cam)}]\n{txt}"})
        else:
            blocos.append({"type": "text", "text": f"[Anexo {os.path.basename(cam)}]\n{dados.decode('utf-8', 'ignore')}"})
    return blocos


RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CFG_IA = os.path.join(RAIZ, "dados", "ia.yaml")


def config_ia():
    import yaml
    with open(CFG_IA, encoding="utf-8") as f:
        return yaml.safe_load(f)


def salvar_config_ia(cfg):
    import yaml
    with open(CFG_IA, "w", encoding="utf-8") as f:
        yaml.safe_dump(cfg, f, allow_unicode=True, sort_keys=False)


def status_provedores():
    cfg = config_ia()
    out = {}
    for k, p in cfg["provedores"].items():
        env = p.get("env_chave") or ""
        out[k] = dict(nome=p["nome"], modelo=p["modelo"], pronto=(not env) or bool(os.environ.get(env)), env=env)
    return out


def _texto_anexos(anexos):
    txt = ""
    for a in anexos or []:
        if a.lower().endswith(".pdf"):
            try:
                import pypdf
                txt += f"\n[Anexo {os.path.basename(a)}]\n" + "\n".join(pg.extract_text() or "" for pg in pypdf.PdfReader(a).pages)
            except Exception:
                pass
        elif a.lower().endswith(".docx"):
            from docx import Document
            d = Document(a)
            txt += f"\n[Anexo {os.path.basename(a)}]\n" + "\n".join(p.text for p in d.paragraphs)
            for t in d.tables:
                for r in t.rows:
                    txt += "\n" + " | ".join(c.text for c in r.cells)
        elif a.lower().endswith((".txt", ".eml", ".csv")):
            txt += f"\n[Anexo {os.path.basename(a)}]\n" + open(a, encoding="utf-8", errors="ignore").read()
    return txt


def ler_com_ia(texto_email: str, anexos: Optional[List[str]] = None, historico_txt: str = "", provedor: str = None) -> Pedido:
    cfg = config_ia()
    provedor = provedor or cfg.get("provedor_padrao", "claude")
    pc = cfg["provedores"][provedor]
    if pc["tipo"] == "anthropic":
        import anthropic
        cli = anthropic.Anthropic(api_key=os.environ.get(pc.get("env_chave") or "ANTHROPIC_API_KEY"))
        conteudo = _blocos_anexos(anexos) + [{"type": "text", "text": f"E-MAIL:\n{texto_email}\n\n{historico_txt}"}]
        resp = cli.messages.create(model=pc["modelo"], max_tokens=2000, system=INSTRUCAO, tools=[_ferramenta()],
                                   tool_choice={"type": "tool", "name": "registrar_pedido"},
                                   messages=[{"role": "user", "content": conteudo}])
        dados = next(b.input for b in resp.content if b.type == "tool_use")
    else:
        # API compatível com OpenAI: ChatGPT, DeepSeek, Gemini, Mistral, Grok, OpenRouter, Ollama local
        from openai import OpenAI
        env = pc.get("env_chave") or ""
        cli = OpenAI(base_url=pc["base_url"], api_key=os.environ.get(env, "") if env else "ollama")
        esquema = json.dumps(_ferramenta()["input_schema"]["properties"], ensure_ascii=False)
        msg = (f"{INSTRUCAO}\nResponda SOMENTE com um objeto JSON com estes campos (omita os desconhecidos):\n{esquema}\n\n"
               f"E-MAIL:\n{texto_email}\n{_texto_anexos(anexos)}\n{historico_txt}")
        resp = cli.chat.completions.create(model=pc["modelo"], temperature=0,
                                           response_format={"type": "json_object"},
                                           messages=[{"role": "user", "content": msg}])
        conteudo = resp.choices[0].message.content
        conteudo = conteudo[conteudo.find("{"): conteudo.rfind("}") + 1]
        dados = json.loads(conteudo)
    ped = _completar(Pedido.from_dict(dados))
    ped.observacoes = (ped.observacoes + f" [lido por IA: {pc['nome']} / {pc['modelo']}]").strip()
    return ped


# ---------------------------------------------------------------- extrator por regras (sem IA)
def _num(rx, txt, grupo=1, conv=float):
    m = re.search(rx, txt, re.I | re.S)
    if not m:
        return None
    try:
        return conv(m.group(grupo).replace(".", "").replace(",", ".") if conv is float and "," in m.group(grupo) else m.group(grupo))
    except Exception:
        return None


def ler_por_regras(texto: str) -> Pedido:
    t = " ".join(texto.split())
    p = Pedido()
    p.quantidade = int(_num(r"\b0?\d{1,2}\s*\|\s*(\d{1,4})\s*\|\s*Filtro", t, conv=int)
                       or _num(r"(\d+)\s*(?:p[eç]ças|pç|und|unid)\b", t, conv=int)
                       or _num(r"Quantidade\D{0,20}(\d+)", t, conv=int) or 1)
    p.tensao_v = _num(r"(\d{3})\s*V(?![a-z/])", t) or 440.0
    p.freq_rede_hz = _num(r"(50|60)\s*Hz", t) or 60.0
    p.corrente_a = _num(r"(\d{1,4}(?:[.,]\d+)?)\s*A\s+\d{3}\s*V", t) or _num(r"senoidal[^.]{0,60}?(\d{1,4})\s*A\b", t) or 0.0
    p.topologia = "LCL" if re.search(r"\bLCL\b", t) else "LC"
    p.vpk_max_v = _num(r"tens[aã]o de pico\D{0,10}(\d{3,4})\s*V", t)
    p.rise_time_min_us = _num(r"rise time\D{0,10}(\d+(?:[.,]\d+)?)", t)
    p.dvdt_max_v_us = _num(r"dv/dt\D{0,10}(\d{2,5})", t)
    p.classe_isolamento_kv = _num(r"isolamento\D{0,5}(\d+(?:[.,]\d+)?)\s*kV", t) or 1.1
    m = re.search(r"inversor\s+([A-Z]{2,5}[\w\-]+)", t)
    if m:
        p.inversor = ("ABB " + m.group(1)) if m.group(1).upper().startswith("ACS") else m.group(1)
        ci = re.search(r"-(\d{2,4})A-", m.group(1))
        if ci:
            p.inversor_corrente_a = float(ci.group(1))
    p.motor_cv = _num(r"(\d{1,4})\s*CV", t) or 0.0
    p.motor_rpm = _num(r"(\d{3,4})\s*rpm", t) or 0.0
    p.motor_polos = int(_num(r"(\d)\s*polos", t, conv=int) or 4)
    p.motor_fp = _num(r"fator de pot[eê]ncia\D{0,5}(\d[.,]\d+)", t) or 0.85
    p.fator_servico = _num(r"fator de servi[cç]o\D{0,5}(\d[.,]\d+)", t) or 1.0
    p.motor_corrente_a = _num(r"corrente nominal motor\D{0,5}(\d{1,4}(?:[.,]\d+)?)", t) or 0.0
    p.cabo_m = _num(r"dist[aâ]ncia cabo\D{0,5}(\d{1,4})\s*m", t) or _num(r"cabo\D{0,10}(\d{1,4})\s*m\b", t) or 0.0
    fx = re.search(r"faixa de opera[cç][aã]o\D{0,5}(\d{1,3})\s*[-–a]\s*(\d{1,3})\s*Hz", t, re.I)
    if fx:
        p.f_saida_min_hz, p.f_saida_max_hz = float(fx.group(1)), float(fx.group(2))
    else:
        p.f_saida_max_hz = p.freq_rede_hz
    m = re.search(r"Raz[aã]o Social\s*[:|]?\s*(.+?)(?:\s+CNPJ|\n|$)", texto, re.I)
    if m:
        p.cliente = m.group(1).strip(" |")
    m = re.search(r"CNPJ\s*[:|]?\s*([\d./-]{14,20})", t)
    if m:
        p.cnpj = m.group(1)
    m = re.search(r"Munic[ií]pio de Faturamento\s*[:|]?\s*([\w\sÀ-ú]+/[A-Z]{2})", t)
    if m:
        p.cidade_uf = m.group(1).strip()
    p.revenda = bool(re.search(r"revenda", t, re.I))
    m = re.search(r"^De:\s*'?\"?([^'\"<\n]+?)'?\"?\s*(?:via|<|$)", texto, re.I | re.M)
    if m:
        p.contato = m.group(1).replace("-", " ").strip()
    m = re.search(r"[\w.+-]+@[\w-]+\.[\w.]+", texto)
    if m:
        p.email_contato = m.group(0)
    m = re.search(r"^Assunto:\s*(.+)$", texto, re.I | re.M)
    if m:
        p.referencia = m.group(1).strip()
    m = re.search(r"aplica[cç][aã]o\s*:?\s*(.+?)(?:,\s*pot[eê]ncia|$)", t, re.I)
    if m:
        p.aplicacao = m.group(1).strip()[:160]
    return _completar(p)


def _completar(p: Pedido) -> Pedido:
    if not p.informados:      # registra o que veio de fato ANTES de preencher premissas
        padrao = Pedido()
        p.informados = [k for k in Pedido.__dataclass_fields__ if k not in ("lacunas", "informados")
                        and getattr(p, k) not in (None, "", 0, []) and getattr(p, k) != getattr(padrao, k)]
    lac = list(p.lacunas or [])
    if not p.fs_khz:
        lac.append("Frequência de chaveamento não informada – adotado o padrão do inversor (catálogo) com fs FIXA.")
    if not p.corrente_a and p.motor_corrente_a:
        p.corrente_a = round(p.motor_corrente_a * max(p.fator_servico, 1.0), 1)
        lac.append("Corrente do filtro não informada – adotado corrente do motor × fator de serviço.")
    if not p.inversor_corrente_a:
        p.inversor_corrente_a = p.corrente_a
    if not p.motor_corrente_a:
        lac.append("Corrente do motor não informada – simulação com a corrente nominal do filtro.")
    if not p.f_saida_min_hz:
        p.f_saida_min_hz = round(0.5 * (p.f_saida_max_hz or p.freq_rede_hz), 1)
        lac.append(f"Faixa de operação não informada – verificado {p.f_saida_min_hz:g}–{p.f_saida_max_hz or p.freq_rede_hz:g} Hz.")
    if not p.cabo_m:
        lac.append("Comprimento de cabo não informado – considerado ≤ 100 m.")
    p.lacunas = list(dict.fromkeys(lac))
    return p


def ler_pedido(texto: str, anexos: Optional[List[str]] = None, usar_ia: Optional[bool] = None, provedor: str = None) -> Pedido:
    """Lê a solicitação com o provedor de IA escolhido (padrão do dados/ia.yaml); se indisponível, usa regras."""
    st = status_provedores()
    provedor = provedor or config_ia().get("provedor_padrao", "claude")
    if usar_ia is None:
        usar_ia = st.get(provedor, {}).get("pronto", False)
    if usar_ia:
        try:
            return ler_com_ia(texto, anexos, provedor=provedor)
        except Exception as e:  # sem rede/chave: segue por regras
            print(f"[leitor_ia] IA {provedor} indisponível ({e}); usando regras.")
    # v1.8.3: sem IA, lê também .docx (parágrafos + TABELAS – a solicitação da A&W vem numa tabela)
    return ler_por_regras((texto or "") + "\n" + _texto_anexos(anexos))
