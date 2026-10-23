"""Login and access control for Medicus OS.

Three ways in:
  normal     health-personnel smart card + PIN. Full access to patients you treat.
  nød        emergency access: card + one tap on the situation, no PIN, so it is fast.
             Life-critical information only, read-only, 30 minutes, logged with the
             person's identity. That person must write a report before the shift ends.
  it         IT staff card + PIN. IT tools (terminal, settings, Sikkerhetssenter), admin
             rights confirmed with the card PIN, and no access to patient data.

`medicus-authd` holds the card state and the active session. The login screen, PAM, the
journal app and the session watcher all ask it, so you log in once for everything.
"""

EMERGENCY_USER = "nodtilgang"
# Cards with this role belong to IT staff. They have no HPR number; their card carries the
# employee number in the "hpr" field instead, so the security log still says who it was.
IT_ROLE = "IT"
EMERGENCY_MINUTES = 30
# The emergency report is due within this many hours: the end of the longest normal shift.
REPORT_HOURS = 12
# Shown as big buttons after tapping "Nødtilgang": one more tap starts it, no typing.
SITUATIONS = ("Hjertestans", "Bevisstløs pasient", "Alvorlig allergisk reaksjon",
              "Alvorlig skade / ulykke", "Annen livstruende situasjon")
SOCKET = "/run/medicus-auth/auth.sock"
