# Pilot plan

What has to be in place before Medicus runs on real PCs with real staff, and how a first pilot can
go without putting patients or staff at risk. For the people who decide on a pilot: the health
trust or municipality, its IT and security teams, the clinic leaders and the employee
representatives.

> Medicus is a prototype with synthetic data. Nothing here has been tried with real patients,
> real chip cards or a real record system yet. This plan is how that would start.

## 1. Priorities

In order. Each step needs the one before it.

1. **Agreements and assessments.** A data processing agreement, a DPIA (GDPR art. 35), a risk
   assessment under Normen, the MDR assessment of the journal assistant and the calculators
   (see [Design](design.md#medical-device-regulation-mdr)), and talks with the employee
   representatives (section 7).
2. **Real login.** Real chip cards through PKCS#11 and HelseID instead of the simulated card
   reader. Nothing clinical goes live before this.
3. **Installation to disk** with full-disk encryption, by IT, from a protected installer mode.
4. **One record system** through its approved interface (DIPS Arena or the hospital's own, see
   [Journal systems](journalsystemer.md)), read first, write later.
5. **Central services** set up and monitored: the update server, the certificate authority for the
   machine certificates, the RADIUS server, the central log server (section 2).
6. **A small pilot** on one unit, side by side with the PCs it has today (section 6).
7. **Measure and decide**: time saved, errors, support cases, what staff say. Then wider, or stop.

## 2. When a central service is down

Medicus must never lock staff out of patient care because a server somewhere is down. What happens
today, and what the pilot must check:

| Service down | What Medicus does | Staff can still |
|---|---|---|
| Update server | Keeps running the version it has; updates come again when the server is back | Work as normal |
| Certificate authority / RADIUS | A PC whose certificate is still valid keeps getting on the network. A certificate that runs out can't be renewed, so Sikkerhetssenter warns 30 days ahead | Work; IT renews when it's back |
| Record system (or the remote desktop server) | The record window shows an error; an unfinished note is kept as a draft (in memory only, never on disk, for up to one shift) until it's back | Write notes, use the calculators, read Post |
| Central log server | The audit log is kept on the PC and the sink failure is logged; nothing is lost (see the IT handbook) | Work as normal |
| HelseID (when real login is in) | Card + PIN still works on the PC; network services that need a token stop | Emergency access as today |
| Whole clinical network | The PC is "outside the clinical network": normal login stops, **emergency access still works** and is marked as such | Emergency access: critical information, 30 minutes, logged |

**Downtime routine:** the unit keeps its paper downtime routine (*nedetidsrutine*), as it has
today. Medicus doesn't replace it. A full "downtime mode" with a read-only local copy is in the
[design notes](design.md#downtime-mode).

The pilot tests each row on purpose, with IT watching, before go-live.

## 3. Support, service level and responsibility

To agree before the pilot, in writing:

- **Who answers the phone.** First line: the unit's own IT support (*brukerstøtte*), using the
  [IT handbook](IT-handbok.md). Second line: whoever maintains Medicus.
- **How fast.** A suggestion to discuss: a PC that stops clinical work is fixed or swapped within
  1 hour during the day and 4 hours at night; other faults the next working day. **Spare PCs** on
  the unit make this realistic: swapping a PC takes minutes, because nothing is stored on it.
- **Security fixes.** Critical fixes rolled out within 48 hours of the fix being ready; the SBOM
  that comes with every build shows within minutes whether a new vulnerability affects it.
- **Who is responsible.** The data controller (*behandlingsansvarlig*) stays the health trust or
  municipality. The maintainer is a data processor under the agreement. The clinician is still
  responsible for what goes into the record: Medicus only drafts.

## 4. Funding, ownership and licence

These are choices for the owner, not for this document. The options:

| Option | Good | Watch out for |
|---|---|---|
| **Open source, owned by the public sector** (e.g. through Norsk helsenett or a joint municipal company) | No lock-in; any trust can use and check the code; fits procurement | Someone must be paid to maintain it, long term |
| **Public owner, paid maintenance contract** | Clear responsibility and service level | The contract must keep the code and the right to change supplier |
| **Grant-funded pilot first** (e.g. innovation funds) | Low cost to try | Plan who pays after the pilot, before it starts |
| **Commercial product with a licence** | Funds a team | Lock-in; harder for other trusts to join |

Whatever is chosen: the code, the build scripts and the SBOM must stay with the owner, so the system
can always be rebuilt and checked without the original maker.

## 5. Threat model

Who we protect against, and what stops them. Short version; the details are in the IT handbook.

| Attacker | What they want | What stops them |
|---|---|---|
| **Thief** takes a PC or the disk | Patient data | Nothing stored locally after logout (home folder wiped); full-disk encryption with the disk installer (step 3); the PC can't get on the network without its TPM certificate |
| **Curious colleague** opens records they have no reason to | Snooping | Card + PIN per person; a reason is asked for any patient not on your list; every opening logged with name and reason; patients can see who looked |
| **Someone at an unlocked PC** | Use a logged-in session | Card out = locked; idle lock; tap-in only within the IT-set limit on the clinical network |
| **Phishing / malware** | Credentials, ransomware | No program runs from the home folder; Post warns on outside mail; the browser only reaches approved sites; virus scanning |
| **Insider with admin rights** | Hide what they did | The audit log is hash-chained with forward-secure keys, and the anchors and (with a log server) every line are kept off the PC; changing old lines breaks the chain |
| **Network attacker** | Read or change traffic | 802.1X with the machine certificate; VPN with kill switch on mobile PCs; the firewall only lets approved systems through |
| **Lost or stolen card** | Log in as someone else | The PIN, and IT revokes the card at once, everywhere, including emergency access |

Not covered by Medicus alone: an attacker with physical access to an *unlocked, logged-in* PC for
a long time, a compromised record system, and supply-chain attacks on Debian itself (the SBOM and
signed packages reduce, but don't remove, that risk).

## 6. Rolling out next to what's there

No "big bang". Medicus runs **next to** today's PCs, and the unit can stop at any time.

1. **Week 0:** IT installs 2–3 Medicus PCs on one unit, next to the old ones. The record system
   opens in its locked-down window, so nothing changes in how records are kept.
2. **Weeks 1–4:** volunteers use Medicus for some of their work. The old PCs stay. Every problem
   is written down, with the time it cost.
3. **Week 4:** a check with the unit, IT and the employee representatives. Go on, change, or stop.
4. **Weeks 5–12:** more PCs, if the check says so. The journal assistant only after the MDR
   assessment and with the unit's agreement.
5. **End:** a short report: time saved, errors, support cases, what staff and patients said.

**Way back:** at any point, the unit goes back to its old PCs the same day. Nothing is stored only
on Medicus, so nothing is lost.

## 7. Monitoring of employees, DPIA and employee representatives

Medicus logs who opened which record, when and why. That is required by law (pasientjournalloven
§ 16 and Normen) and protects patients. But logs are also information about employees, so:

- The DPIA covers staff as well as patients.
- **Employee representatives** (*tillitsvalgte*) are involved before the pilot, as the Working
  Environment Act chapter 9 (control measures, *kontrolltiltak*) requires: what is logged, who can
  read it, for how long, and what it may **not** be used for.
- The access log is only used to check access to patient records, as the law intends, not to
  measure how fast people work.
- **Paused until this is agreed:** automatic "snooping detection" and usage or workload metrics.
  They are in the [design notes](design.md#workload-metrics) only, and won't be built until the
  DPIA and the talks with the employee representatives say they can be.

## 8. Mobile workers

Home nurses, ambulance staff and doctors on call work outside the hospital network.

- **Mobile profile** (`profil: mobil` on the workplace): login only through the WireGuard VPN with
  the kill switch on; tap-in is off; the IT handbook has the details.
- **No mobile signal:** login stops, but **emergency access** still works, marked as outside the
  clinical network. Notes can be written; an unfinished note is kept as a draft in memory (never on disk) for up
  to one shift. Patient data the person hasn't opened before is not available offline.
- **Shared car PCs** (ambulance): card out = locked, and the home folder is wiped at logout, so the
  next crew gets a clean PC.
- To try in the pilot: battery life, signal in rural areas, and how the card reader holds up in a car.

## 9. When a card or reader fails

Cards and readers will fail, at the worst moment. The routine:

| What happened | What to do | Medicus |
|---|---|---|
| **Forgot the card at home** | Get a **day card** (*dagkort*) from the unit leader or the reception, on ID. It's personal, logged, and runs out the same day | Works as a normal card while valid |
| **Card lost or stolen** | Call IT at once. IT revokes it (`medicus-kort tilbakekall`) | Refused everywhere, also for emergency access; a try is logged as an alert |
| **Card expired** | Get a new one from the card office | Normal login refused; emergency access still allowed, logged |
| **Card blocked** (wrong PIN too many times) | IT unblocks it after checking ID | Login refused until unblocked |
| **Reader broken** | Use the next PC; IT swaps the reader (a spare per unit) | No card can be read on that PC |
| **New card** (replaced) | The old one is revoked as "replaced" | The old card stops working at once |

**Never share a card.** Everything done with a card is logged as that person's. If someone can't
log in, the answer is a day card or emergency access, not a colleague's card. The units keep a few
spare day cards in a locked place, and IT checks each month that they are all there.
