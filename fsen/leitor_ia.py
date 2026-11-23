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
        elif ext in (".xlsx", ".xlsm", ".xls", ".csv", ".txt") and ext != ".txt" or _parece_medicao(cam):
            blocos.append({"type": "text", "text": f"[Anexo {os.path.basename(cam)}]\n{texto_planilha(cam)}"})
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
# Preferências e chaves do USUÁRIO ficam fora do Drive e fora da cópia do programa (que é reescrita a cada abertura):
# %USERPROFILE%\.fsen\ia_usuario.yaml (modelo, esforço, provedor) e %USERPROFILE%\.fsen\chaves.json (chaves de API)
PASTA_USUARIO = os.path.join(os.path.expanduser("~"), ".fsen")
CFG_USUARIO = os.path.join(PASTA_USUARIO, "ia_usuario.yaml")
CHAVES_USUARIO = os.path.join(PASTA_USUARIO, "chaves.json")

MODELOS_CLAUDE = {
    "claude-opus-5-5": "Claude Opus 5.5 (mais capaz)",
    "claude-sonnet-5-5": "Claude Sonnet 5.5 (rápido e barato)",
    "claude-haiku-5-5": "Claude Haiku 5.5 (mais rápido)",
    "claude-fable-5-2": "Claude Fable 5.2 (topo)",
}
ESFORCOS = {"low": "baixo", "medium": "médio", "high": "alto", "xhigh": "muito alto", "max": "máximo"}


def carregar_chaves():
    """Carrega as chaves salvas pelo usuário (se a variável de ambiente não estiver definida)."""
    try:
        for k, v in json.load(open(CHAVES_USUARIO, encoding="utf-8")).items():
            if v and not os.environ.get(k):
                os.environ[k] = v
    except Exception:
        pass


def salvar_chave(env, valor):
    os.makedirs(PASTA_USUARIO, exist_ok=True)
    try:
        d = json.load(open(CHAVES_USUARIO, encoding="utf-8"))
    except Exception:
        d = {}
    d[env] = valor.strip()
    json.dump(d, open(CHAVES_USUARIO, "w", encoding="utf-8"))
    os.environ[env] = valor.strip()


