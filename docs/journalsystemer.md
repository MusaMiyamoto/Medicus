# Journal systems: DIPS, transfer from Epic, and the hospital's own system next to Medicus

How Medicus saves notes into a patient's record, where the doctor's patient list comes from, and how
a record is moved from Epic. The code is in [`epj/`](../epj/) (*elektronisk pasientjournal*).

The last section covers showing the hospital's existing record system in a locked-down window
next to Medicus. That code is in [`journalsystem/`](../journalsystem/).

> Medicus is a prototype with synthetic data. A connection to a real DIPS or Epic needs an agreement
> with the health trust or municipality and the vendor, a HelseID client and a DPIA first.

## Settings

Everything is in `/etc/medicus/integrasjon.toml`:

```toml
[journal]
system = "helsenett"   # or "dips"

[dips]
fhir_url = ""                         # the DIPS FHIR R4 address the health trust gives you
token_fil = "/etc/medicus/dips/token"

[epic]
fhir_url = ""                         # only for fetching straight from Epic
token_fil = "/etc/medicus/epic/token"
```

Until a real connection is set up, every DIPS or Epic call says what is missing instead of failing silently.

## The journal assistant's patient picker

The journal assistant has a search field at the top. It drops down the doctor's own patients
(fastlege list, or today's list in DIPS). The doctor can search by name, birth date or the start of
the fødselsnummer. A patient who is not on the list is found by typing the whole fødselsnummer. That
lookup is logged.

With a patient chosen, **Godkjenn** becomes **Godkjenn og lagre i journalen**. The approved note is
saved in that patient's record, in the system set under `[journal]`. Without a patient the note is
only approved and logged, as before.

## DIPS Arena (FHIR R4)

[`epj/dips.py`](../epj/dips.py) uses standard FHIR R4:

| What | FHIR call |
|---|---|
| Find the patient | `GET Patient?identifier=urn:oid:2.16.578.1.12.4.1.4.1\|<fødselsnummer>` |
| The doctor's patients today | `GET Encounter?practitioner.identifier=urn:oid:2.16.578.1.12.4.1.4.4\|<HPR>&date=ge<today>&_include=Encounter:subject` |
| Save the approved note | `POST DocumentReference` (status `current`, docStatus `final`, LOINC 11506-3, author by HPR number, the text inline as UTF-8) |

Before a real connection, the health trust and DIPS must confirm:

- the FHIR address, and that these searches are supported in their installation (some use
  appointment lists, `Appointment`, instead of `Encounter`)
- which document type and status notes from Medicus should have
- the HelseID client and scopes Medicus gets. Today the token is read from `token_fil`, which is
  only for test environments.

**Trying it without DIPS:** the helsenett simulator has a small FHIR server at
`http://127.0.0.1:8100/fhir`. Set `system = "dips"`, `fhir_url = "http://127.0.0.1:8100/fhir"`, and
put any text in the token file. Notes saved this way show up in Pasientjournal.

## Transfer from Epic

For patients coming from a hospital or municipality that uses Epic. It is under **Overføring** in Medicus.

1. **Load** an Epic FHIR R4 export (a Bundle `.json` file), or fetch it straight from Epic by
   fødselsnummer (needs `[epic]`).
2. **Check** the preview: who it is, allergies, diagnoses, medicines and documents, plus warnings,
   for example a PDF that can't be moved or a name that differs.
3. **Confirm** that it is the right person, and import.

What happens on import:

- One summary note (allergies, diagnoses, medicines) and one note per text document are saved in the
  journal system.
- **Allergies and medicines become text marked "må kontrolleres"**, never critical information
  (kjernejournal) directly. A clinician registers them after checking.
- The patient sees on Helsenorge that the record was moved, and by whom. The security log gets `record_transferred`.
- The preview is kept on the server for 30 minutes, only for the person who loaded it, and can be imported once.

What is read: `Patient` (must have a fødselsnummer or D-nummer), `AllergyIntolerance`, `Condition`,
`MedicationRequest`, `MedicationStatement`, `Medication` and `DocumentReference` with text, inline or
in a `Binary`. Entries marked `entered-in-error` are skipped. When fetching from Epic, a document's
`Binary` is only fetched from the same Epic server, so the access token is never sent anywhere else.

A synthetic example is in [`samples/epic-eksport-eksempel.json`](../samples/epic-eksport-eksempel.json)
(Kari Nordmann, a test patient in the simulator).

## The hospital's own record system next to Medicus

A hospital doesn't switch record system overnight. Medicus can show the one it has, DIPS Arena,
Epic or another, in its own window. The system keeps running on the hospital's servers; the Medicus
PC only shows it. IT lists the systems in `/etc/medicus/journalsystemer.toml` and runs
`sudo medicus-journalsystem oppdater`. Each system gets an icon in the Start menu.

```toml
[[system]]
navn = "DIPS Arena"
type = "rdp"                        # a RemoteApp from the hospital's Remote Desktop servers
server = "rds.sykehuset.no"
program = "||DIPSArena"             # the published RemoteApp; leave out for the whole remote desktop
gateway = "rdgw.sykehuset.no"       # optional

[[system]]
navn = "Epic (web)"
type = "web"                        # a web version, opened in Nettleser
url = "https://epic.sykehuset.no/"
```

**Remote window (`rdp`)**, with FreeRDP:

| | |
|---|---|
| Login | The health worker's **own card** (smart-card logon), so there is **no second login**. The servers must accept smart-card logon with the health personnel cards. |
| Shared with the server | **Nothing**: no disks, no clipboard, no USB, no printers. Patient data can't be copied out through the window, and the server can't reach the PC's files. The card is shared so the record system can sign, for example prescriptions. The microphone is shared only if `mikrofon = true`, for dictation. |
| Server certificate | Must be trusted by the PC (`/cert:deny`). There is no "connect anyway". |
| Network | The firewall opens **only** the listed servers' addresses and ports. The addresses go into `/etc/hosts`, because users have no DNS of their own. They are refreshed at boot and every 30 minutes. |

**Web version (`web`):** opens in Nettleser. Only that exact host name is allowed, over HTTPS, and
the web filter lets it through.

**Who can open them:** only health personnel with a normal card login. They are not available in IT
mode, during emergency access, or while the session is held after the card was taken out.

**If something is wrong in the file:**
- *One bad entry:* `oppdater` refuses the whole change, so nothing half-checked goes live.
- *The file can't be read at all:* Nettleser allows no extra hosts.
- *VPN kill switch on* (`medicus-vpn på`): the servers must be reached through the VPN.
- **Test against the hospital's real servers first:** smart-card logon in a remote session depends on
  how their servers and card readers are set up.
