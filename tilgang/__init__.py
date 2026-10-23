"""Login and access control for Medicus OS.

Two ways in:
  normal     health-personnel smart card + PIN. Full access to patients you treat.
  nød        emergency access: card tap + reason, no PIN. Critical information only,
             30 minutes, always logged with the person's identity and reviewed afterwards.

`medicus-authd` holds the card state and the active session. The login screen, PAM, the
journal app and the session watcher all ask it, so you log in once for everything.
"""

EMERGENCY_USER = "nodtilgang"
EMERGENCY_MINUTES = 30
SOCKET = "/run/medicus-auth/auth.sock"
