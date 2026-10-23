"""Called by pam_exec during login and screen unlock.

The PIN (or, for emergency access, the reason) arrives on stdin. Exit 0 lets the user in.
Anything printed is shown to the user, so only print safe, human-readable messages.
"""

import os
import sys

from . import EMERGENCY_USER
from .client import AuthError, call


def main() -> int:
    if os.getenv("PAM_TYPE") != "auth":
        return 0
    user = os.getenv("PAM_USER", "")
    secret = sys.stdin.read(1024).rstrip("\0\n")
    try:
        if user == EMERGENCY_USER:
            call("emergency", reason=secret)
        else:
            call("login", username=user, pin=secret)
    except AuthError as e:
        # pam_exec's `stdout` option shows this text on the login screen.
        print(e)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
