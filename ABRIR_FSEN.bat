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
REM v1.36.1 (REQ-GER-021): a copia local so ganha o versao_plataforma.json DEPOIS de copiar tudo sem erro, e a copia e
REM conferida (arquivos principais). Antes, uma copia interrompida (Drive ainda baixando) ficava marcada como atualizada
REM e a plataforma abria quebrada ("No module named fsen.modelos").
set "OK_LOCAL=1"
for %%F in (app.py janela_fsen.py fsen\__init__.py fsen\modelos.py fsen\pipeline.py fsen\dimensionamento.py requirements.txt) do (
  if not exist "%LOCAL%\%%F" set "OK_LOCAL=0"
)
if "%OK_LOCAL%"=="0" del "%LOCAL%\versao_plataforma.json" >nul 2>&1
fc /b "%ORIGEM%versao_plataforma.json" "%LOCAL%\versao_plataforma.json" >nul 2>&1
if errorlevel 1 goto :copiar
goto :copiado
:copiar
REM v1.36.2 (REQ-GER-021): primeiro tenta o ZIP da versao (1 arquivo de ~4 MB baixa rapido do Google Drive; centenas de
REM arquivos pequenos num computador novo demoram muitos minutos e a janela parecia travada em [1/4]).
set "VER="
for /f "usebackq delims=" %%V in (`powershell -NoProfile -Command "(Get-Content -LiteralPath '%ORIGEM%versao_plataforma.json' -Raw | ConvertFrom-Json).versao"`) do set "VER=%%V"
set "ZIP=%ORIGEM%..\FSEN_plataforma_v%VER%.zip"
if defined VER if exist "%ZIP%" (
  echo       baixando o pacote da versao %VER% ^(zip^)...
  powershell -NoProfile -Command "$t=Join-Path $env:TEMP 'fsen_zip'; Remove-Item $t -Recurse -Force -EA SilentlyContinue; Expand-Archive -LiteralPath '%ZIP%' -DestinationPath $t -Force; $s=(Get-ChildItem $t -Directory | Select-Object -First 1).FullName; New-Item -ItemType Directory -Force -Path '%LOCAL%' | Out-Null; Copy-Item -Path (Join-Path $s '*') -Destination '%LOCAL%' -Recurse -Force"
)
if exist "%LOCAL%\fsen\modelos.py" if exist "%LOCAL%\versao_plataforma.json" (
  fc /b "%ORIGEM%versao_plataforma.json" "%LOCAL%\versao_plataforma.json" >nul 2>&1
  if not errorlevel 1 goto :copiado
)
echo       copiando arquivo por arquivo do Drive ^(pode levar alguns minutos na primeira vez^)...
  robocopy "%ORIGEM%." "%LOCAL%" /MIR /R:3 /W:3 /XD __pycache__ saidas .git /XF historico.db versao_plataforma.json /NP /LOG:"%LOCALAPPDATA%\FSEN\robocopy.log" >nul
  if errorlevel 8 (
    echo   Aviso: o Google Drive ainda esta baixando arquivos - abrindo direto da pasta do Drive desta vez.
    set "LOCAL=%ORIGEM:~0,-1%"
  ) else (
    copy /y "%ORIGEM%versao_plataforma.json" "%LOCAL%\versao_plataforma.json" >nul
  )
:copiado
if not exist "%LOCAL%\fsen\modelos.py" (
  echo   Aviso: copia local incompleta - abrindo direto da pasta do Drive.
  set "LOCAL=%ORIGEM:~0,-1%"
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
