#!/usr/bin/env python3
"""Regenerate Tekton-Eval-Kit-Instructions.pdf (reportlab).

Run from the repo root or this directory:

    .venv/bin/python tekton-eval-kit/_make_instructions_pdf.py

Underscore-prefixed files are EXCLUDED from tekton-eval-kit.zip by the kit
zip build (see docs/inbox/target-2025.md), so this generator never ships.
Keep the PDF in lockstep with EMAIL-DRAFT.md / REPORT-CARD.md / INSTALL.md:
the PDF is the merged, reviewer-facing rendering of those three.
"""
from __future__ import annotations

import os

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (Paragraph, SimpleDocTemplate, Spacer, Table,
                                TableStyle)

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "Tekton-Eval-Kit-Instructions.pdf")

SS = getSampleStyleSheet()
H1 = ParagraphStyle("H1x", parent=SS["Heading1"], fontSize=20, spaceAfter=2)
SUB = ParagraphStyle("SUBx", parent=SS["Normal"], fontSize=9,
                     textColor=colors.HexColor("#555555"), spaceAfter=10)
H2 = ParagraphStyle("H2x", parent=SS["Heading2"], fontSize=13, spaceBefore=12,
                    spaceAfter=4)
H3 = ParagraphStyle("H3x", parent=SS["Heading3"], fontSize=11, spaceBefore=8,
                    spaceAfter=3)
P = ParagraphStyle("Px", parent=SS["Normal"], fontSize=9.5, leading=13,
                   spaceAfter=6)
LI = ParagraphStyle("LIx", parent=P, leftIndent=14, bulletIndent=4)
BOX = ParagraphStyle("BOXx", parent=P, backColor=colors.HexColor("#FDF6E3"),
                     borderPadding=6, borderColor=colors.HexColor("#E0D5B8"),
                     borderWidth=0.5)
VBOX = ParagraphStyle("VBOXx", parent=P, backColor=colors.HexColor("#EAF2FB"),
                      borderPadding=6, borderColor=colors.HexColor("#B9D2EE"),
                      borderWidth=0.5)
CELL = ParagraphStyle("CELLx", parent=P, fontSize=8.5, leading=11, spaceAfter=0)
MONO = ParagraphStyle("MONOx", parent=CELL, fontName="Courier")

TBL = TableStyle([
    ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#CCCCCC")),
    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EFEFEF")),
    ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ("LEFTPADDING", (0, 0), (-1, -1), 5),
    ("RIGHTPADDING", (0, 0), (-1, -1), 5),
    ("TOPPADDING", (0, 0), (-1, -1), 4),
    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
])

FILES = [
    ("01", "01_genesis_project_base.rvt",
     "An empty project whose <b>entire setup we authored</b> — settings, styles, "
     "line weights, phases, levels, views, categories, materials. No Autodesk "
     "sample content.",
     "Does an “our own” project base open clean? Try Manage → Project "
     "Info / Phases / Object Styles — do the settings look sane?"),
    ("02", "02_created_room_shell_with_geometry.rvt",
     "Four <b>walls we created</b>, with their 3D geometry written by us. "
     "Autodesk's viewer draws them as a room shell.",
     "Do the walls appear immediately? Do they behave like real walls when you "
     "click and edit them?"),
    ("03", "03_electrical_room_shell_walls_only.rvt",
     "The electrical room's <b>shell</b> (walls only), generated <b>from a "
     "plain-English prompt</b>.",
     "Is the room outline correct?"),
    ("04", "04_electrical_room_equipment_families.rvt",
     "The room's <b>equipment</b>: our generated switchboard / panelboard / "
     "transformer <b>families</b>, placed.",
     "Do the panels appear? Click one — does it show PanelName / Voltage / "
     "BusRating properties?"),
    ("05", "05_electrical_room_COMBINED_experimental.rvt",
     "<b>KNOWN-EXPERIMENTAL:</b> shell + equipment in <b>one</b> file — a "
     "combination the cloud viewer currently rejects.",
     "Does real Revit ALSO reject it, or does it open? Either answer is very "
     "useful."),
    ("06", "06_electrical_room_from_your_IFC.rvt",
     "The 2500 A electrical room <b>built from the IFC you made</b> — MSB, "
     "distribution panels, lighting panels, transformer. Full circle.",
     "Are the boards and transformer roughly where the IFC had them?"),
    ("07", "07_constructed_layers_project.rvt",
     "A larger project where <b>63% of the elements are ours</b> (settings and "
     "styles plus a great deal more).",
     "Just: does a bigger one open and behave?"),
    ("08", "08_eaton_panelboard_family.rfa",
     "A <b>family file</b> we generated (Eaton Pow-R-Line PRL2X, 400 A, "
     "42-space).",
     "Open it in the <b>Family Editor</b> — does it open? Try <b>Load into "
     "Project</b> — does it place?"),
]

