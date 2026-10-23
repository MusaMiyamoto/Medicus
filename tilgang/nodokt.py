"""The emergency-access session: a full-screen browser showing only the emergency page.

There is no desktop, Start menu or file access. When the 30 minutes are up or the user
presses "Avslutt", medicus-oktvakt ends the session. Closing the browser ends it too.
"""

import subprocess
import sys

from .client import AuthError, call

URL = "http://127.0.0.1:8000/nod"


def main() -> int:
    try:
        subprocess.run(["medicus-nettleser", "--kiosk", URL], check=False)
    finally:
        try:
            call("end")
        except AuthError:
            pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
