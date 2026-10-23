# Journal systems: DIPS and transfer from Epic

How Medicus saves notes into a patient's record, where the doctor's patient list comes from, and how
a record is moved from Epic. The code is in [`epj/`](../epj/) (*elektronisk pasientjournal*).

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