def config_ia():
    import yaml
    with open(CFG_IA, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    try:
        u = yaml.safe_load(open(CFG_USUARIO, encoding="utf-8")) or {}
        cfg["provedor_padrao"] = u.get("provedor_padrao", cfg.get("provedor_padrao"))
        for k, pv in (u.get("provedores") or {}).items():
            if k in cfg["provedores"]:
                cfg["provedores"][k].update({kk: vv for kk, vv in pv.items() if kk in ("modelo", "esforco")})
    except Exception:
        pass
    return cfg


def salvar_config_ia(cfg):
    """Grava só as preferências do usuário (provedor, modelo, esforço) na pasta do usuário."""
    import yaml
    os.makedirs(PASTA_USUARIO, exist_ok=True)
    u = {"provedor_padrao": cfg.get("provedor_padrao"),
         "provedores": {k: {kk: v[kk] for kk in ("modelo", "esforco") if kk in v} for k, v in cfg["provedores"].items()}}
    with open(CFG_USUARIO, "w", encoding="utf-8") as f:
        yaml.safe_dump(u, f, allow_unicode=True, sort_keys=False)


def status_provedores():
    carregar_chaves()
    cfg = config_ia()
    out = {}
    for k, p in cfg["provedores"].items():
        env = p.get("env_chave") or ""
        pronto = bool(_claude_cli()) if p.get("tipo") == "claude_code" else ((not env) or bool(os.environ.get(env)))
        out[k] = dict(nome=p["nome"], modelo=p["modelo"], pronto=pronto, env=env, tipo=p.get("tipo"))
    return out


def testar_ia(provedor=None):
    """Chamada mínima para confirmar chave/modelo. Retorna (ok, mensagem)."""
    try:
        p = ler_com_ia("Filtro senoidal 10 A 380 V, 1 peça, cliente TESTE.", [], provedor=provedor)
        return True, f"OK – leu {p.corrente_a:g} A / {p.tensao_v:g} V ({p.observacoes})"
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"


def _parece_medicao(cam):
    return os.path.splitext(cam)[1].lower() in (".xlsx", ".xlsm", ".xls", ".csv")


def texto_planilha(cam, max_linhas=60, max_cols=70):
    """v1.14.0: planilhas e exportações de medição (Dranview, Fluke, PQ Analyzer, CSV) em texto para a IA.
    Tabelas curtas vão inteiras; séries longas (medição no tempo) viram ESTATÍSTICAS por coluna (média, P95, máximo) –
    é o que o dimensionamento usa (harmônicas P95/máximo, DHT, kW, kvar, FP)."""
    import numpy as np
    out = []
    try:
        import pandas as pd
        if cam.lower().endswith(".csv"):
            folhas = {"csv": pd.read_csv(cam, sep=None, engine="python", header=None, nrows=200000, encoding_errors="ignore")}
        else:
            folhas = pd.read_excel(cam, sheet_name=None, header=None, nrows=200000)
    except Exception as e:
        return f"(planilha não lida: {type(e).__name__}: {e})"
    for nome, df in list(folhas.items())[:12]:
        df = df.dropna(how="all").dropna(axis=1, how="all")
        if df.empty:
            continue
        df = df.iloc[:, :max_cols]
        out.append(f"--- aba '{nome}' ({df.shape[0]} linhas × {df.shape[1]} colunas)")
        if df.shape[0] <= max_linhas:
            for _, r in df.iterrows():
                out.append(" | ".join("" if (isinstance(v, float) and np.isnan(v)) else str(v)[:30] for v in r.values))
            continue
        # série longa: cabeçalho (primeiras linhas não numéricas) + estatística por coluna
        hdr_rows = []
        for i in range(min(8, df.shape[0])):
            r = df.iloc[i]
            if pd.to_numeric(r, errors="coerce").notna().mean() < 0.5:
                hdr_rows.append(i)
        cab = [" / ".join(str(df.iloc[i, j]) for i in hdr_rows if str(df.iloc[i, j]) != "nan")[:60] or f"col{j}" for j in range(df.shape[1])]
        num = df.drop(index=df.index[hdr_rows]).apply(pd.to_numeric, errors="coerce")
        out.append("coluna | n | média | P95 | máximo | mínimo")
        for j, c in enumerate(num.columns):
            v = num[c].dropna().values
            if len(v) < 3:
                continue
            out.append(f"{cab[j]} | {len(v)} | {np.mean(v):.4g} | {np.percentile(v, 95):.4g} | {np.max(v):.4g} | {np.min(v):.4g}")
    return "\n".join(out)[:60000]


def _texto_anexos(anexos):
    txt = ""
    for a in anexos or []:
        if _parece_medicao(a):
            txt += f"\n[Anexo {os.path.basename(a)}]\n" + texto_planilha(a)
        elif a.lower().endswith(".pdf"):
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


def _claude_cli():
    import shutil
    c = shutil.which("claude") or shutil.which("claude.cmd")
    if not c and os.name == "nt":
        for cand in (os.path.join(os.environ.get("APPDATA", ""), "npm", "claude.cmd"),
                     os.path.join(os.path.expanduser("~"), ".local", "bin", "claude.exe")):
            if os.path.exists(cand):
                return cand
    return c


def _figuras_pdf(anexos, max_fig=30, min_kb=25):
    """v1.23.4: extrai as figuras (gráficos de espectro, tendências) dos PDFs anexados para a IA LER os valores –
    relatórios de QEE costumam trazer as harmônicas só em gráfico. Devolve [(caminho_png, legenda)]."""
    import tempfile
    out = []
    try:
        import pypdf
    except Exception:
        return out
    dst = os.path.join(tempfile.gettempdir(), "fsen_figuras_pdf")
    os.makedirs(dst, exist_ok=True)
    for a in anexos or []:
        if not a.lower().endswith(".pdf"):
            continue
        try:
            r = pypdf.PdfReader(a)
        except Exception:
            continue
        base = os.path.splitext(os.path.basename(a))[0][:40]
        for ip, pg in enumerate(r.pages, 1):
            try:
                imgs = list(pg.images)
            except Exception:
                continue
            for k, im in enumerate(imgs):
                if len(im.data) < min_kb * 1024:
                    continue
                ext = os.path.splitext(im.name)[1] or ".png"
                cam = os.path.join(dst, f"{base}_p{ip:02d}_{k}{ext}")
                try:
                    with open(cam, "wb") as fh:
                        fh.write(im.data)
                    txt = (pg.extract_text() or "").strip().replace("\n", " ")
                    out.append((cam, f"{os.path.basename(a)} – página {ip} ({txt[:120]})"))
                except Exception:
                    pass
                if len(out) >= max_fig:
                    return out
    return out


def _ler_via_claude_code(pc, texto_email, anexos, historico_txt, instrucao=None, ferramenta=None):
    """Usa o Claude Code instalado no computador, logado na ASSINATURA do Claude (Pro/Max/Team) – sem chave de API.
    Equivale a: claude -p --model <m> --effort <e> --output-format json --json-schema <esquema>."""
    import subprocess, tempfile
    exe = _claude_cli()
    if not exe:
        raise RuntimeError("Claude Code não encontrado. Instale (claude.com/claude-code) e faça login com sua conta Claude.")
    instrucao = instrucao or INSTRUCAO
    esquema = (ferramenta or _ferramenta())["input_schema"]
    figs = _figuras_pdf(anexos)
    pastas = sorted({os.path.dirname(os.path.abspath(a)) for a in list(anexos or []) + [f for f, _ in figs]})
    lista = "\n".join(f"- {os.path.abspath(a)}" for a in anexos or [])
    if figs:
        lista += ("\n\nFIGURAS EXTRAÍDAS DOS PDFs (gráficos – espectros de harmônicas, tendências). Quando o texto não trouxer os "
                  "valores por ordem harmônica, ABRA estas imagens com Read e leia os valores pela escala do gráfico (THD e cada "
                  "ordem, tensão em % e corrente em A ou %), dizendo em `observacoes` que foram lidos da figura:\n"
                  + "\n".join(f"- {os.path.abspath(f)}  [{leg}]" for f, leg in figs))
    prompt = (f"{instrucao}\nResponda SOMENTE com o JSON do pedido (esquema fornecido).\n\n"
              f"Arquivos anexos (leia PDF/imagens com a ferramenta Read; o texto do Word/PDF já vai abaixo):\n{lista or '(nenhum)'}\n\n"
              f"TEXTO DOS ANEXOS:\n{_texto_anexos(anexos)}\n\nE-MAIL:\n{texto_email}\n\n{historico_txt}")
    # o esquema vai no PROMPT (não em --json-schema): no Windows o claude.cmd passa pelo cmd.exe, que estraga aspas/JSON na linha
    prompt += "\n\nESQUEMA (campos possíveis; omita os desconhecidos):\n" + json.dumps(esquema["properties"], ensure_ascii=False)
    cmd = [exe, "-p", "--output-format", "json", "--model", pc["modelo"], "--allowedTools", "Read"]
    if pc.get("esforco"):
        cmd += ["--effort", pc["esforco"]]
    for d in pastas:
        cmd += ["--add-dir", d]
    r = subprocess.run(cmd, input=prompt, capture_output=True, text=True, encoding="utf-8", timeout=600,
                       cwd=tempfile.gettempdir(), creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if r.returncode != 0 and not r.stdout.strip():
        raise RuntimeError(f"Claude Code retornou erro: {(r.stderr or r.stdout)[:300]}")
    out = json.loads(r.stdout)
    if out.get("is_error"):
        raise RuntimeError(f"Claude Code: {str(out.get('result'))[:300]}")
    dados = out.get("structured_output")
    if not dados:
        txt = str(out.get("result", ""))
        dados = json.loads(txt[txt.find("{"): txt.rfind("}") + 1])
    return dados


def ler_com_ia(texto_email: str, anexos: Optional[List[str]] = None, historico_txt: str = "", provedor: str = None) -> Pedido:
    dados, pc = extrair_dados(texto_email, anexos, INSTRUCAO, _ferramenta(), historico_txt, provedor)
    ped = _completar(Pedido.from_dict(dados))
    ped.observacoes = (ped.observacoes + f" [lido por IA: {pc['nome']} / {pc['modelo']}"
                       + (f" / esforço {pc['esforco']}" if pc.get("esforco") else "") + "]").strip()
    return ped


def extrair_dados(texto_email, anexos, instrucao, ferramenta, historico_txt="", provedor=None):
    """v1.14.0: MESMO caminho de IA do filtro senoidal (Claude Code pela assinatura, API Anthropic ou compatível OpenAI),
    com instrução e esquema próprios – usado também por bancos dessintonizados e filtros sintonizados."""
    cfg = config_ia()
    provedor = provedor or cfg.get("provedor_padrao", "claude")
    pc = cfg["provedores"][provedor]
    if pc["tipo"] == "claude_code":
        dados = _ler_via_claude_code(pc, texto_email, anexos, historico_txt, instrucao, ferramenta)
    elif pc["tipo"] == "anthropic":
        import anthropic
        carregar_chaves()
        cli = anthropic.Anthropic(api_key=os.environ.get(pc.get("env_chave") or "ANTHROPIC_API_KEY"))
        conteudo = _blocos_anexos(anexos) + [{"type": "text", "text": f"E-MAIL:\n{texto_email}\n\n{historico_txt}\n\n"
                                                                     f"Chame a ferramenta {ferramenta['name']} com os dados extraídos."}]
        extra = {"output_config": {"effort": pc["esforco"]}} if pc.get("esforco") else {}
        # modelos 5.x pensam (thinking adaptativo): tool_choice "auto" + instrução (forçar a ferramenta não combina com thinking)
        resp = cli.messages.create(model=pc["modelo"], max_tokens=16000, system=instrucao, tools=[ferramenta],
                                   tool_choice={"type": "auto"}, messages=[{"role": "user", "content": conteudo}],
                                   extra_body=extra or None)
        dados = next((b.input for b in resp.content if b.type == "tool_use"), None)
        if dados is None:
            txt = "".join(getattr(b, "text", "") for b in resp.content)
            dados = json.loads(txt[txt.find("{"): txt.rfind("}") + 1])
    else:
        # API compatível com OpenAI: ChatGPT, DeepSeek, Gemini, Mistral, Grok, OpenRouter, Ollama local
        from openai import OpenAI
        env = pc.get("env_chave") or ""
        cli = OpenAI(base_url=pc["base_url"], api_key=os.environ.get(env, "") if env else "ollama")
        esquema = json.dumps(ferramenta["input_schema"]["properties"], ensure_ascii=False)
        msg = (f"{instrucao}\nResponda SOMENTE com um objeto JSON com estes campos (omita os desconhecidos):\n{esquema}\n\n"
               f"E-MAIL:\n{texto_email}\n{_texto_anexos(anexos)}\n{historico_txt}")
        resp = cli.chat.completions.create(model=pc["modelo"], temperature=0,
                                           response_format={"type": "json_object"},
                                           messages=[{"role": "user", "content": msg}])
        conteudo = resp.choices[0].message.content
        conteudo = conteudo[conteudo.find("{"): conteudo.rfind("}") + 1]
        dados = json.loads(conteudo)
    return dados, pc


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
    # ---- dados de instalação / inversor / cabo (antes eram sempre perguntados de novo no questionário)
    ach = set()
    v = _num(r"(?:\bfs\b|frequ[eê]ncia de chaveamento|freq\.? de chaveamento|chaveamento)\D{0,12}(\d{1,2}(?:[.,]\d+)?)\s*kHz", t)
    if v:
        p.fs_khz = v; ach.add("fs_khz")
    m = re.search(r"\b(vetorial|sensorless|escalar|V/f|V/Hz|DTC)\b", t, re.I)
    if m:
        p.inversor_controle = {"v/hz": "escalar V/f", "v/f": "escalar V/f"}.get(m.group(1).lower(), m.group(1).lower()); ach.add("inversor_controle")
    v = _num(r"(?:ambiente|temperatura ambiente|t\.?\s*amb)\D{0,15}(\d{2})\s*°?\s*C\b", t)
    if v:
        p.amb_max_c = v; ach.add("amb_max_c")
    v = _num(r"altitude\D{0,10}(\d{2,4}(?:[.,]\d+)?)\s*m\b", t)
    if v is not None:
        p.altitude_m = v; ach.add("altitude_m")
    m = re.search(r"\bIP\s?(\d{2})\b", t)
    if m:
        p.ip = "IP" + m.group(1); ach.add("ip")
    m = re.search(r"\b(abrigad[ao]|ao tempo|intemp[eé]rie|externa)\b", t, re.I)
    if m:
        p.instalacao = "abrigada" if m.group(1).lower().startswith("abrig") else "ao tempo"; ach.add("instalacao")
    m = re.search(r"(\d)\s*[x×]\s*\(?\s*(?:\d\s*[x×]\s*)?(\d{1,3}(?:[.,]\d+)?)\s*mm[²2]", t)
    v = _num(r"(\d{1,3}(?:[.,]\d+)?)\s*mm[²2]", t)
    if v:
        p.cabo_secao_mm2 = v; ach.add("cabo_secao_mm2")
    m = re.search(r"(\d)\s*cabos? em paralelo|(\d)\s*(?:x|×)\s*por fase", t, re.I)
    if m:
        p.cabo_paralelos = int(m.group(1) or m.group(2)); ach.add("cabo_paralelos")
    if re.search(r"cabo[^.]{0,30}blindad|blindad[^.]{0,20}cabo", t, re.I):
        p.cabo_blindado = True; ach.add("cabo_blindado")
    elif re.search(r"(?:n[aã]o|sem)\s+blindad", t, re.I):
        p.cabo_blindado = False; ach.add("cabo_blindado")
    m = re.search(r"\b(TN-S|TN-C-S|TN-C|TT|IT)\b(?=[^a-z])", t)
    if m and re.search(r"aterramento|esquema|rede", t, re.I):
        p.aterramento = m.group(1); ach.add("aterramento")
    m = re.search(r"filtro EMC[^.]{0,25}?\b(sim|n[aã]o|ligado|desligado|interno)\b", t, re.I)
    if m:
        p.inversor_filtro_emc = m.group(1); ach.add("inversor_filtro_emc")
    if re.search(r"motor[^.]{0,30}(?:para|pr[oó]prio para|adequado a)\s+inversor|inverter duty|NEMA MG\s?1 Pa?r?t?\.?\s?31", t, re.I):
        p.motor_para_inversor = "sim"; ach.add("motor_para_inversor")
    if re.search(r"mancal isolado|rolamento isolado|escova de aterramento", t, re.I):
        p.mancal_isolado = "sim"; ach.add("mancal_isolado")
    v = re.search(r"(?:auxiliar|ventila[cç][aã]o|ventiladores)\D{0,15}(\d{3})\s*V", t, re.I)
    if v:
        p.alim_aux_v = v.group(1) + " V"; ach.add("alim_aux_v")
    m = re.search(r"(\d{3,4})\s*[x×]\s*(\d{3,4})\s*[x×]\s*(\d{3,4})\s*mm", t)
    if m:
        p.dim_max_mm = "×".join(m.groups()); ach.add("dim_max_mm")
    if re.search(r"bomba|bombeador|ventilador|exaustor", t, re.I):
        p.carga_tipo = "torque quadrático (bomba/ventilador)"; ach.add("carga_tipo")
    # campos achados no texto contam como INFORMADOS mesmo quando o valor coincide com o padrão (ex.: 60 Hz, IP54)
    if fx:
        ach.update({"f_saida_min_hz", "f_saida_max_hz"})
    padrao = Pedido()
    p.informados = sorted(ach | {k for k in Pedido.__dataclass_fields__ if k not in ("lacunas", "informados")
                                 and getattr(p, k) not in (None, "", 0, []) and getattr(p, k) != getattr(padrao, k)})
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
    # v1.26.4 (auditoria AW-07): a premissa escrita pela IA não pode contradizer o campo usado no cálculo (ex.: 'adotar não
    # blindado' com cabo_blindado = True) – vale o campo; a frase é reescrita
    _bl = bool(getattr(p, "cabo_blindado", True))
    lac2 = []
    for t in lac:
        tl = str(t).lower()
        if "blindad" in tl and "cabo" in tl and ("não informad" in tl or "nao informad" in tl or "adot" in tl):
            t = ("Tipo do cabo do motor não informado – adotado cabo "
                 + ("blindado simétrico para inversor (aterramento 360° nas duas pontas)" if _bl else "NÃO blindado (unipolar em eletrocalha)")
                 + "; confirmar com o cliente (muda a tensão de modo comum e a tensão no mancal).")
        lac2.append(t)
    p.lacunas = list(dict.fromkeys(lac2))
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
        except Exception as e:  # sem rede/chave: segue por regras – e AVISA na tela (lacunas)
            print(f"[leitor_ia] IA {provedor} indisponível ({e}); usando regras.")
            p = ler_por_regras((texto or "") + "\n" + _texto_anexos(anexos))
            p.lacunas = [f"⚠️ A IA ({provedor}) falhou e a leitura foi feita por REGRAS – confira tudo: {type(e).__name__}: {str(e)[:200]}"] + p.lacunas
            return p
    # v1.8.3: sem IA, lê também .docx (parágrafos + TABELAS – a solicitação da A&W vem numa tabela)
    return ler_por_regras((texto or "") + "\n" + _texto_anexos(anexos))
