@echo off
REM Instala dependencias (Anaconda/Python ja instalados)
cd /d %~dp0
python -m pip install -r requirements.txt
echo.
echo Instalacao concluida. Use INICIAR.bat para abrir a plataforma.
pause
