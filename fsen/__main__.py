"""Linha de comando da plataforma FSEN.

  python -m fsen processar exemplos/email_AW_293A.txt [--anexo arquivo.pdf] [--ia] [--saida PASTA]
  python -m fsen json exemplos/AW_293A_440V.json
  python -m fsen monitor --intervalo 5
  python -m fsen importar "G:/Meu Drive/.../6 - FILTRO SENOIDAL LC" "G:/Meu Drive/.../7 - FILTRO SENOIDAL LCL"
  python -m fsen clientes clientes_fornecidos.xlsx
  python -m fsen cotacao-indutor Cootrans 47.4 8200     (registra preço real -> recalibra custo)
"""
import argparse
import json
import os
import sys


def main(argv=None):
    ap = argparse.ArgumentParser(prog="fsen", description="Plataforma de filtros senoidais LC/LCL")
    sp = ap.add_subparsers(dest="cmd", required=True)
    a = sp.add_parser("processar", help="lê um e-mail (.txt/.eml) e gera tudo")
    a.add_argument("email")
    a.add_argument("--anexo", action="append", default=[])
    a.add_argument("--ia", action="store_true", help="forçar leitura por IA (ANTHROPIC_API_KEY)")
    a.add_argument("--saida", default=os.environ.get("FSEN_PASTA_SAIDA"))
    a.add_argument("--capacitor", action="append", default=None, help="restringe aos capacitores do catálogo (ex.: TDK_PEC_20u_480)")
    j = sp.add_parser("json", help="processa um pedido em JSON")
    j.add_argument("arquivo")
    j.add_argument("--saida", default=os.environ.get("FSEN_PASTA_SAIDA"))
    m = sp.add_parser("monitor", help="monitora a caixa de e-mail (IMAP) e processa automaticamente")
    m.add_argument("--intervalo", type=int, default=5)
    i = sp.add_parser("importar", help="importa pastas antigas de clientes para o histórico")
    i.add_argument("pastas", nargs="+")
    c = sp.add_parser("clientes", help="exporta planilha de clientes fornecidos")
    c.add_argument("saida", nargs="?", default="clientes_fornecidos.xlsx")
    q = sp.add_parser("cotacao-indutor", help="registra preço real de indutor (energia em J, preço R$)")
    q.add_argument("fornecedor")
    q.add_argument("energia_j", type=float)
    q.add_argument("preco", type=float)
    args = ap.parse_args(argv)

    if args.cmd == "processar":
        from .leitor_ia import ler_pedido
        from .pipeline import processar
        txt = open(args.email, encoding="utf-8", errors="ignore").read()
        ped = ler_pedido(txt, args.anexo, usar_ia=True if args.ia else None)
        r = processar(ped, args.saida, capacitores=args.capacitor)
        print("\n" + r["resumo"])
    elif args.cmd == "json":
        from .modelos import Pedido
        from .pipeline import processar
        ped = Pedido.from_dict(json.load(open(args.arquivo, encoding="utf-8")))
        r = processar(ped, args.saida)
        print("\n" + r["resumo"])
    elif args.cmd == "monitor":
        from .monitor_email import monitorar
        monitorar(args.intervalo)
    elif args.cmd == "importar":
        from .historico import importar_pastas
        r = importar_pastas(args.pastas)
        print(f"{r['arquivos']} arquivos catalogados; {len(r['clientes'])} clientes/pastas:")
        for cl, t in r["clientes"]:
            print(f"  [{t}] {cl}")
    elif args.cmd == "clientes":
        from .historico import exportar_clientes_xlsx
        print(exportar_clientes_xlsx(args.saida))
    elif args.cmd == "cotacao-indutor":
        from .historico import registrar_cotacao_fornecedor, calibrar_custo_indutor
        registrar_cotacao_fornecedor(args.fornecedor, "INDUTOR", "indutor filtro senoidal", args.energia_j, args.preco)
        print("Calibração atual:", calibrar_custo_indutor() or "precisa de ≥ 2 cotações")


if __name__ == "__main__":
    sys.exit(main())
