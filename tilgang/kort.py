"""medicus-kort: command-line control of the simulated card reader.

    medicus-kort status
    medicus-kort liste
    medicus-kort sett-inn <kort-id>
    medicus-kort ta-ut
    medicus-kort opphev-sperre <kort-id>   IT: lift a PIN block after checking the person's ID
    medicus-kort tilbakekall <kort-id> tapt|stjålet|erstattet
                                           IT: the card stops working everywhere, at once
    medicus-kort gjenopprett <kort-id>     IT: a lost card turned up again (check the person's ID)
"""

import os
import sys

from .client import AuthError, call

COMMAND = "/usr/local/bin/medicus-kort"


def main(argv: list[str]) -> int:
    command = argv[0] if argv else "status"
    try:
        if command == "status":
            reply = call("status")
            card, session = reply["kort"], reply["okt"]
            print(f"Kort i leser: {card['navn']} ({card['rolle']})" if card else "Ingen kort i leseren.")
            print(f"Økt: {session['navn']}, {session['modus']}" if session else "Ingen aktiv økt.")
        elif command == "liste":
            for c in call("cards")["kort"]:
                flags = ("  SPERRET" if c["sperret"] else "") + (f"  TILBAKEKALT ({c['tilbakekalt']})"
                                                                   if c.get("tilbakekalt") else "")
                print(f"{c['card_id']:<8} {c['navn']:<16} {c['rolle']:<16}{flags}")
        elif command == "sett-inn" and len(argv) == 2:
            call("insert", card_id=argv[1])
            print("Kort satt inn.")
        elif command == "ta-ut":
            call("remove")
            print("Kort tatt ut.")
        elif command in ("tilbakekall", "gjenopprett") and len(argv) == (3 if command == "tilbakekall" else 2):
            if os.geteuid() != 0:
                os.execvp("sudo", ["sudo", COMMAND, *argv])
            who = os.getenv("SUDO_USER", "root")
            if command == "tilbakekall":
                call("revoke", card_id=argv[1], grunn=argv[2], it_bruker=who)
                print("Kortet er tilbakekalt og virker ikke lenger noe sted. En åpen økt på kortet er avsluttet. "
                      "Dette er loggført. Meld det også til den som utsteder kortene.")
            else:
                call("restore", card_id=argv[1], it_bruker=who)
                print("Kortet virker igjen. Dette er loggført.")
        elif command == "opphev-sperre" and len(argv) == 2:
            # IT only: sudo asks for the IT card's PIN, and authd only accepts this from root.
            if os.geteuid() != 0:
                print("Sjekk legitimasjonen til personen først. Skriv PIN-koden for IT-kortet når du blir spurt.")
                os.execvp("sudo", ["sudo", COMMAND, "opphev-sperre", argv[1]])
            call("unblock", card_id=argv[1], it_bruker=os.getenv("SUDO_USER", "root"))
            print("Sperren er opphevet. Kortet har tre nye forsøk. Dette er loggført.")
        else:
            print(__doc__)
            return 2
    except AuthError as e:
        print(e, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
