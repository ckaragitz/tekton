# Email draft — to your brother

**Subject:** Need your Revit eyes — files we generated *without* Revit (30 min?)

---

Hey —

Quick one, but it'd help me a lot. I've been building a tool (working name
**tekton**) that creates and edits Revit files *directly* — no Revit running,
no Autodesk seat. You describe what you want, or feed it an IFC, and it produces
the `.rvt`. Autodesk's own cloud viewer already opens and renders our output,
including 3D geometry for walls we authored ourselves. What I can't test is the
thing that actually matters for your world: **what happens when you File → Open
these in real Revit.** You'd literally be the first person to do it.

Attached: `tekton-eval-kit.zip`. Inside:

- `TEST-KIT/` — 8 files (`.rvt` + one `.rfa` family). **The main ask.**
- `REPORT-CARD.md` — a short table: what each file is + the one thing to check.
- the `tekton-plugin/` folder + `INSTALL.md` — optional; only if you want to actually
  talk to the tool through Claude (Track B below).

## Zeroth question — which Revit version do you run?

The files are **Revit 2026 format**, and Revit can't open files newer than
itself — so **if you're on Revit 2025 or older, every file in the kit will
refuse to open** (a "created in a later version" dialog). Two things if so:
the exact dialog text is *still* useful to me (please copy it), and a
**Revit-2025-native kit is in certification right now** — I'll send it the
moment it's done. If you can get at a 2026 seat (a trial counts), that
unlocks Track A today.

## Track A — the main ask (Revit 2026, ~30 min)

Open each file in `TEST-KIT/` in Revit and note, per the report card:
does it open, any warning dialogs (copy the text), does it look right,
can you edit and save. Screenshots welcome. The interesting ones:

- **02** — four walls *we* created, geometry and all. Do they show up and
  act like real walls?
- **04** — panelboards/switchboard/transformer *families we generated*, placed.
  Click one: does it carry PanelName / Voltage / BusRating properties?
- **05** — flagged experimental on purpose. I *expect* Revit might reject it.
  If it does, that confirms something; if it opens, that surprises me. Either
  way tell me.
- **06** — the 2500 A electrical room built from an IFC. Full circle if it
  looks like the room.
- **08** — a `.rfa`. Open it in the Family Editor, then try Load into Project.

Brutal honesty please — "this dialog popped up," "these walls are the wrong
type," "no engineer would accept this because ___" is exactly the feedback I
want. You know what real deliverables look like; I don't.

## Track B — optional, if you're curious (talk to it in Claude)

If you install the plugin per `INSTALL.md`, try prompts like these — just
type them:

1. *"Inspect the file 06_electrical_room_from_your_IFC.rvt and tell me what's
   in it — levels, walls, equipment, families."*
2. *"List every panelboard in this file with its voltage, phases, bus rating
   and what feeds it."*
3. *"Generate the panel schedule table for LP-1."*
4. *"Move DP-1 three feet along the wall and save it as a new file."*
5. *"Delete LP-4 from the room, including anything hosted to it."*
6. *"Rename panel LP-2 to LP-2A and set its mark accordingly."*
7. *"I need an electrical room, 30 by 20 ft, rated for 2500 A service, with a
   main switchboard, two 400 A distribution panels and four lighting panels —
   build it."* — this now runs **entirely on your machine**: it generates the
   equipment families, builds the room and hands you the `.rvt` file(s) plus
   a manifest of what it made. (It will ask your Revit version first — see
   the zeroth question; on 2025 it also writes an IFC you can link today.)
8. *"Validate 05_electrical_room_COMBINED_experimental.rvt and tell me exactly
   what's wrong with it."*

## Three caveats

- Everything's stamped **PROOF-ONLY** — research output, **not** for a real
  job or a real submittal yet. Legal review of the format/IP questions is
  underway; the name isn't final either. (Creating native `.rvt` files now
  works fully standalone on your machine — the PROOF-ONLY stamp is about
  legal review and provenance disclosure, not about capability.)
- **Versions:** everything tekton creates today targets **Revit 2026**;
  the **Revit 2025** path is in certification. If you tell it you're on
  2025 it says so plainly and adds a version-agnostic IFC beside the build
  rather than pretending.
- Please keep it to yourself for now — don't forward the kit. Happy to demo
  live if easier.

Really appreciate it. Even "file 02 opened fine, file 05 threw error X" is a
big result for me.

— C
