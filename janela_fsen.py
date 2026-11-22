"""Abre a Plataforma FSEN como PROGRAMA (janela própria), não como aba do navegador – v1.18.2.

O motor continua o mesmo (Streamlit, só neste computador, sem internet); muda só a casca:
  1. sobe o servidor escondido numa porta livre (sem janela preta);
  2. abre uma janela própria com título e ícone "FSEN v…":
       a) pywebview (janela nativa do Windows – Edge WebView2), se instalado;
       b) senão, Edge (ou Chrome) em modo APLICATIVO (--app): janela sem abas, sem barra de endereço, perfil separado;
       c) último recurso: navegador padrão;
  3. ao fechar a janela, o servidor é encerrado.
Log em %LOCALAPPDATA%\\FSEN\\janela.log.
"""
import json
import os
import socket
import subprocess
import sys
import time
import urllib.request

RAIZ = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.join(os.environ.get("LOCALAPPDATA") or os.path.expanduser("~"), "FSEN")
LOG = os.path.join(BASE, "janela.log")


def log(msg):
    os.makedirs(BASE, exist_ok=True)
    with open(LOG, "a", encoding="utf-8") as fh:
        fh.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {msg}\n")


def porta_livre(pref=8501):
    for p in [pref] + list(range(8502, 8600)):
        with socket.socket() as s:
            try:
                s.bind(("127.0.0.1", p))
                return p
            except OSError:
                continue
    return pref


def versao():
    try:
        return json.load(open(os.path.join(RAIZ, "versao_plataforma.json"), encoding="utf-8")).get("versao", "")
    except Exception:
        return ""


def subir_servidor(porta):
    py = sys.executable
    if py.lower().endswith("pythonw.exe"):
        cand = py[:-len("pythonw.exe")] + "python.exe"
        py = cand if os.path.exists(cand) else py
    cmd = [py, "-m", "streamlit", "run", os.path.join(RAIZ, "app.py"), "--server.headless", "true",
           "--server.port", str(porta), "--server.address", "127.0.0.1", "--browser.gatherUsageStats", "false",
           "--client.toolbarMode", "minimal"]
    os.makedirs(BASE, exist_ok=True)
    out = open(os.path.join(BASE, "servidor.log"), "w", encoding="utf-8")
    return subprocess.Popen(cmd, cwd=RAIZ, stdout=out, stderr=subprocess.STDOUT,
                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))


def esperar(url, srv, limite=120):
    t0 = time.time()
    while time.time() - t0 < limite:
        if srv.poll() is not None:
            return False
        try:
            urllib.request.urlopen(url + "/_stcore/health", timeout=2)
            return True
        except Exception:
            time.sleep(0.5)
    return False


def navegador_app():
    cands = [os.path.join(os.environ.get(v, ""), *p) for v, p in (
        ("ProgramFiles(x86)", ("Microsoft", "Edge", "Application", "msedge.exe")),
        ("ProgramFiles", ("Microsoft", "Edge", "Application", "msedge.exe")),
        ("ProgramFiles", ("Google", "Chrome", "Application", "chrome.exe")),
        ("ProgramFiles(x86)", ("Google", "Chrome", "Application", "chrome.exe")),
        ("LOCALAPPDATA", ("Google", "Chrome", "Application", "chrome.exe")))]
    return next((c for c in cands if c and os.path.exists(c)), None)


def abrir_janela(url, titulo):
    try:
        import webview  # pywebview
        log("janela: pywebview")
        webview.create_window(titulo, url, width=1500, height=950, min_size=(1100, 700), maximized=True)
        webview.start()
        return True
    except Exception as e:
        log(f"pywebview indisponível ({type(e).__name__}: {e}) – tentando Edge/Chrome em modo aplicativo")
    exe = navegador_app()
    if exe:
        perfil = os.path.join(BASE, "janela_perfil")
        log(f"janela: {exe} --app")
        p = subprocess.Popen([exe, f"--app={url}", f"--user-data-dir={perfil}", "--start-maximized",
                              "--no-first-run", "--no-default-browser-check", "--disable-features=Translate"])
        p.wait()
        return True
    import webbrowser
    log("janela: navegador padrão (último recurso)")
    webbrowser.open(url)
    input("Plataforma aberta no navegador. Feche esta janela para encerrar.") if sys.stdin and sys.stdin.isatty() else time.sleep(10 ** 7)
    return True


def main():
    porta = porta_livre()
    url = f"http://127.0.0.1:{porta}"
    log(f"iniciando FSEN v{versao()} em {url}")
    srv = subir_servidor(porta)
    try:
        if not esperar(url, srv):
            log("servidor não respondeu – veja servidor.log")
            try:
                import ctypes
                ctypes.windll.user32.MessageBoxW(0, f"A plataforma não iniciou. Envie ao suporte o arquivo:\n{os.path.join(BASE, 'servidor.log')}",
                                                 "FSEN", 0x10)
            except Exception:
                pass
            return
        abrir_janela(url, f"FSEN v{versao()} – Filtros e Bancos – Electric Service")
    finally:
        srv.terminate()
        try:
            srv.wait(10)
        except Exception:
            srv.kill()
        log("encerrado")


if __name__ == "__main__":
    main()
