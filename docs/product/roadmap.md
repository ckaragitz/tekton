# Business roadmap — from family tool to real business

Companion to `docs/product/architecture.md` (the technical productization
plan). This file is the *business* path: phases, go/no-go gates, tiers,
who we sell to, and what the current family beta must teach us. Living
document; the orchestrator updates it as gates are passed.

## The one-line thesis

We turn Claude into a Revit-fluent teammate for people who make models
and drawings but aren't Revit power-users: describe or sketch it in Claude
→ get a file that opens *and behaves* in Revit. Nobody sells the bridge;
Autodesk sells the destination. The moat is (1) hard-won `.rvt` format
knowledge nobody else has and (2) SOPs that make the AI reliable at a
task that's normally fiddly and manual.

## Track A — NOW: family beta (skill-with-scripts, on-machine)

Ship exactly what we're building: the `revit-bridge` skill with bundled
scripts, running in the brothers' Cowork sandbox / on their machine. No IP
protection needed with family. **This is not a detour from the business —
it is the cheapest possible market test.** Everything they use is the future
paid engine wearing a free wrapper.

What the beta MUST measure (each is a business assumption to de-risk):
- **Willingness signal:** would they pay, and roughly what per month or
  per project? Ask directly once it saves them real time.
- **Time saved per deliverable** vs their manual workflow — the ROI number
  every future sales conversation needs.
- **Where "editable" actually matters:** which Tier-1 (clean IFC) results
  are good enough vs where they hit the Tier-2 wall (native MEP families /
  circuits). This decides whether the paid product needs `.rvt`/APS at all,
  or whether IFC tiers alone are a business.
- **Failure log:** every time the output disappoints in Revit → the product
  backlog. Frequency of each failure = its priority.
- **The Revit-version reality** across their firm/clients (target ceiling).

**Gate A→B:** the brothers use it for real work unprompted for ~a month
AND say they'd pay. If they abandon it, we learn why for near-zero cost —
before writing a line of licensing/billing code.

## Track B — DESIGN PARTNERS (2–5 external firms, still hand-held)

First strangers. Still on the on-machine script version is fine at this
size (light NDA/terms, no self-serve). Purpose: prove the value transfers
beyond family, find the repeatable use case, and pressure-test onboarding
without us in the room. Charge *something* (even token) — free tools get
no honest feedback.

Deliverables before entering: onboarding SOP a stranger can follow, the
delivery-report format (Tier 1 / Tier 2 framing), a support channel.

**Gate B→C:** ≥2 partners renew/keep using it after 60 days; a named use
case that repeats across firms; a price point at least one partner accepted.

## Track C — COMMERCIAL v1 (protected engine, self-serve)

Execute `docs/product/architecture.md`: lift the engine behind a Remote
MCP server (OAuth, per-seat entitlement, metering, signed-URL file
transport); ship the plugin (skills + hooks + agent templates + connector).
Engine and format knowledge never leave our servers.

Tier hypothesis (validate against Track A/B data before committing):
- **Free usage tier (funnel):** limited conversions/month of the same
  server-side product; SOPs are the readable knowledge layer. NOT open-core
  (user decision: no conversion logic ever runs client-side).
- **Pro (per-seat):** validate + harden + spec→IFC generation, delivery
  reports, Revit-fidelity linting.
- **Team / firm:** shared standards (company tagging library, house family
  conventions, shared-parameter sets), usage across projects, priority
  support.
- **Premium / `.rvt` (later, Track D):** native `.rvt` output via APS
  orchestration; deep `.rvt` inspection ("what's in this Revit file").
  Legal review REQUIRED before selling any `.rvt`-write capability.

**Gate C:** unit economics work (hosting + APS pass-through vs price),
churn acceptable, one repeatable acquisition channel.

## Track D — `.rvt` premium & the reader moat (research-gated)

Commercial `.rvt` output via **APS Design Automation** (sanctioned, no
reverse-engineered writer shipped). Our reverse-engineering becomes the
**read-side moat**: validation, inspection, diffing, extraction from `.rvt`
— safer legally and unique in the market. Native writer stays research
until the ECC gate is solved AND counsel signs off.

## Ideal customer profile (hypothesis — Track A/B must confirm or replace)

- Small MEP / electrical contractors and specialty subs producing shop
  drawings, submittals, coordination models — Revit is demanded of them
  (by GCs/owners) but they aren't Revit-native. **The brothers are the
  archetype.** High pain, low Revit fluency, project-based buying.
- Adjacent: small architecture/interiors studios prototyping in AI tools
  and needing a Revit handoff; BIM coordinators cleaning inbound IFC.
- Anti-ICP: large firms with in-house BIM teams and Dynamo scripts — they
  don't feel the pain.

## Moats, ranked by durability

1. `.rvt` format knowledge base + reader (years of RE, not googleable).
2. SOP corpus: what makes AI-authored geometry survive Revit import
   (Tier-1 rules, fidelity linter) — accumulates with every failure log.
3. Distribution inside Claude (plugin) — low switching once installed.
4. All conversion logic stays server-side (decided; not open-core), so
   the exporter algorithms remain private — reference impl in the beta
   skill gets ported server-side.

## Risks to watch

- **Platform:** Autodesk ships an official "AI to Revit" import, or Claude
  ships native IFC/Revit handling. Mitigation: the fidelity/SOP layer and
  read-side depth compound; move fast during the beta.
- **Legal:** `.rvt` writing (mitigate via APS route + counsel); Autodesk
  EULA on RE — reading for interoperability is defensible; document it.
- **Version treadmill:** every Revit release changes the schema. Mitigation:
  our grammar is release-independent; capturing a new release's schema is
  a repeatable, cheap task (need one sample file per release).
- **Market size:** may be a niche tool (great small business) not a venture
  business — decide which we're building; both are valid, they differ in
  how much we spend on Track C infra.

## Immediate business to-dos (cheap, do during Track A)

- Keep the failure log and the time-saved numbers from day one of the beta.
- Draft the delivery-report format now (it doubles as the sales artifact).
- Note every question a stranger would ask that the brothers didn't —
  that's the onboarding gap.
- Do NOT build billing, auth, or hosting until Gate A→B passes.
