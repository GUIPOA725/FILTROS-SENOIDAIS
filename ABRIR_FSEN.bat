@echo off
title Plataforma FSEN - Filtros Senoidais
chcp 65001 >nul
echo ================================================================
echo   PLATAFORMA FSEN - Filtros Senoidais LC/LCL - Electric Service
echo ================================================================
echo.

REM --- 1) copia a versao do Drive para este computador (roda mais rapido e sem conflito no Drive)
set "ORIGEM=%~dp0"
REM v1.18.5: sempre abre a versao MAIS NOVA do Drive (pasta PROGRAMAS\FSEN_v1.7.1), mesmo que o atalho
REM ou o duplo-clique tenha sido numa pasta de versao antiga (FSEN_plataforma_v1.xx.x)
for %%I in ("%~dp0..\FSEN_v1.7.1") do set "CANON=%%~fI\"
REM v1.31.2 (REQ-GER-018): se a pasta irma nao existir (versao extraida em outro lugar), usa o caminho oficial do Drive
if not exist "%CANON%ABRIR_FSEN.bat" set "CANON=G:\Drives compartilhados\Engenharia\15 - TEMPLATES-PLANILHA ESTUDOS\PLATAFORMA FILTROS SENOIDAIS\PROGRAMAS\FSEN_v1.7.1\"
if exist "%CANON%ABRIR_FSEN.bat" if /i not "%ORIGEM%"=="%CANON%" (
  echo Abrindo a versao mais nova: %CANON%
  call "%CANON%ABRIR_FSEN.bat"
  exit /b
)
set "LOCAL=%LOCALAPPDATA%\FSEN\programa"
echo [1/4] Atualizando a copia local do programa...
REM v1.32.1 (REQ-GER-019): /R:2 /W:2 - sem isso o robocopy tenta 1 milhao de vezes (30 s cada) um arquivo que o Google Drive
REM ainda esta sincronizando e a janela fica parada em [1/4]. Se algum arquivo falhar, segue com a copia local que ja existe.
REM v1.32.3: se a copia local ja tem a MESMA versao do Drive, nao copia nada (abre na hora, sem depender do Drive).
REM So copia quando a versao muda; log em %LOCALAPPDATA%\FSEN\robocopy.log para diagnostico.
fc /b "%ORIGEM%versao_plataforma.json" "%LOCAL%\versao_plataforma.json" >nul 2>&1
if errorlevel 1 (
  robocopy "%ORIGEM%." "%LOCAL%" /MIR /R:1 /W:1 /XD __pycache__ saidas .git /XF historico.db /NP /LOG:"%LOCALAPPDATA%\FSEN\robocopy.log" >nul
  if errorlevel 8 echo   Aviso: alguns arquivos do Drive ainda estao sincronizando - abrindo com a copia local.
) else (
  echo       copia local ja esta na versao do Drive.
)
cd /d "%LOCAL%"

REM --- 2) procura o Python (Anaconda primeiro)
set "PY="
if exist "%USERPROFILE%\anaconda3\python.exe" set "PY=%USERPROFILE%\anaconda3\python.exe"
if not defined PY if exist "%USERPROFILE%\miniconda3\python.exe" set "PY=%USERPROFILE%\miniconda3\python.exe"
if not defined PY if exist "C:\ProgramData\anaconda3\python.exe" set "PY=C:\ProgramData\anaconda3\python.exe"
if not defined PY (
  for %%V in (3.12 3.11 3.13 3.10) do (
    if not defined PY py -%%V -c "import sys" >nul 2>&1 && set "PY=py -%%V"
  )
)
if not defined PY python -c "import sys" >nul 2>&1 && set "PY=python"
if not defined PY (
  echo.
  echo  ERRO: Python nao encontrado. Instale o Anaconda ^(anaconda.com^) e rode de novo.
  pause
  exit /b 1
)
echo [2/4] Python: %PY%

REM --- 3) instala as bibliotecas na primeira vez (ou quando o requirements mudar)
fc /b requirements.txt "%LOCALAPPDATA%\FSEN\req_ok.txt" >nul 2>&1
if errorlevel 1 (
  echo [3/4] Instalando bibliotecas ^(so na primeira vez, pode levar alguns minutos^)...
  %PY% -m pip install --upgrade pip >nul 2>&1
  %PY% -m pip install -r requirements.txt
  if errorlevel 1 (
    echo.
    echo  ERRO na instalacao das bibliotecas. Tire um print desta janela e mande para o Claude.
    pause
    exit /b 1
  )
  copy /y requirements.txt "%LOCALAPPDATA%\FSEN\req_ok.txt" >nul
) else (
  echo [3/4] Bibliotecas ja instaladas.
)

REM --- 4) janela propria (v1.18.2): pywebview na primeira vez (opcional - se falhar, abre em modo aplicativo do Edge/Chrome)
if not exist "%LOCALAPPDATA%\FSEN\webview_ok.txt" (
  echo [4/5] Preparando a janela do programa ^(so na primeira vez^)...
  %PY% -m pip install pywebview >nul 2>&1
  echo ok> "%LOCALAPPDATA%\FSEN\webview_ok.txt"
)

REM --- 5) atalho na area de trabalho (uma vez) e abertura como PROGRAMA (sem navegador, sem janela preta)
set "FSEN_ORIGEM=%ORIGEM%"
set "FSEN_PASTA_SAIDA=G:\Drives compartilhados\Engenharia\15 - TEMPLATES-PLANILHA ESTUDOS\PLATAFORMA FILTROS SENOIDAIS\PROJETOS"
REM Chave da IA (opcional). Tire o REM e cole a chave para usar o Claude na leitura dos e-mails:
REM set ANTHROPIC_API_KEY=sk-ant-...
REM v1.18.5: o atalho e sempre refeito apontando para esta pasta (a mais nova), corrigindo atalhos antigos
(
  powershell -NoProfile -Command "$s=(New-Object -ComObject WScript.Shell).CreateShortcut([Environment]::GetFolderPath('Desktop')+'\FSEN Filtros.lnk');$s.TargetPath='%ORIGEM%ABRIR_FSEN.bat';$s.WorkingDirectory='%ORIGEM%';$s.WindowStyle=7;$s.Description='Plataforma FSEN - Filtros e Bancos';$s.Save()" >nul 2>&1
)
set "PYW=%PY%"
if /i "%PY:~-10%"=="python.exe" set "PYW=%PY:~0,-10%pythonw.exe"
if /i "%PY:~0,3%"=="py " set "PYW=pyw %PY:~3%"
if /i "%PY%"=="python" set "PYW=pythonw"
echo [5/5] Abrindo a plataforma...  ^(esta janela fecha sozinha^)
start "" %PYW% "%LOCAL%\janela_fsen.py"
exit /b 0
