# Design notes: what comes next

Larger changes that are planned but not built yet, with how we'd build them and why. Each one says
what it protects against and what it needs first. For the order they come in, see the
[pilot plan](pilot.md#1-priorities).

## A/B system images and Secure Boot

**Today:** a live system. The image on the USB stick or disk is read-only, and a restart always
gives a clean system. Updates come through Debian's unattended upgrades into the running system.

**Next:** two system partitions, A and B. The PC runs from A; an update is written whole to B, and
the next start uses B. If B doesn't start, or a health check fails, the PC goes back to A on its
own. The system partitions are read-only (dm-verity), so nothing can change them while running.
Tools: systemd-boot or GRUB with boot counting, `systemd-sysupdate` for the images, and a
unified kernel image (UKI) signed with the owner's own Secure Boot key, so only Medicus images
start.

*Protects against:* a half-done update that leaves a PC unusable, and malware that changes the
system so it survives a restart. *Needs:* the disk installer, and an owner's key kept in an HSM.

## Measured boot and attestation

Each step of the start (firmware, boot loader, kernel, system image) is measured into the TPM. A
PC can then **prove** to a server that it runs an approved image, before it gets access.

The plan: the RADIUS server (or a small attestation service next to it) checks the TPM quote
before the 802.1X login. A PC that doesn't prove its image gets a quarantine network with only the
update server, not the clinical network.

*Needs:* A/B images (so there is a known "good" measurement), and a service that keeps the list of
good measurements for each released version. **When it's down,** the PCs keep their last decision
for a set time (e.g. 24 hours), so staff aren't locked out (see the pilot plan, section 2).

## Revocation of machine certificates

**Today:** a stolen PC can be locked out by revoking its certificate on the certificate authority.

**Next:** the RADIUS server checks each certificate against the CA through OCSP (or a CRL fetched
every 15 minutes) at each 802.1X login. IT's routine for a lost PC: revoke the certificate, block
the MAC address, and note the serial number in the incident log. The same is planned for the VPN
keys of mobile PCs: a WireGuard key is removed from the server's peer list.

Card revocation is already built (`medicus-kort tilbakekall`, see the IT handbook).

## Downtime mode

When the record system is down for a long time (hours), the unit uses its paper routine today.

**Next:** a read-only **downtime copy** of the essentials for patients on the unit right now (the
patient list, the critical information, the medication list), updated every 15 minutes by the
record system to one PC per unit, encrypted, and shown only in downtime mode. Notes written
during the downtime are kept and sent to the record when it's back, marked as written during
downtime.

*Must be decided with the unit and the record system's supplier first:* who may open the
downtime copy, how it's kept safe on the PC, and how notes are merged back without mistakes.

## Patient context across apps

When a patient is opened in one app (the record system, Medicus, the lab system), the others
should follow, so no one writes in the wrong patient's record.

**Next:** a local "context manager" on the PC that the apps tell when a patient is opened, and
that shows the current patient in the taskbar. It follows the HL7 CCOW idea or, for web apps,
SMART on FHIR launch context. Every app that can't follow is shown with a warning colour when it
has a different patient open.

## Logs off the PC

**Today:** the audit log can be sent to a central log server as it's written (the *sink*, see the
IT handbook), and IT can take the anchors off the PC (`medicus-revisjon ankre`) and keep them elsewhere.

**Next:** a fixed set-up for the central server: the PCs send over TLS with the machine
certificate, the server keeps the logs read-only for the time the law requires (pasientjournal-
loven and Normen), and it checks each PC's chain every night. A PC that stops sending for more
than an hour shows up in IT's overview.

## Start screens for each role, and notifications

A doctor, a nurse and a secretary need different things first. **Next:** a start screen per role
(from the card's role): the doctor's patient list and unapproved notes, the nurse's tasks and
NEWS2 scores, the secretary's Post. One notification centre for Post, results and requests, with
quiet hours, so staff aren't interrupted with a patient.

## Workload metrics

**Paused.** Numbers like "notes per hour" or "time per patient" could help plan staffing, but
they're also monitoring of employees. They won't be built before the DPIA and the talks with the
employee representatives (see the [pilot plan](pilot.md#7-monitoring-of-employees-dpia-and-employee-representatives))
say they can be, and then only as numbers for a whole unit, never per person. The same holds for
automatic "snooping detection" in the access log.

## Full Northern Sámi translation

**Today:** the Northern Sámi keyboard (Alt+Shift), so names and text in Sámi can be typed.

**Next:** all Medicus text in Northern Sámi too, through gettext, translated by professional
translators who know health vocabulary, with the Sámi Parliament (Sámediggi) asked to advise, and
letters to patients in Sámi when they want it. Lule and South Sámi after that.

## Medical device regulation (MDR)

Software that helps with diagnosis or treatment can be a medical device under EU MDR (2017/745).
Our assessment, to be confirmed by the regulatory authority (*Direktoratet for medisinske
produkter*, DMP) and a notified body:

| Part | Our view | Why |
|---|---|---|
| The OS, Post, browser, login | Not a medical device | General IT |
| Unit conversion (volume, weight) | Not a medical device, probably | Plain conversion; it has a warning not to use it for dosing |
| Clinical scores (NEWS2, GCS, CURB-65, CHA₂DS₂-VASc, Cockcroft-Gault, QTc …) | **Class IIa, probably** (rule 11) | They support decisions about treatment |
| The journal assistant (draft notes) | Unclear; at least class I, perhaps IIa | It summarises, but the clinician approves every word |

Until this is settled, the calculators and the journal assistant say clearly that they are
decision support, show the formula and its source, and leave the decision to the clinician. A
pilot uses them only with the unit's agreement.

## Live memory and the TPM

It isn't possible to "seal" a running session's memory with the TPM: the TPM protects keys, not RAM
that the processor is using. What protects a held session (card out for under 15 minutes)
instead: the screen is locked, memory encryption (AMD SME, or Intel TME switched on in the
firmware; the `mem_encrypt=on` boot option), and the kernel's protections against reading another
process's memory. Against someone who takes the PC with the session held, the answer is the
short hold time, and that the PC can't get on the network without its certificate.

## Pinned Python packages

**Done (24 Oct 2026):** `requirements.txt` is a lock file with exact versions and hashes, made from
the version ranges in `requirements.in` with `pip-compile --generate-hashes`. The ISO build installs
it with `pip install --require-hashes`, so a changed or fake package on PyPI stops the build, and
GitHub Actions runs every test against exactly these versions on Debian 13. The lock file is
updated on purpose (the command is at the top of `requirements.in`), with the tests run before it
is committed.

**Next:** check the lock file against known vulnerabilities on every update (`pip-audit`), and
later use Debian's own packages (`python3-fastapi` etc.) where they're new enough, so all software
comes signed from Debian.
