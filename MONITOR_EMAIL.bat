@echo off
REM Automacao: le e-mails novos, gera tudo e cria rascunho de resposta
cd /d %~dp0
set FSEN_PASTA_SAIDA=G:\Drives compartilhados\Engenharia\15 - TEMPLATES-PLANILHA ESTUDOS\PLATAFORMA FILTROS SENOIDAIS\PROJETOS
set FSEN_IMAP_HOST=imap.gmail.com
set FSEN_IMAP_USER=contato@electricservice.com.br
REM set FSEN_IMAP_SENHA=senha_de_app_do_google
REM set ANTHROPIC_API_KEY=sk-ant-...
python -m fsen monitor --intervalo 5
