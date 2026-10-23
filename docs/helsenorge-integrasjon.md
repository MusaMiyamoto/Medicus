# Connecting Medicus OS to Helsenorge and the national health services

Medicus OS is built so it can be connected to Norway's national health services if an agreement
with Norsk helsenett (NHN) happens. Until then, it runs against a **local simulator** with
synthetic test patients, using the same interface.

> **Check before relying on this.** Service names, requirements and processes below are based on
> public information as understood when this was written, and they change. Confirm every point
> directly with Norsk helsenett before planning work or costs.

## How it's built

```
 Medicus apps (patient record, emergency page, journal assistant)
        │  use only this interface ↓
 helsenett.client.HelsenettClient
        ├── SimulatedClient ──► helsenett-sim on 127.0.0.1:8100   (today)
        └── NhnClient ────────► Norsk helsenett services           (after an agreement)
```

The setting `modus` in `/etc/medicus/integrasjon.toml` chooses which one is used:

```toml
modus = "simulert"   # today
modus = "nhn"        # after an agreement: fill in the [nhn] section
```

Nothing else in Medicus needs to change. The apps don't know which one they're talking to.

## What each Medicus feature maps to

| Medicus feature | Method | National service | Status |
|---|---|---|---|
| Login for health personnel | (OS login) | **HelseID** with chip card | Card reader simulated; real card support (PC/SC, OpenSC) installed |
| Look up a patient | `find_patient` | Folkeregisteret (through NHN) | Simulated |
| Critical information (emergency and normal) | `critical_info` | **Kjernejournal** | Simulated |
| Visits and notes from all institutions | `encounters`, `add_note` | **Pasientens journaldokumenter** / document sharing | Simulated |
| Prescriptions | `prescriptions`, `prescribe` | **e-resept** (Reseptformidleren) | Simulated |
| Patient sees who opened their record | `log_access` | **Helsenorge** (access log and notices) | Simulated |
| Requests from authorities | simulator `/utlevering` | Handled by each institution's privacy officer and legal team, not a national API | Simulated workflow |

## Steps towards a real connection

1. **First conversation with Norsk helsenett.** Present Medicus, the use case and this architecture.
   Ask which services are realistic first and what the current requirements are.
2. **Membership of Helsenettet.** Required for connecting to the closed health network. It requires
   following **Normen** (the sector's security and privacy standard) and a membership agreement.
3. **Enterprise certificate.** Real services identify the institution with an enterprise
   certificate (*virksomhetssertifikat*) from an approved issuer.
4. **HelseID client.** Register Medicus as a HelseID client. Machine-to-machine calls use
   client credentials with a signed key (`private_key_jwt`). Health personnel log in to HelseID
   with their chip card, which replaces today's simulated card reader.
5. **Per-service approval.** Each national service (Kjernejournal, e-resept, document sharing,
   Helsenorge) has its own technical requirements, test environment and approval testing.
6. **Privacy and security documentation:**
   - A DPIA (*vurdering av personvernkonsekvenser*).
   - A risk assessment.
   - An external penetration test.
   - An assessment of whether Medicus is a **medical device** under EU MDR.
7. **Pilot** with one institution in NHN's test environment, then production.

## What is already prepared in the code

- **One interface** (`helsenett/client.py`) for every national service, with the mapping above in comments.
- **`NhnClient`**, the slot for the real services. Until it's implemented, every call fails safely with a
  message explaining what's missing (`IkkeTilkoblet`).
- **The settings file** `/etc/medicus/integrasjon.toml` with an `[nhn]` section ready to fill in.
- **The firewall** (`/etc/nftables.conf`) blocks all outgoing traffic from users and apps. It has
  an empty `helsenett4` set: add Helsenettet's address ranges there and Medicus can reach them,
  and nothing else.
- **Login identity:** every session already carries name, role, institution and HPR number, which
  is what the national services need to know about the person.
- **Access logging:** every time a record is opened (normal or emergency), Medicus sends who, why
  and what to `log_access`. That's the data Helsenorge shows patients.
- **The simulator** returns data in the same shape Medicus expects from the real services. Its
  tests (`tests/test_helsenett.py`) describe the expected behavior.

## What has to be built after an agreement

- Implement `NhnClient`: HelseID token handling, enterprise certificate, and each service's API
  according to NHN's specifications.
- Replace the simulated card reader in `tilgang/cards.py` with a PKCS#11 reader for real cards
  (the interface is already separate: `inserted()` and `verify_pin()`).
- Switch the access check from "any logged-in health worker" to an actual care relationship (*tjenstlig behov*),
  based on the institution's patient lists and roles.
- Remove the simulator service and the synthetic patient list from the production image.
