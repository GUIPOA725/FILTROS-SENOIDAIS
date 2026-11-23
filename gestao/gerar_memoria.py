"""Gera gestao/MEMORIA_PROJETO.md – a memória LEVE do projeto que a IA da plataforma lê (REQ-IA-012).
Rodar antes de publicar cada versão:  python gestao/gerar_memoria.py
Fontes: este cabeçalho (contexto escrito), gestao/REQUISITOS.yaml (palavras do engenheiro), REFERENCIAS_PROJETOS.yaml e CHANGELOG.md.
O histórico literal das conversas fica à parte em gestao/conversas/ (pesado – a IA não lê inteiro)."""
import datetime as dt
import json
import os
import re

import yaml

G = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(G)

CONTEXTO = """# Memória do projeto – Plataforma FSEN (Electric Service)

## O que é
Plataforma (Python/Streamlit, roda no computador de cada um) que projeta três produtos da Electric Service: **filtro senoidal**
(saída de inversor), **banco de capacitores dessintonizado** e **filtro harmônico sintonizado** (padrão ou robusto). A partir do
pedido do cliente (e-mail, medições de qualidade de energia, placa do trafo) ela dimensiona, simula, projeta o reator por
elementos finitos, escolhe componentes reais de catálogo, desenha o painel (2D e 3D de montagem), gera esquema elétrico, lista de
material até o parafuso, verificação por normas, especificações para fornecedores e um relatório consolidado.

## Quem é quem
- **Guilherme** – engenheiro responsável. Só ele altera o código e aprova componentes/painéis para a equipe. A experiência de campo
  dele (projetos antigos feitos à mão e instalados) é a referência; os projetos antigos são ponto de partida, o novo tem que ser melhor.
- **Colegas** – operam a plataforma; podem cadastrar componentes na biblioteca (entram "a conferir") e mandar a IA executar projetos.
- **IA** – orquestra e executa; o engenheiro aprova. Nada de achismo: tudo calculado, com fonte, e com coluna Check.

## Como a equipe usa
- Abrir pelo atalho "FSEN Filtros": a cada abertura a plataforma se atualiza pela versão do Drive (PROGRAMAS\\FSEN_v1.7.1).
- Menu **Nova solicitação**: colar e-mail/anexos → ler → conferir → gerar. Menu **🤖 Assistente IA**: perguntar ou mandar fazer
  ("faça um <filtro> com os dados da pasta <caminho> e salve em <caminho>").
- Resultados em PROJETOS\\<cliente>\\<código>_<marca>_<data>: 00_RELATORIO_CONSOLIDADO, RESUMO.md, 01_Engenharia, 02_Cliente,
  03_Fornecedores (reator e montadora do painel), 05_Desenhos.
- Drive (PLATAFORMA FILTROS SENOIDAIS): PROGRAMAS (código oficial), PROJETOS, BIBLIOTECA_PAINEIS (painéis aprovados),
  BIBLIOTECA_COMPONENTES (componentes da equipe), MEMORIA_IA (esta memória + registro de uso), ATUALIZACOES-MELHORIAS (CHANGELOG e gestão).

## Regras de segurança da operação
Nunca digitar senhas; não usar robô no ATPDraw; não instalar programas nem apagar projetos/tarefas sem o engenheiro; código só
com o engenheiro; componente novo só vale para todos depois da aprovação dele; projeto com componente "a conferir" (vermelho no
3D) NÃO está liberado para cotação.

## Leitura do resultado
Todo resultado tem coluna **Check**: ✔ APROVADO, ⚠ ATENÇÃO (perto do limite ou a confirmar), ✖ REPROVADO, INFO. A planilha
Conferencia_Esquema_x_Painel_x_Lista confere esquema elétrico × painel 2D/3D × lista de material: tem que dar zero reprovado.
"""


def main():
    req = yaml.safe_load(open(os.path.join(G, "REQUISITOS.yaml"), encoding="utf-8"))["requisitos"]
    ver = json.load(open(os.path.join(RAIZ, "versao_plataforma.json"), encoding="utf-8"))
    L = [CONTEXTO, f"_Gerado em {dt.datetime.now():%d/%m/%Y %H:%M} – plataforma v{ver.get('versao')} – {len(req)} requisitos registrados._\n",
         "## Regras e decisões do engenheiro (registro de requisitos – palavras dele)",
         "Legenda: ! = crítico; situação: ATENDIDO / PARCIAL / PENDENTE.\n"]
    por_area = {}
    for r in req:
        por_area.setdefault(r.get("area", "GERAL"), []).append(r)
    for area in sorted(por_area):
        L.append(f"### {area}")
        for r in por_area[area]:
            txt = re.sub(r"\s+", " ", str(r.get("requisito", ""))).strip()
            nota = re.sub(r"\s+", " ", str(r.get("nota") or "")).strip()
            L.append(f"- {r['id']}{' !' if r.get('critico') else ''} [{r.get('status')}] {txt}" + (f" — nota: {nota[:220]}" if nota else ""))
        L.append("")
    try:
        refs = yaml.safe_load(open(os.path.join(G, "REFERENCIAS_PROJETOS.yaml"), encoding="utf-8"))["referencias"]
        L.append("## Projetos de referência (lições)")
        for r in refs:
            nome = r.get("nome") or r.get("id") or "?"
            lic = r.get("licoes") or r.get("lições") or []
            lic = lic if isinstance(lic, list) else [lic]
            L.append(f"- **{nome}**: " + " | ".join(re.sub(r"\s+", " ", str(x))[:260] for x in lic[:3]))
        L.append("")
    except Exception as ex:
        L.append(f"(referências não lidas: {ex})")
    try:
        ch = open(os.path.join(RAIZ, "CHANGELOG.md"), encoding="utf-8").read()
        blocos = re.split(r"\n(?=## v)", ch)[1:5]
        L.append("## Últimas versões (resumo do CHANGELOG)")
        for b in blocos:
            lin = b.strip().splitlines()
            L.append("- **" + lin[0].replace("## ", "") + "**: " + " ".join(re.sub(r"\*\*", "", x.strip("- ").strip())[:150] for x in lin[1:5]))
        L.append("")
    except Exception:
        pass
    L.append("## Histórico literal\nAs conversas completas do engenheiro com a IA estão em gestao/conversas/ (no programa e no Drive em "
             "ATUALIZACOES-MELHORIAS\\GESTAO\\conversas). Consulte lá quando precisar da frase exata.")
    txt = "\n".join(L)
    open(os.path.join(G, "MEMORIA_PROJETO.md"), "w", encoding="utf-8").write(txt)
    print(f"MEMORIA_PROJETO.md: {len(txt)} caracteres, {len(req)} requisitos")


if __name__ == "__main__":
    main()
