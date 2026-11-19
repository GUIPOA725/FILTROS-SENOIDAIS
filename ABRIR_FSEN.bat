@echo off
title Plataforma FSEN - Filtros Senoidais
chcp 65001 >nul
echo ================================================================
echo   PLATAFORMA FSEN - Filtros Senoidais LC/LCL - Electric Service
echo ================================================================
echo.

REM --- 1) copia a versao do Drive para este computador (roda mais rapido e sem conflito no Drive)
set "ORIGEM=%~dp0"
set "LOCAL=%LOCALAPPDATA%\FSEN\programa"
echo [1/4] Atualizando a copia local do programa...
robocopy "%ORIGEM%." "%LOCAL%" /MIR /XD __pycache__ saidas /XF historico.db /NFL /NDL /NJH /NJS /NP >nul
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

REM --- 4) configuracoes e abertura
set "FSEN_PASTA_SAIDA=G:\Drives compartilhados\Engenharia\15 - TEMPLATES-PLANILHA ESTUDOS\PLATAFORMA FILTROS SENOIDAIS\PROJETOS"
REM Chave da IA (opcional). Tire o REM e cole a chave para usar o Claude na leitura dos e-mails:
REM set ANTHROPIC_API_KEY=sk-ant-...
echo [4/4] Abrindo a plataforma no navegador...  ^(NAO feche esta janela enquanto estiver usando^)
start "" cmd /c "timeout /t 6 >nul & start http://localhost:8501"
%PY% -m streamlit run app.py --server.headless true --browser.gatherUsageStats false
echo.
echo Plataforma encerrada.
pause