PROMPTS = [
    "“Inspect the file 06_electrical_room_from_your_IFC.rvt and tell me what's "
    "in it — levels, walls, equipment, families.”",
    "“List every panelboard in this file with its voltage, phases, bus rating "
    "and what feeds it.”",
    "“Generate the panel schedule table for LP-1.”",
    "“Move DP-1 three feet along the wall and save it as a new file.”",
    "“Delete LP-4 from the room, including anything hosted to it.”",
    "“Rename panel LP-2 to LP-2A and set its mark accordingly.”",
    "“Validate 05_electrical_room_COMBINED_experimental.rvt and tell me exactly "
    "what's wrong with it.”",
    "“I need an electrical room, 30 by 20 ft, rated for 2500 A service, with a "
    "main switchboard, two 400 A distribution panels and four lighting panels — "
    "build it.” (This now runs <b>entirely on your machine</b>: it generates the "
    "equipment families, builds the room and hands you the .rvt plus a manifest. "
    "It asks your Revit version first; on 2025 it also writes an IFC you can link "
    "today.)",
]


def build() -> str:
    doc = SimpleDocTemplate(OUT, pagesize=letter, leftMargin=0.9 * inch,
                            rightMargin=0.9 * inch, topMargin=0.8 * inch,
                            bottomMargin=0.8 * inch, title="tekton — Revit Eval Kit",
                            author="tekton")
    story = [
        Paragraph("tekton — Revit Eval Kit", H1),
        Paragraph("Instructions for the reviewer · Confidential · PROOF-ONLY "
                  "(not for real project use)", SUB),
        Paragraph(
            "Thank you for looking at this. <b>tekton</b> (a working name) is a tool "
            "that creates and edits Revit files <i>directly</i> — no Revit running, no "
            "Autodesk seat involved in producing them. You describe what you want in "
            "plain English, or feed it an IFC, and it produces the <font face='Courier'>.rvt</font>. "
            "Autodesk's own cloud viewer already opens and renders our output, including "
            "3D geometry for walls we author ourselves — and the whole pipeline now runs "
            "standalone on an ordinary machine.", P),
        Paragraph(
            "What we <i>cannot</i> test is what happens when someone hits <b>File → "
            "Open</b> on these files in real desktop Revit. That is the whole point of "
            "this kit — and you would be the first person to do it. Honest notes are far "
            "more useful than kind ones.", P),
        Paragraph(
            "<b>Please treat everything here as confidential and don't forward it.</b> "
            "The files are stamped PROOF-ONLY (research output, not for a real job or "
            "submittal) until a legal review of the format questions is finished. The "
            "product name isn't final either.", BOX),
        Spacer(1, 6),
        Paragraph(
            "<b>Zeroth question — which Revit version do you run?</b> Every file in this "
            "kit is <b>Revit 2026 format</b>, and Revit only opens files from its own "
            "release or older — <b>Revit 2025 or older will refuse them</b> (usually a "
            "“created in a later version” dialog). If that's you: the exact dialog text "
            "is still a useful data point (please copy it), and a <b>Revit-2025-native "
            "kit is in certification now</b> — you'll get it the moment it passes. A "
            "Revit 2026 seat (a trial counts) unlocks Track A today.", VBOX),
        Paragraph("What's in the kit", H2),
    ]
    kit = [
        [Paragraph("<b>TEST-KIT/</b>", CELL),
         Paragraph("Eight files — seven <font face='Courier'>.rvt</font> projects and one "
                   "<font face='Courier'>.rfa</font> family. <b>The main ask.</b> Every one was "
                   "generated by our software, never opened by Revit.", CELL)],
        [Paragraph("<b>REPORT-CARD.md</b>", CELL),
         Paragraph("The short per-file checklist (same table as below).", CELL)],
        [Paragraph("<b>Tekton-Eval-Kit-Instructions.pdf</b>", CELL),
         Paragraph("This document.", CELL)],
        [Paragraph("<b>tekton-plugin/ + INSTALL.md</b>", CELL),
         Paragraph("Optional (Track B) — the Claude Code plugin folder (already unpacked), "
                   "if you want to talk to the tool directly.", CELL)],
    ]
    t = Table(kit, colWidths=[2.1 * inch, 4.6 * inch])
    t.setStyle(TBL)
    story += [t]

    story += [
        Paragraph("Track A — the main ask (Revit 2026, about 30 minutes)", H2),
        Paragraph("Open each file in <font face='Courier'>TEST-KIT/</font> in Revit. For "
                  "<b>each</b> one, please jot down:", P),
    ]
    for i, q in enumerate([
            "<b>Did it open?</b> Yes / opened with warnings / refused — copy the exact "
            "text of any dialog.",
            "<b>Warnings on open?</b> Revit's Review Warnings list — a screenshot or a "
            "count is fine.",
            "<b>Does the model look right?</b> Walls and equipment where you'd expect, "
            "or missing/invisible?",
            "<b>Can you edit and save?</b> Move something, Save-As, reopen — does it "
            "survive?",
            "Anything Revit “fixes” or complains about — regeneration, upgrade "
            "prompts, and so on."], start=1):
        story.append(Paragraph(f"{i}&nbsp;&nbsp;{q}", LI))
    story.append(Paragraph("<b>Screenshots are gold. So is the exact text of any "
                           "error.</b>", P))
    story.append(Paragraph("The files", H3))
    rows = [[Paragraph("<b>#</b>", CELL), Paragraph("<b>File</b>", CELL),
             Paragraph("<b>What it is</b>", CELL),
             Paragraph("<b>The one thing to check</b>", CELL)]]
    for n, f, what, check in FILES:
        rows.append([Paragraph(f"<b>{n}</b>", CELL), Paragraph(f, MONO),
                     Paragraph(what, CELL), Paragraph(check, CELL)])
    t = Table(rows, colWidths=[0.32 * inch, 1.75 * inch, 2.5 * inch, 2.13 * inch],
              repeatRows=1)
    t.setStyle(TBL)
    story += [t, Spacer(1, 6)]
    story += [
        Paragraph(
            "<b>The most interesting ones:</b> <b>02</b> (walls we created — do they "
            "show and act real?), <b>04</b> (our generated families and their "
            "properties), <b>05</b> (flagged experimental on purpose — I <i>expect</i> "
            "Revit may reject it; either result tells me something), <b>06</b> (your "
            "IFC come to life), and <b>08</b> (does the Family Editor accept a family "
            "we wrote from scratch).", P),
        Paragraph(
            "Brutal honesty please — “this dialog popped up,” “these walls are the "
            "wrong type,” “no engineer would accept this because ___” is exactly what "
            "I'm after. You know what real deliverables look like; I don't.", P),
    ]

    story += [
        Paragraph("Track B — optional: talk to it through Claude", H2),
        Paragraph("You do <b>not</b> need this to test the files — Track A is the main "
                  "ask. But if you're curious, the plugin lets you drive tekton in "
                  "plain English.", P),
        Paragraph("What you need", H3),
        Paragraph("• <b>Claude Code</b> (Anthropic's command-line assistant) — "
                  "https://claude.com/product/claude-code (a Claude account; the Pro "
                  "plan works).", LI),
        Paragraph("• <b>Python 3.10 or newer</b> on your machine (type "
                  "<font face='Courier'>python3 --version</font> in a terminal to check).", LI),
        Paragraph("• The <font face='Courier'>tekton-plugin/</font> folder from this kit "
                  "(already unpacked — no unzipping).", LI),
        Paragraph("Load it", H3),
        Paragraph("1. Copy the <font face='Courier'>tekton-plugin/</font> folder somewhere "
                  "handy, e.g. your Desktop.", LI),
        Paragraph("2. Open a terminal and start Claude Code with the plugin loaded:", LI),
        Paragraph("<font face='Courier'>claude --plugin-dir ~/Desktop/tekton-plugin</font>",
                  ParagraphStyle("code", parent=LI, backColor=colors.HexColor("#F2F2F2"),
                                 borderPadding=4, leftIndent=24)),
        Paragraph("3. On first run Claude may ask to set up the Python environment for "
                  "the plugin's tools — say yes.", LI),
        Paragraph("That's it. Now just type requests in plain English. The plugin's "
                  "skills — <b>tekton-author</b>, <b>tekton-edit</b>, "
                  "<b>tekton-inspect</b> — kick in automatically based on what you ask.", P),
        Paragraph("Prompts to try — just type them", H3),
    ]
    for i, pr in enumerate(PROMPTS, start=1):
        story.append(Paragraph(f"{i}&nbsp;&nbsp;{pr}", LI))
    story += [
        Paragraph("What works on your machine (honest boundary)", H3),
        Paragraph(
            "<b>Everything runs standalone now</b> — including the part that used to "
            "need our lab: <b>creating a brand-new native .rvt from a prompt or an IFC "
            "works entirely on your machine.</b> Every build input ships inside the "
            "plugin (our own certified project base — no Autodesk content, no donor "
            "file, no internet). Also standalone: inspecting and validating any .rvt "
            "(including all the test-kit files), listing panels and their properties, "
            "panel-schedule tables, and editing an existing file (move / rename / "
            "delete). The old “specimen ancestor not found” stop is gone.", P),
        Paragraph(
            "<b>The one honest caveat is the Revit version.</b> Files tekton creates "
            "today are <b>Revit 2026 format</b>; the <b>Revit-2025-native path is in "
            "certification</b>. Tell it you run 2025 and it still builds, says so in "
            "one clear line, and writes an <b>IFC of the same design</b> beside the "
            ".rvt — any Revit can link/import that IFC today.", P),
        Paragraph("Three caveats", H2),
        Paragraph("• Everything is stamped <b>PROOF-ONLY</b> — research output, "
                  "<b>not</b> for a real job or a real submittal. Legal review of the "
                  "format questions is underway; the name isn't final. (Native .rvt "
                  "creation itself now works fully standalone — the stamp is about "
                  "legal review and provenance disclosure, not capability.)", LI),
        Paragraph("• <b>Versions:</b> outputs target <b>Revit 2026</b> today; "
                  "<b>Revit 2025</b> is in certification. On a 2025 target the tool "
                  "says so plainly and adds a version-agnostic IFC — it never "
                  "pretends.", LI),
        Paragraph("• Please keep it to yourself for now — don't forward the kit. "
                  "Happy to demo live if that's easier.", LI),
        Spacer(1, 4),
        Paragraph("Really appreciate it. Even “file 02 opened fine, file 05 threw "
                  "error X” is a big result for me. — C", P),
    ]
    doc.build(story)
    return OUT


if __name__ == "__main__":
    print(build())
