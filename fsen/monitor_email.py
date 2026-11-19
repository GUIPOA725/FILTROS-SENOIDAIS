"""Monitor de caixa de e-mail (IMAP) – automação total.

A cada N minutos procura e-mails novos de solicitação de filtro senoidal, baixa anexos, lê com IA,
roda a plataforma completa, salva tudo na pasta do Google Drive e cria um RASCUNHO de resposta ao cliente
(com proposta e folha de dados anexas) para você só revisar e enviar.

Configuração (variáveis de ambiente ou dados/config_local.yaml):
  FSEN_IMAP_HOST=imap.gmail.com   FSEN_IMAP_USER=contato@electricservice.com.br
  FSEN_IMAP_SENHA=<senha de app do Google>   FSEN_PASTA_SAIDA=G:/Meu Drive/FILTRO SENOIDAL - PLATAFORMA/PROJETOS
  ANTHROPIC_API_KEY=<chave>  (leitura por IA)
"""
from __future__ import annotations
import os
import re
import time
import email
import imaplib
import datetime as _dt
from email.header import decode_header
from email.message import EmailMessage

from .leitor_ia import ler_pedido
from .pipeline import processar

PALAVRAS = ["filtro senoidal", "sine wave", "filtro sen", "filtro lc", "filtro lcl", "senoidal"]


def _dec(v):
    if not v:
        return ""
    out = ""
    for txt, enc in decode_header(v):
        out += txt.decode(enc or "utf-8", "ignore") if isinstance(txt, bytes) else txt
    return out


def _corpo(msg):
    partes = []
    for part in msg.walk():
        if part.get_content_type() == "text/plain" and not part.get_filename():
            partes.append(part.get_payload(decode=True).decode(part.get_content_charset() or "utf-8", "ignore"))
    if not partes:
        for part in msg.walk():
            if part.get_content_type() == "text/html":
                html = part.get_payload(decode=True).decode(part.get_content_charset() or "utf-8", "ignore")
                partes.append(re.sub(r"<[^>]+>", " ", html))
    return "\n".join(partes)


def _anexos(msg, pasta):
    os.makedirs(pasta, exist_ok=True)
    out = []
    for part in msg.walk():
        fn = part.get_filename()
        if fn:
            fn = re.sub(r"[^\w.\-]", "_", _dec(fn))
            cam = os.path.join(pasta, fn)
            with open(cam, "wb") as f:
                f.write(part.get_payload(decode=True))
            out.append(cam)
    return out


def _rascunho(imap, de, para, assunto, corpo, anexos):
    m = EmailMessage()
    m["From"], m["To"], m["Subject"] = de, para, assunto
    m.set_content(corpo)
    for a in anexos:
        with open(a, "rb") as f:
            m.add_attachment(f.read(), maintype="application", subtype="octet-stream", filename=os.path.basename(a))
    pasta = '"[Gmail]/Drafts"' if "gmail" in (os.environ.get("FSEN_IMAP_HOST", "")) else "Drafts"
    for tentativa in (pasta, '"[Gmail]/Rascunhos"', "Drafts", "INBOX.Drafts"):
        typ, _ = imap.append(tentativa, "\\Draft", imaplib.Time2Internaldate(time.time()), m.as_bytes())
        if typ == "OK":
            return True
    return False


def verificar_uma_vez(log=print):
    host = os.environ.get("FSEN_IMAP_HOST", "imap.gmail.com")
    user = os.environ["FSEN_IMAP_USER"]
    senha = os.environ["FSEN_IMAP_SENHA"]
    saida = os.environ.get("FSEN_PASTA_SAIDA")
    imap = imaplib.IMAP4_SSL(host)
    imap.login(user, senha)
    imap.select("INBOX")
    desde = (_dt.date.today() - _dt.timedelta(days=3)).strftime("%d-%b-%Y")
    typ, ids = imap.search(None, f'(UNSEEN SINCE {desde})')
    feitos = []
    for num in ids[0].split():
        typ, dados = imap.fetch(num, "(RFC822)")
        msg = email.message_from_bytes(dados[0][1])
        assunto = _dec(msg["Subject"])
        corpo = _corpo(msg)
        if not any(p in (assunto + " " + corpo).lower() for p in PALAVRAS):
            imap.store(num, "-FLAGS", "\\Seen")
            continue
        log(f"Solicitação encontrada: {assunto}")
        tmp = os.path.join(saida or ".", "_entrada", _dt.datetime.now().strftime("%Y%m%d_%H%M%S"))
        anexos = _anexos(msg, tmp)
        texto = f"De: {_dec(msg['From'])}\nAssunto: {assunto}\n\n{corpo}"
        ped = ler_pedido(texto, anexos)
        if not ped.email_contato:
            ped.email_contato = email.utils.parseaddr(_dec(msg.get("Reply-To") or msg["From"]))[1]
        r = processar(ped, saida, log=log)
        cli = os.path.join(r["pasta"], "02_Cliente")
        anexos_resp = [os.path.join(cli, f) for f in os.listdir(cli) if f.endswith(".docx")]
        corpo_resp = open(os.path.join(cli, "Email_Resposta_Cliente.txt"), encoding="utf-8").read().split("\n\n", 1)[1]
        _rascunho(imap, user, ped.email_contato, f"RE: {assunto}", corpo_resp, anexos_resp)
        imap.store(num, "+FLAGS", "\\Seen")
        feitos.append(r["pasta"])
    imap.logout()
    return feitos


def monitorar(intervalo_min=5):
    print(f"Monitorando e-mails a cada {intervalo_min} min. Ctrl+C para sair.")
    while True:
        try:
            feitos = verificar_uma_vez()
            if feitos:
                print(f"{len(feitos)} projeto(s) gerado(s): {feitos}")
        except Exception as e:
            print("Erro no monitor:", e)
        time.sleep(intervalo_min * 60)
