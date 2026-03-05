import argparse
import sys
from src.cli.controller import CLI_Controller

def main():
    parser = argparse.ArgumentParser(prog="coinami", description="Client CLI Coinami (Light Wallet)")
    subparsers = parser.add_subparsers(dest="command", help="Commandes disponibles")

    # Commande init
    subparsers.add_parser("init", help="Générer un nouveau wallet sécurisé")

    # Commande balance
    parser_balance = subparsers.add_parser("balance", help="Consulter votre solde")
    parser_balance.add_argument("--node-url", help="URL optionnelle du nœud")

    # Commande send
    parser_send = subparsers.add_parser("send", help="Envoyer des fonds")
    parser_send.add_argument("--to", required=True, help="Adresse du destinataire")
    parser_send.add_argument("--amount", required=True, type=float, help="Montant à envoyer")
    parser_send.add_argument("--node-url", help="URL optionnelle du nœud")

    args = parser.parse_args()
    
    controller = CLI_Controller()

    if args.command == "init":
        controller.init_cmd()
    elif args.command == "balance":
        controller.balance_cmd(node_url=args.node_url)
    elif args.command == "send":
        controller.send_cmd(to=args.to, amount=args.amount, node_url=args.node_url)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
