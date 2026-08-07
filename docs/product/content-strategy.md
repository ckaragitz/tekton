# rev-revit — Content Sourcing Strategy (Model Content, Templates, Standards)

Status: DEFINITIVE STRATEGY, second synthesis pass — 2026-08-03. Supersedes the earlier draft in this
file; it now incorporates the electrical-distribution manufacturer lens, the adversarial verification
pass over the lighting / aggregator / government lenses, and the internal completeness critique in
`docs/inbox/content-research.md`.

**This is not legal advice.** Every "may we" answer is FOUND-IN-TERMS (a clause we located and can
quote, with a URL), INFERRED (our reading, flagged), or UNKNOWN (silence — and silence is never
permission). Operationally, every UNKNOWN in the BUNDLE and EMBED columns is treated as **NO** until a
lawyer or a written license says otherwise. Items marked NEEDS COUNSEL must be cleared before they
gate a shipped feature.

Constraint driving this document (unchanged): we will not export a template or families from any
customer's Revit, and we must not ship, bundle, or embed Autodesk's own sample projects or
Autodesk-authored family content. The .rvt is the deliverable, so anything loaded into it is
*embedded and shipped with it* — a Revit project stores a full copy of every family it references.

---

## 1. EXECUTIVE VERDICT

**Question:** Can we lawfully populate customer deliverables with electrical-distribution and
lighting content without a customer-exported seed and without Autodesk sample content? What is the
primary source stack?

**Verdict: not by using anyone else's model geometry — but yes, conditionally, by generating our
own.** The condition is that two foundational, non-content risks are cleared first (the format-layer
posture in §5.1 and the product name in §5.3) and that the shipping pipeline is actually moved off
Autodesk sample seeds (see the reality check below).

Across three vendor lenses and a government lens — now covering the eight electrical-distribution
majors (Eaton, Schneider Electric, Siemens, ABB, Legrand, Hubbell, Emerson/Appleton, nVent), nine
lighting brands (Acuity, Cooper, Genlyte, Cree, Current/HLI, Focal Point, Finelite, USAI, RAB),
seven aggregators (BIMobject, BIMsmith, ARCAT, CADdetails, NBS, MEPcontent, community sites), and the
federal / owner-agency libraries (USACE, VA, GSA, NAVFAC, PANYNJ, etc.) — the adversarial verification
found **no license, from any source, that grants a software vendor the right to harvest, bundle,
redistribute, or server-side embed third-party family (.rfa) content in a paying customer's
deliverable.** Every located grant is scoped to a personal / non-commercial user or to a design
professional's *own* project, and the redistribution / derivative-work / third-party-service
prohibitions are express in most terms
([Cree](https://www.creelighting.com/terms-of-use/),
[Focal Point](https://www.focalpointlights.com/terms-use),
[nVent §5](https://www.nvent.com/en-us/terms-use),
[Siemens §4.4](https://www.siemens.com/en-us/terms-of-use/),
[ABB](https://new.abb.com/provider-information),
[BIMobject §4.7(f)–(g)](https://business.bimobject.com/terms-of-service-eula/),
[ARCAT](https://www.arcat.com/terms),
[CADdetails §5.3](https://www.caddetails.com/Content/PDF/TermsOfUse.pdf)).
The single most important structural finding of the electrical pass is that **nearly every website
ToU defers to a per-download license nobody has opened** — Eaton "Unless otherwise specified,"
Legrand "materials … with their own license terms … will be governed by such terms," nVent "unless
otherwise stated under specific terms and conditions," Siemens §4.1 (separately-agreed license
terms prevail and switch off §§4.2–4.5), Cooper §8 "Except as set forth in the applicable license
agreement." So the honest state of the vendor cells is not "non-commercial only, settled" but
"restrictive default, operative EULA UNREAD — UNKNOWN — NEEDS COUNSEL."

Therefore the lawful architecture is:

1. **GENERATE-OUR-OWN parametric families (primary).** Author every family ourselves — our
   geometry, our type catalogs, our formulas — and drive it with *facts* (dimensions, breaker frame
   sizes, bus ratings, kVA, lumen/wattage, catalog numbers, NEMA/UL classes) read from published
   spec sheets. Facts are not copyrightable ([Feist v. Rural, 499 U.S. 340](https://supreme.justia.com/cases/federal/us/499/340/) — INFERRED as applied to product geometry; see §5.5 for the limits, including design-patent/trade-dress questions Feist does not answer). We own what we author, so USE / BUNDLE / EMBED are clear for our own output.
2. **DOWNLOAD-ON-DEMAND by the end user (secondary).** When a spec demands the manufacturer's
   *actual* family, the **customer** — a design professional on their own project — pulls the .rfa
   through the manufacturer's or aggregator's own sanctioned interface inside their own Revit seat,
   the one use every term contemplates ([BIMobject §4.4(c)](https://business.bimobject.com/terms-of-service-eula/)).
   We never touch, host, or transmit the bytes. **Status: UNKNOWN — NEEDS COUNSEL**, not "clear" —
   every EULA is *silent* on an automated tool that generates the placeholder, produces the
   procurement manifest, drives the download, and remaps the file, and this document's own rule is
   that silence is not permission (see §3 Tier B and §5.2).
3. **OPEN / GOVERNMENT STANDARDS as the schema-and-defaults layer, never as geometry.** IFC
   (CC BY-ND 4.0), COBie / NBIMS-US (implementation license), bSDD dictionaries per each dictionary's
   declared license, IES TM-32/TM-33 parameter naming, GSA public-domain guide text, GLDF (MIT
   schema) for photometry interchange.

**Recommended primary source stack:** our own parametric family generator + manufacturer-published
*facts* (never their .rfa, drawings, or prose) + IES/GLDF photometry *referenced by the customer,
not redistributed by us* + IFC/COBie/TM-32/bSDD for schema. Manufacturer .rfa enters a deliverable
**only** through the customer's own download-on-demand act — and only after §5.2 clears the
automation boundary. Written manufacturer licenses (Tier C) are the growth path that converts
UNKNOWN/NO cells to YES.

**Reality check the verdict is conditional on (from `docs/inbox/seed.md` and
`docs/legal/provenance-memo.md`):**
- The **current** pipeline seeds jobs from **Autodesk's own sample projects**
  (`rmebasicsampleproject.rvt`, `rstbasic`, `racbasic`) and resolves/clones the Autodesk-authored
  family symbols in them (rme: 187/187) into deliverables. That is exactly the "ship/embed Autodesk
  sample content" prohibition. **Tier A is an aspiration until the genesis path writes a
  family-free file that our own masters populate.** Set an explicit cutover gate: no Tier-A claim,
  and no shipped deliverable, may carry any Autodesk-authored family. This is the highest-priority
  content risk in the product and is entirely operational.
- The format knowledge behind the writer was partly confirmed by analyzing Autodesk's
  `Utility.dll` (now quarantined out of the repo, with an independent mathematical re-derivation
  documented) — see §5.1. The privity question is a *fact to reconstruct*, not a hypothetical.

Two foundational risks sit above every content row and are NEEDS COUNSEL before launch:
**(a) the .rvt format / reverse-engineering posture (§5.1)** and **(b) the name "rev-revit" (§5.3).**

---

## 2. THE THREE-QUESTION LICENSE MATRIX

Columns: **USE** = may we use it to produce a customer's deliverable · **BUNDLE** = may we
redistribute/ship it inside our product · **EMBED** = may it be embedded in the .rvt we output.
Each cell states its evidence class. Where terms are silent the cell is UNKNOWN and the operating
rule is **silence is not permission**; every UNKNOWN under BUNDLE/EMBED is operationally **NO**.
"NC" = non-commercial. Row groups: our own work · electrical majors · lighting · aggregators ·
Autodesk · government/owner · open standards · community.

| # | Source (URL) | USE in customer project | BUNDLE in our product | EMBED in output .rvt |
|---|---|---|---|---|
| 1 | **Our own generated families** (§6) | INFERRED yes — our own expression; facts free per [Feist](https://supreme.justia.com/cases/federal/us/499/340/). *Not* "low risk" until the design-patent/trade-dress + trademark-in-type-name + collection-legality screens in §5.4–§5.5 clear | INFERRED yes — we own the copyright | INFERRED yes; residual: mfr names/catalog numbers in family names → §5.4 |
| **Electrical distribution majors** | | | | |
| 2 | **Eaton** BIM models ([portal](https://www.eaton.com/us/en-us/support/business-resources/consultants-engineers/consultant---engineer-resources-for-medium-voltage-power---eaton/bim-models-and-drawings.html); [terms](https://www.eaton.com/us/en-us/company/policies-and-statements/terms-and-conditions.html)) | UNKNOWN — FOUND-IN-TERMS default is "Unless otherwise specified, all material on these sites may only be downloaded for personal non-commercial use"; the "unless otherwise specified" carve-out defers to in-ZIP EULAs **nobody has opened** — NEEDS COUNSEL + open the packages (Ohio law) | NO/UNKNOWN — FOUND-IN-TERMS "COPYING OR REPRODUCTION OF THE SOFTWARE TO ANY OTHER SERVER OR LOCATION FOR FURTHER REPRODUCTION OR REDISTRIBUTION IS EXPRESSLY PROHIBITED" (clause scoped to "Software"; whether .rfa is Software or "material" → counsel) | UNKNOWN — silent |
| 3 | **Schneider Electric / Square D** (LayoutFAST; [portal](https://www.se.com/us/en/work/support/resources-and-tools/cad-drawings/); [ToU](https://www.se.com/us/en/about-us/legal/terms-of-use/)) | UNKNOWN — site ToU (search-index corroborated only; live page 403s all clients) grants only a license "to consult" on an "as is" basis and bars reproduction beyond "personal, non-commercial use … without Schneider Electric's permission, given in writing"; the LayoutFAST/registration EULA is UNREAD | UNKNOWN → NO — "All other rights are reserved" | UNKNOWN — configurator EULA unread |
| 4 | **Siemens BIMPOWER** ([App Store listing](https://apps.autodesk.com/RVT/en/Detail/Index?id=7500015743078743753&appLang=en&os=Win64); [siemens.com ToU](https://www.siemens.com/en-us/terms-of-use/)) | UNKNOWN — §4.2 grants use "solely for its own business purposes … to the extent agreed, or … to the extent of the purpose intended by Siemens," **but §4.1 makes separately-agreed license terms (the App Store / BIMPOWER EULA) prevail and switches off §§4.2–4.5**; that EULA is UNREAD (German or Delaware law) | NO — §4.4: information/software "may not be distributed by the User to any third party at any time" | UNKNOWN — real tension between "own business purposes" grant and §4.4; resolve via the unread EULA |
| 5 | **ABB Electrification US** ([BIM files](https://electrification.us.abb.com/your-business/consulting-design-engineer/bimfile); [current terms](https://new.abb.com/provider-information)) | UNKNOWN — current terms grant nothing for commercial project use; a **legacy version of the same URL** (2025 archive) barred "commercial purposes" and limited use to "information purposes within an organization." **Which document governs the electrification download host is UNRESOLVED** | NO — current terms: "reproducing, distributing, modifying, or scraping … prohibited without prior written permission from ABB" | UNKNOWN — "modifying … prohibited" cuts against parameter editing |
| 6 | **Legrand North America** ([BIM models](https://www.legrand.us/resources/bim-models); [terms](https://www.legrand.us/terms), last update 2011-03-16) | UNKNOWN — express grant is display of "the Web pages … solely on your computer and for your personal, non-commercial use," conditioned on "not modifying the content"; file-specific license carve-out unread | NO — distribution/derivative works need "LNA's prior written consent"; "may not mirror any of the content … on another Web site or in any other media" | UNKNOWN — no-modification condition vs. parametric editing |
| 7 | **Hubbell** ([technical resources](https://www.hubbell.com/wiringdevice-kellems/en/technical-resources); [web terms](https://www.hubbell.com/hubbell/en/web-terms), updated 2022-01-06) | UNKNOWN — grant: "download, display, print or reproduce the Hubbell Content in unaltered form for personal, non-commercial use, research or study"; tech info "may not be sold or distributed for commercial gain" | NO — may not "modify, copy, distribute or otherwise use the Website or Hubbell Content without our express permission" (Connecticut law) | UNKNOWN — "unaltered form" cuts against parameter changes |
| 8 | **Emerson / Appleton** ([PARTcommunity portal](https://emerson-appleton-e.partcommunity.com/3d-cad-models/appleton?info=appleton_group&languageIso=en&countryIso=US); [emerson.com ToU](https://www.emerson.com/en-us/terms-of-use)) | UNKNOWN — emerson.com: "provided for your personal information and non-commercial use"; **but the CAD/Revit exports are served by CADENAS PARTcommunity, whose own terms are unread and likely govern** | UNKNOWN → NO — Missouri law, arbitration; governing document unresolved | UNKNOWN |
| 9 | **nVent (CADDY/ERICO)** ([BIM library](https://www.nvent.com/en-us/building-information-modeling); [ToU §5](https://www.nvent.com/en-us/terms-use)) | UNKNOWN — download permitted "so long as such activity is for your own personal and non-commercial use (unless otherwise stated under specific terms and conditions)" — none located (Minnesota law) | NO — §5: no "reproduce, license, publish, distribute … create a derivative work" or incorporation "into any information retrieval system … without our express written authorization" | UNKNOWN — derivative-work + retrieval-system bans are broad |
| **Lighting manufacturers** | | | | |
| 10 | **Acuity Brands** (Lithonia/Peerless/Mark; [BIM downloads](https://www.acuitybrands.com/resources/technical-resources/bim-downloads); [site terms](https://www.acuitybrands.com/site-terms); [collateral policy](https://www.acuityinc.com/en/resources/our-newsroom/usage-policies/product-collateral-usage-policy)) | NO for us — site §6.1 "personal, non-commercial use"; collateral usable only "to promote, market and sell Acuity products … for the benefit of Acuity," "not … with a product or service of a company other than Acuity." (Whether .rfa/IES are "Product Materials" is definitional → counsel) | NO — §6.1: no reproduce/distribute/derivatives "except as expressly permitted"; the policy itself contemplates "Business partners who have agreements with Acuity" | UNKNOWN — silent |
| 11 | **Cooper Lighting / Signify** ([revit-files](https://www.cooperlighting.com/global/revit-files); [ToU](https://www.cooperlighting.com/global/terms-of-use), eff. 2020-07-20) | UNKNOWN — NO express content grant; §9 "All rights … not expressly granted herein are reserved" | NO — §8: software "for use by end users only and any further copying, reproduction or redistribution … is expressly prohibited," *"Except as set forth in the applicable license agreement"* (file EULA unread; .rfa = "software" or "Content" → counsel) | UNKNOWN — silent |
| 12 | **Genlyte / Signify NA** ([terms](https://www.genlyte.com/en-ca/terms-of-use), Jan 2019, Signify Netherlands B.V.; summarizer-read, verify verbatim) | UNKNOWN — same Signify template; no personal/NC grant either — all rights reserved | UNKNOWN → NO — same §8-style clause | UNKNOWN |
| 13 | **Cree Lighting** ([document library](https://www.creelighting.com/document-library/); [ToU](https://www.creelighting.com/terms-of-use/), Rev. Nov 2023) | NO — license only "for your own informational purposes and … business dealings with Cree Lighting"; marketing/selling "except as may be agreed … in writing" | NO — no "copy, reproduce, download, modify … republish or redistribute … for any purpose or in any medium" | UNKNOWN. Automated crawlers/scripts, harvesting, and deep-linking all expressly prohibited |
| 14 | **Current / HLI (Prescolite, Columbia)** ([BIM files](https://www.currentlighting.com/document-library/type/bim-files-4526); terms 301 → [led.com/terms](https://www.led.com/terms)) | NO — "personal and non-commercial use"; use "for purposes competitive to Current" prohibited. Entity mismatch (HLI site → Current Lighting Solutions terms) is a counsel question | NO — distribution/licensing/sale/derivatives "expressly prohibited"; license "revocable at any time" | UNKNOWN |
| 15 | **Focal Point** ([BIM library](https://www.focalpointlights.com/resources/bim-revit-library); [ToU](https://www.focalpointlights.com/terms-use)) | NO — "internal, personal, non-commercial purposes"; may not use "to develop, of as a component of, any information, storage and retrieval system … offered for commercial distribution of any kind" — directly on-point | NO — distribution, compilations, derivative works prohibited | UNKNOWN. Automated harvesting expressly prohibited ("any automatic or manual process to harvest information from the Site") |
| 16 | **Finelite** ([downloads](https://www.finelite.com/downloads)) — a **Legrand** brand | UNKNOWN — no site ToU; "© Finelite Inc., All rights reserved."; **parent Legrand's terms (row 6) may govern — unchecked** | UNKNOWN → NO | UNKNOWN |
| 17 | **USAI Lighting** ([revit files](https://www.usailighting.com/revit-files-for-our-recessed-and-surface-mount-light-fixtures)) | UNKNOWN — /terms-and-conditions 301s to /warranty; "All Rights Reserved"; the Revit Family User Guide PDF (may carry terms) is unread | UNKNOWN → NO | UNKNOWN |
| 18 | **RAB Lighting** ([IES](https://www.rablighting.com/ies); [/legal](https://www.rablighting.com/legal), summarizer-read) | NO — "You may not use, reproduce, distribute, transmit, or publicly display RAB Lighting Information for any commercial purpose, unless expressly authorized in writing"; "may not modify … in any way" | NO — the free IES ZIP is not a redistribution grant | UNKNOWN |
| **Aggregators / marketplaces** | | | | |
| 19 | **BIMobject / Bim.com** ([lighting](https://www.bimobject.com/en-us/categories/lighting); [EULA](https://business.bimobject.com/terms-of-service-eula/), eff. 2025-06-24; [API docs](https://github.com/bimobject/api-documentation) — no API terms found) | NO for us — §4.4(b) "solely for your own personal use (and not for any commercial purposes or to make a profit)"; §4.4(c) covers a professional party-to-the-project (the Tier B hook) | NO — §4.7(f)–(g): no distributing/sublicensing the Services or incorporating them "into a product or service you provide to a third party" (whether downloaded objects are "Services" → counsel, likely yes per §8.1) | UNKNOWN — §4.4(c) plausibly lets the *customer* embed what *they* downloaded; automated placement silent. **§4.7(j): no using Content to train/improve AI/ML/LLMs; §4.7(a): access only via Bim.com interfaces** — both bind our design directly |
| 20 | **BIMsmith Market** ([lighting](https://market.bimsmith.com/category/Lighting_revit); [terms](https://bimsmith.com/legal/terms-and-conditions)) | UNKNOWN — grant scoped to "use in Licensee's design process"; "may not sub-license its rights to any third party without written permission of the Licensor" | UNKNOWN → NO — §1.03 no-transmit/distribute is framed "with respect to the BIMsmith Site, or any part thereof"; downloaded-family redistribution technically silent; §1.02 pushes content questions to the **manufacturer** | UNKNOWN — §2.01 (licensee's own output is theirs) concerns assemblies the designer creates, not the mfr geometry |
| 21 | **ARCAT** ([BIM](https://www.arcat.com/content-type/bim); [terms](https://www.arcat.com/terms)) | NO for us — usable "only for the limited purpose of preparing construction specification, drawing and BIM documents" | NO — "shall not reproduce, adapt, distribute, display or publish 'Products' without ARCAT's explicit permission" | NO/AMBIGUOUS — "shall not use Website and/or 'Products' to create or provide content for third parties" is the clearest direct blocker in the corpus |
| 22 | **CADdetails** ([site](https://www.caddetails.com/); [ToU PDF](https://www.caddetails.com/Content/PDF/TermsOfUse.pdf)) | NO — §5.3 "not to use or resell Visions Products or services for any commercial purpose"; §5.2 no copy/download/use/store of Site Materials without written authorization | NO — §5.3 no download (beyond caching)/reproduce/sell "except with the express written consent of Visions" | UNKNOWN — INFERRED adverse; §11(i) bans crawl/scrape (Ontario law; legal@caddetails.com) |
| 23 | **NBS Source / National BIM Library** ([library](https://source.thenbs.com/en/gb/bimlibrary); [site terms](https://www.thenbs.com/terms-and-conditions)) | NO for us — "must not use any part of the content on our sites for commercial purposes without obtaining a licence"; operative Hubexo product terms and legacy NBL object-licence quotes UNVERIFIED | UNKNOWN → NO — likely restrictive; needs current Hubexo terms | UNKNOWN. Express anti-TDM: no "text or data mining or web scraping," no "robot, bot, spider, scraper" |
| 24 | **MEPcontent (Trimble/Stabiplan)** ([site](https://www.mepcontent.com/en/); footer → [Trimble Terms of Sale](https://www.trimble.com/Support/Terms_of_Sale.aspx)) | UNKNOWN — no content-specific license located; click-through at registration never retrieved | UNKNOWN → NO | UNKNOWN |
| **Autodesk** | | | | |
| 25 | **Autodesk OOTB families / templates / sample projects** ([content article](https://www.autodesk.com/support/technical/article/caas/sfdcarticles/sfdcarticles/Where-to-find-Revit-Content-Libraries-to-download.html); [legacy LSA](https://download.autodesk.com/global/dlm_eula/English.html); [General Terms](https://www.autodesk.com/company/terms-of-use/en/general-terms) — live page 403s, cached copy only) | NO — product constraint; we hold no license as a vendor to ship it | NO — legacy LSA §2.1.1 (verified verbatim): no license to "distribute, rent, loan, lease, sell, sublicense, transfer or otherwise provide all or any portion of the Autodesk Materials to any person or entity"; General Terms §8.1 wording cached/unverified live | **NO — and today's pipeline violates this** (Autodesk sample seeds; §1 reality check). Cutover gate required |
| **Government / owner content** | | | | |
| 26 | **USACE UBOL + USACE Revit templates** ([UBOL](https://cadbimcenter.erdc.dren.mil/ubol); [BIM/CIM](https://cadbimcenter.erdc.dren.mil/bim-cim/)) | UNKNOWN — **verified: no license/terms/copyright text anywhere on the site** (silence ≠ permission); stated purpose is internal USACE review; objects are district-submitted (contractor authorship possible); templates "built from the Revit Out-of-the-Box template" (Autodesk-derived) | UNKNOWN → NO — needs written ERDC position + per-object provenance | UNKNOWN → NO |
| 27 | **VA BIM Standard / TIL families & templates** ([bim.asp](https://www.cfm.va.gov/til/bim.asp) — TLS cert issues; [VA copyright policy](https://department.va.gov/copyright-policy/)) | Requirements text: FOUND-IN-TERMS "Government-produced materials appearing on this and other VA websites are not copyright protected." Files: UNKNOWN — same policy says the Government "may receive and hold copyrights transferred to it by assignment" (A/E deliverables), and authorship per file is unverified | UNKNOWN → NO for files | Requirements implementable; files UNKNOWN |
| 28 | **GSA PBS BIM Guides + "GSA Spatial Template"** ([policies](https://www.gsa.gov/website-information/website-policies); [Guide 07](https://www.gsa.gov/system/files/BIM_Guide_07_v_1.pdf)) | Guide text: FOUND-IN-TERMS "Works produced by federal government employees … are generally not protected by copyright and are in the public domain in the U.S." — but "You should determine for yourself whether or not an item is protected by copyright"; protected items need "written permission." Spatial Template: NO (derived from an Autodesk-created test model) | Text YES per-item, third-party items excluded; Template NO | Text N/A; Template NO |
| 29 | **NAVFAC titleblocks/templates on WBDG (NIBS)** ([titleblocks-revit](https://www.wbdg.org/navy/cad/titleblocks-revit)) | UNKNOWN — WBDG is hosted by NIBS (a private nonprofit) which asserts site copyright; the Navy-authored files' status is separate and unverified; zips may embed OOTB content — NEEDS COUNSEL | UNKNOWN → NO | UNKNOWN |
| 30 | **State / port-authority owner templates** (PANYNJ [BIM Standard](https://www.panynj.gov/content/dam/port-authority/pdfs/-available-engineering-documents/BIM-Standard.pdf); Mass DCAMM; DEN; LAWA) | Project-restricted — the owner's own contract governs (e.g. PANYNJ mandates its templates for PA projects and asserts ownership of project models — verifier reported an express ownership clause). Usable only when the customer is executing that owner's project | UNKNOWN → NO for general bundling. Verifier reported Mass.gov's reuse policy as an affirmative permission for *state web content* — that does not clearly reach DCAMM's Revit template; verify the template's own terms | Only inside that owner's mandated template on that owner's project |
| **Open standards / schema (structure only, never geometry)** | | | | |
| 31 | **NBIMS-US v4 / COBie** ([license](https://www.nibs.org/nbims/user-license-agreement)) | YES — FOUND-IN-TERMS royalty-free license for the standard's intended implementation | RESTRICTED — no commercial sale/transfer of the standard's text; attribution; no modification | YES — COBie population is the intended use |
| 32 | **IFC (ISO 16739) / bSDD** ([IFC](https://www.buildingsmart.org/standards/bsi-standards/industry-foundation-classes/); [bSDD license page](https://technical.buildingsmart.org/services/bsdd/license/)) | YES — IFC CC BY-ND 4.0 (implement/export); bSDD "FREE for both accessing and publishing public content," and per-dictionary licenses declared in each dictionary (search-summary read; **verify per dictionary — default is rights-reserved**) | Schema unmodified: YES (ND). bSDD content: per each dictionary's declared license — INFERRED, verify | YES — exporting IFC / mapping to bSDD classes is the intended use |
| 33 | **BIMForum LOD Specification** ([resource](https://bimforum.org/resource/lod-level-of-development-lod-specification/)) | Cite/link the spec: YES. Reproduce text: NO — CC BY-NC-ND 4.0 (non-commercial, no derivatives) per the spec's own front matter ([Part I 2024](https://bimforum.org/wp-content/uploads/2024/11/LOD-Spec-2024-Part-I-official-English.pdf)); **the verifier reported a correction regarding the Part II license that was not received in full — re-verify Part I vs Part II before relying on either** | NO — NC forbids bundling in a paid product | N/A — LOD is a contractual target our model must satisfy |
| 34 | **Penn State BIM Execution Planning guide/template** ([guide](https://psu.pb.unizin.org/bimprojectexecutionplanning/)) | YES — CC BY-SA 4.0, commercial OK with attribution ("except where otherwise noted" — check the template file) | YES with attribution + share-alike | A generated BEP is a CC BY-SA derivative doc, separate from the .rvt |
| 35 | **ANSI/IES TM-32-24 / TM-33 / LM-63 (parameters & photometry format)** ([TM-32](https://webstore.ansi.org/standards/iesna/ansiiestm3224); [LM-63-19](https://webstore.ansi.org/standards/iesna/ANSIIESLM6319)) | INFERRED yes to *implement* the parameter names / file format — **the webstore purchase license was never read; every permission here is INFERRED, not FOUND-IN-TERMS** | NO for the standards' text; the reported TM-32 GUID/Excel companion's redistributability is UNKNOWN | TM-32-conformant parameter *names* in our own families: INFERRED intended use |
| 36 | **GLDF photometric container** ([gldf.io](https://gldf.io/); XSD MIT on [GitHub](https://github.com/globallightingdata/gldf)) | YES — open spec; XSD MIT (verify verbatim) | YES for the format/schema; NOT for any mfr's data payload | Format YES; payload carries the mfr's rights |
| 37 | **CSI MasterFormat / UniFormat / OmniClass** ([licensing](https://theconstructionstandard.com/license-masterformat-construction-software)) | UNKNOWN — licensor asserts platform / revenue-generating use requires a paid license; agencies mandate these classifications — a licensing path, not avoidance (EULA unread) | UNKNOWN → LICENSE REQUIRED presumptively | Same — budget for the CSI license |
| **Community** | | | | |
| 38 | **RevitCity, revitfamiliesfree, GitHub .rfa dumps** ([RevitCity](https://www.revitcity.com/downloads.php)) | UNKNOWN — no locatable terms, unverifiable provenance | NO — indefensible | NO |

**Cross-cutting findings that survived adversarial verification.**
(1) No row grants a software vendor bundle/embed rights in third-party model geometry; every
discrepancy the verifier found made the picture *more* restrictive or more uncertain, never more
permissive. (2) The carve-outs are the story: the decisive documents — in-ZIP READMEs/EULAs (Eaton),
the LayoutFAST EULA (Schneider), the BIMPOWER/App-Store EULA (Siemens), CADENAS PARTcommunity terms
(Emerson), file-specific licenses under Cooper §8 and Legrand/nVent "unless otherwise stated" —
are **unread by anyone** and can only be read by a human downloading and opening the packages.
(3) API/automation is either silent or expressly banned everywhere: Cree, Focal Point, ABB (bots
sending more requests "than a human can reasonably produce"), Siemens (text/data mining and AI
training), NBS (TDM/scraping), CADdetails §11(i), BIMobject §4.7(a) and §4.7(j) (no AI/ML training
on Content). An AI-driven harvester is squarely in the crosshairs of these clauses.
(4) Rows 31–36 are the only affirmative licenses in the corpus, and they license *schema and
structure*, not geometry — the matrix points unambiguously at row 1.

---

## 3. RECOMMENDED CONTENT ARCHITECTURE

Reasoned from the matrix: BUNDLE/EMBED are NO or UNKNOWN for every third-party geometry source
and YES only for our own work (row 1) and open schemas (rows 31–36). So third-party bytes stay out
of our supply chain, full stop.

### Tier A — GENERATE-OUR-OWN parametric families (PRIMARY; the actual product)

- We author every family: geometry, type catalogs, parameters, formulas. Copyright is ours →
  USE/BUNDLE/EMBED clear (row 1), *conditional on* the geometry-IP and collection screens (§5.4–5.5).
- Geometry is driven by **facts** — enclosure H×W×D, breaker frame ratings, bus ampacity, kVA and
  impedance, lamp/lumen/wattage, catalog numbers, NEMA/UL/IP classes, connector counts and sizes —
  read from published cut sheets. We regenerate geometry from dimensions; we never trace their
  drawings, never paste their prose, never store their .rfa.
- Parameter naming conforms to open schemas: TM-32 for luminaires (row 35), COBie/NBIMS-US
  (row 31), IFC psets + bSDD where a dictionary's license permits (row 32).
- **Photometry: reference, don't redistribute — and even the reference is a counsel item.** We do
  not ship manufacturer .ies files (RAB, row 18, shows even "free" IES ZIPs are asserted against
  commercial use). The customer supplies the IES/GLDF they obtained; we set Revit's photometric-web
  parameter to it locally. Note the internal critique: several manufacturers bar *deep-linking or
  any commercial use* of their materials (Cree row 13, RAB row 18), so a link our commercial
  product writes into a deliverable is not automatically outside their terms — §5.2.
- Residual Tier A risk is **trademark and non-copyright IP in the names and shapes** (§5.4, §5.5),
  not copyright.

### Tier B — DOWNLOAD-ON-DEMAND BY THE END USER (SECONDARY — status UNKNOWN, NEEDS COUNSEL)

When a spec calls for the manufacturer's actual family: (1) we generate a dimensionally-correct
placeholder + a procurement manifest; (2) the **customer** downloads the .rfa through the
manufacturer's or aggregator's own interface inside their own Revit seat, as the professional on
their own project — the use BIMobject §4.4(c), BIMsmith §1.01, and ARCAT actually license
([BIMobject](https://business.bimobject.com/terms-of-service-eula/),
[BIMsmith](https://bimsmith.com/legal/terms-and-conditions), [ARCAT](https://www.arcat.com/terms));
(3) our tooling remaps types/parameters onto the customer-loaded family. We never possess or
transmit the bytes.

**Do not describe this as clear.** The EULAs are *silent* on a vendor tool that fabricates the
placeholder, generates the shopping list, drives the customer to the download, then auto-swaps the
file — and silence is not permission (this document's own rule). Open questions: is an *automated*
swap performed by our tool still the "professional's own" act; do harvesting/deep-linking bans
(Cree, Focal Point, ABB, CADdetails, NBS) reach a "here's the download page" feature; is there
inducement/contributory exposure. Gate every automated step on §5.2. Manufacturers with **no terms
at all** (Finelite row 16, USAI row 17) give the customer no license either — those need Tier C.

### Tier C — MANUFACTURER PARTNERSHIP / WRITTEN LICENSE (STRATEGIC; the only path to real .rfa)

Every manufacturer row ends in "except by written agreement / prior written consent" — Eaton
(EULA), Schneider ("permission, given in writing"), ABB ("prior written permission"), Legrand
("LNA's prior written consent"), Hubbell ("express permission"), nVent ("express written
authorization"), Cree, RAB, Acuity ("Business partners who have agreements with Acuity"). The
clean way to legitimately BUNDLE a real Eaton/Square D/Lithonia family is a distribution or
content-partner agreement — manufacturers *want* to be specified. Prioritize the brands our first
customers actually spec: **Eaton** (panelboards for the DDOT electrical rooms) and the plenum-rated
recessed-lighting brands.

### Tier D — GOVERNMENT / OPEN CONTENT (schema and defaults ONLY — see §4)

**Ranking:** Tier A (build now; ships once the sample-seed cutover gate is met) → Tier D
(structure, adopt now) → Tier B (enable, don't ship; gated on §5.2) → Tier C (business
development, unlocks real .rfa over time). **Explicitly rejected:** harvesting aggregators or
manufacturer portals, seeding from any customer's Revit, shipping Autodesk sample/OOTB content
(the current pipeline — must be retired), treating UBOL/community libraries as free seed, and
scraping/AI-training on any aggregator's Content (expressly banned by BIMobject §4.7(j)).

---

## 4. GOVERNMENT / PUBLIC CONTENT WE CAN ADOPT AS A DEFAULT BASE

The premise "US federal works are public domain, so government BIM libraries are free seed"
is **refuted for model content** and **holds only for federal-employee-authored TEXT, verified per
item.** Adoptable vs. not:

**Adopt (with the stated basis):**
- **GSA PBS BIM Guide text** — public-domain federal-employee work, per-item verification
  required, protected third-party items excluded ([GSA policies](https://www.gsa.gov/website-information/website-policies)).
  Requirements/structure only, never geometry.
- **VA BIM Manual requirements** (COBie, LOD, rooms/areas) — implementable as procedures; VA site
  materials "not copyright protected," but note the Government may hold **assigned** copyrights, so
  VA-hosted *files* are not automatically free ([VA policy](https://department.va.gov/copyright-policy/)).
- **NBIMS-US v4 / COBie** — implement under the NIBS license with attribution (row 31).
- **IFC / bSDD** — export IFC (CC BY-ND 4.0); consume bSDD dictionaries per each one's declared
  license, remembering bSDD's stated grant for commercial BIM use is per-dictionary and defaults
  restrictive (row 32).
- **Penn State BEP guide/template** — CC BY-SA 4.0, commercial OK with attribution + share-alike (row 34).
- **Owner-mandated templates** (PANYNJ, DCAMM, DEN, LAWA) — usable **only** to produce that owner's
  own deliverable in its mandated template, with the customer as contracting party (row 30). Not a
  general default; PANYNJ additionally asserts ownership of project models (verifier-reported).

**Do NOT adopt as bundled content:**
- **USACE UBOL / USACE templates** — verified: no license anywhere on the site; stated purpose is
  internal USACE review; district/contractor-submitted (copyrightable) objects; templates
  Autodesk-OOTB-derived ([UBOL](https://cadbimcenter.erdc.dren.mil/ubol),
  [BIM/CIM](https://cadbimcenter.erdc.dren.mil/bim-cim/)). Reference lead only; a usable subset needs
  per-object provenance + a written ERDC position — NEEDS COUNSEL.
- **VA family/template files** — government ownership of an assigned copyright ≠ public domain.
- **GSA Spatial Template** — derived from an Autodesk-created test model; excluded by our
  no-Autodesk-content constraint.
- **NAVFAC/WBDG zips, SEPS2BIM, community libraries** — private-nonprofit host copyright (NIBS),
  per-contributor IP, no provenance.
- **BIMForum LOD Spec text** — non-commercial CC; cite it, never bundle it. (Part I vs Part II
  license discrepancy flagged for re-verification.)
- **CSI MasterFormat/UniFormat/OmniClass** — agencies require them and the licensor asserts a paid
  platform license ([licensing](https://theconstructionstandard.com/license-masterformat-construction-software)).
  Budget for the license; do not silently embed OmniClass Table 23 / MasterFormat keynotes. NEEDS
  COUNSEL to read the actual CSI EULA scope.

Rule for the whole tier: **government and standards bodies give us requirements, schema, and
public-domain prose — never a ready-made family library.**

---

## 5. LEGAL RISK MAP

**We are not counsel. Every rating is a triage priority for a lawyer, not a legal conclusion.**
Ratings HIGH / MED / LOW with sourced basis. The full factual record for §5.1 is
`docs/legal/provenance-memo.md` — hand counsel the memo, not hypotheticals.

### 5.1 The .rvt format / reverse-engineering posture — **HIGH (foundational)**

rev-revit reads and writes `.rvt` in pure Python with no Revit install, so we necessarily
implement a proprietary, undocumented format learned by analysis. This sits *above* every content
question. The relevant facts are documented, not hypothetical:

- **What was actually done** (`docs/legal/provenance-memo.md`): (1) publicly-obtained sample .rvt
  files were analyzed as data; (2) the stream page-checksum was first characterized empirically;
  (3) to *confirm* it, `Utility.dll` (Revit 2023.1.9) was extracted from Autodesk's public update
  package and its checksum routine analyzed — no Revit install, and to the operator's understanding
  no click-through license was accepted for the extracted DLL (**counsel to confirm the acquisition
  terms of the update package**); (4) the checksum was then **independently re-derived by pure
  mathematics** from the samples alone and validated byte-exact across Revit 2016–2026 files; the
  shipping code (`src/rvt/ecc.py`) is ours; (5) the DLL has been **removed from the repo and
  quarantined** (`docs/inbox/ecc-intel-Utility-2023_1_9.QUARANTINED.md`); (6) no Autodesk source
  code was accessed.
- **Contractual no-RE (EULA privity):** Autodesk's General Terms prohibit licensees from
  "decompiling, disassembling, or other reverse engineering, or otherwise attempting to discover …
  underlying algorithms or other internals, protocols, data structures … or the source code of the
  Offerings," qualified "except as expressly permitted under applicable law"
  ([General Terms](https://www.autodesk.com/company/terms-of-use/en/general-terms) — clause per
  search extracts; the live page 403s automated fetch, verify in a browser). Whether *anyone on the
  team is a bound licensee* is decisive: no Revit was installed for the RE work, but **if any
  engineer/QA seat runs licensed Revit to validate our output, the entity is a licensee** — the
  privity fact the memo asks counsel to confirm. Sample-file acquisition terms and the update-package
  terms both need reconstruction.
- **Statute:** 17 U.S.C. §1201(f) permits circumvention/analysis "for the sole purpose of
  identifying and analyzing those elements of the program that are necessary to achieve
  interoperability of an independently created computer program" ([§1201](https://www.law.cornell.edu/uscode/text/17/1201)).
  The internal critique correctly flags that this covers only the (f) defense: **counsel must also
  address the trafficking prongs §1201(a)(2)/(b)** — whether the CRCIO page-checksum/framing we
  reimplement is a "technological measure" and whether a writer that reproduces it is a
  circumvention *device*. That is the prong a plaintiff pleads.
- **Copyright in the format itself:** functional file structures generally get thin protection
  (Baker v. Selden / merger doctrine) — INFERRED, unsourced here; counsel question.
- **The sanctioned alternatives (candidates, terms UNREAD — do not rate as risk-collapsing until
  read):** (a) **Open Design Alliance BimRv SDK** reads/writes .rvt/.rfa without Autodesk software
  and permits commercial use under a Sustaining membership + BimRv module ([BimRv](https://www.opendesign.com/products/bimrv);
  [FAQ](https://www.opendesign.com/faq/bimrv)) — obtain the membership agreement and a quote, and
  understand ODA's own IP posture toward Autodesk before relying on it; (b) **Autodesk APS Automation
  API for Revit** — sanctioned, but binds us to Autodesk platform terms and per-job cost
  ([automation-apis](https://aps.autodesk.com/automation-apis)).

**Questions for counsel (5.1):** (a) Is our independently re-derived writer lawful under
copyright and §1201, given the documented provenance (including the DLL-confirmation step)?
(b) Does any Autodesk EULA bind any person/machine involved — reconstruct sample-file and
update-package acquisition terms, and the effect of any Revit seat used for QA? (c) Is a clean-room
re-implementation advisable now that a non-DLL derivation exists? (d) §1201(a)(2)/(b) trafficking:
is the page checksum/framing a "technological measure," and is the writer a circumvention device?
(e) Preservation vs. destruction of the quarantined DLL. (f) Read the ODA BimRv membership agreement
and APS Automation-API terms; cost/benefit of replacing our writer.

### 5.2 EULA privity, automation, and inducement across manufacturer/aggregator terms — **MED**

Every "NO" in rows 2–24 is a website/EULA term binding whoever downloads. In Tier A we download
nothing, so we may not be a party to those contracts — the customer is. The exposure is:
(a) our **fact-extraction pipeline** reads spec sheets from the same sites whose ToU bar automated
collection (Cree, Focal Point, ABB, Siemens TDM/AI clause, CADdetails §11(i), NBS, Acuity's
large-load clause) — "facts are free" (Feist) does **not** answer "may we lawfully collect them
from a site that bans automated collection"; default Pipeline 2 (§6) to manual entry per source
until each site's collection posture is recorded; (b) if we ever automate the customer's own
download, we walk into every automation/harvesting ban directly; (c) **inducement / contributory**
theories if our tool systematically routes customers past manufacturers' terms; (d) BIMobject
§4.7(j) forbids using Content to train or improve AI/ML/LLM systems — a hard constraint on any
learned component. **Questions for counsel:** what may the extraction pipeline collect, and how;
is enabling/automating a customer's own download inducement; what must the UX say and not do to
keep the customer as licensee-of-record.

### 5.3 Trademark: the name "rev-revit" — **HIGH (cheapest to eliminate)**

The product name incorporates Autodesk's registered mark **REVIT**. Autodesk's guidance permits
*referential* use — a trademark used "in a referential phrase to accurately indicate that your
product or service is for use with Autodesk's product" — but disfavors incorporating the mark into
your own product name, and asks that marks be used as adjectives with attribution
([Guidelines for Use](https://www.autodesk.com/company/legal-notices-trademarks/trademarks/guidelines-for-use);
[trademark list](https://www.autodesk.com/company/legal-notices-trademarks/trademarks)). A name
that is the mark plus a prefix, on a product that writes Revit files, is the highest-visibility
exposure and the first cease-and-desist. **Recommendation: rename before public launch** to a
non-derivative brand, keeping "for use with Autodesk® Revit®" as an attributed referential tagline;
register no domain containing "revit"; describe file compatibility factually (".rvt files that open
in Autodesk Revit"). **Questions for counsel:** clearance search for the new name; approved
compatibility/attribution language; whether "Revit-compatible" claims need Autodesk consent.

### 5.4 Trademark and marks inside our generated families — **MED**

Naming families/types by real manufacturer + catalog number is *likely* nominative fair use
(identifying the product the customer specified) — INFERRED, unsourced — but a full
vendor-branded content library is exactly where nominative use gets tested, and several
manufacturers police "competitive" and "commercial" use (Current/HLI, Cree, Siemens). Also
unassessed: **catalog numbers, "UL Listed"/NEMA/CSA marks inside generated types.** **Questions
for counsel:** approved naming convention (mfr names as parameter *values* vs. displayed family
names); disclaimers; which brands to approach for consent (feeds Tier C).

### 5.5 Copying expression / non-copyright IP while extracting facts — **MED**

Feist protects our use of *facts*, not the cut sheet's drawings, prose, or a catalog's original
selection/arrangement ([Feist](https://supreme.justia.com/cases/federal/us/499/340/)) — and Feist
is a **copyright** case: it says nothing about **design patents or trade dress in a fixture's or
enclosure's ornamental shape**, which a faithful parametric family could replicate. Our pipeline
regenerates geometry from dimensions (never traces/rasterizes their artwork), never stores their
copy, and models functional envelopes rather than ornamental styling. **Questions for counsel:**
fact/expression line for the ingestion pipeline; design-patent + trade-dress screen on the first
master-family equipment classes; compilation copyright in catalog selection/arrangement; UK/EU
database right if any source or customer is non-US (NBS is UK).

### 5.6 Classification-standard licensing (CSI) inside agency deliverables — **MED**

VA/agency deliverables require MasterFormat/OmniClass; the licensor claims platform use needs a
paid license ([licensing](https://theconstructionstandard.com/license-masterformat-construction-software)).
LOW dollars, MED because it is easy to violate silently. Read the CSI EULA and procure the license
before shipping classification-populated exports.

### 5.7 Contamination from "free" or sample seeds — **HIGH today, LOW once gated**

This is not hypothetical: the shipping pipeline currently mutates Autodesk sample projects carrying
187 Autodesk-authored family symbols into deliverables (§1). Add UBOL/ARCAT/community/OOTB content
quietly entering the library and the exposure is Autodesk- and third-party-copyrighted geometry in
every .rvt we ship. Mitigation is process: (1) an immediate **cutover gate** — no deliverable ships
while its element inventory contains any Autodesk-authored family; (2) a **provenance ledger** —
every family tagged "authored-in-house, generator version X, facts from source URL Y" — and a CI
gate rejecting any untagged .rfa. Drops to LOW only when Tier A generates everything.

---

## 6. THE FAMILY-GENERATION PATH (engineering)

Ranked pipelines, "lawful data source → our own generated family." (The dedicated
family-formats lens report was not present in this synthesis input; the pipelines are built from
the verified content findings plus the format-layer facts in §5.1. The choice of *format writer*
is the §5.1 counsel decision and is a dependency, not resolved here.)

**Pipeline 0 — the format layer (decide first; blocks everything).**
Choose with counsel and after reading the relevant terms: (a) our existing pure-Python writer,
whose checksum is now independently re-derived (keeps zero-Revit architecture; carries the §5.1
posture); (b) **ODA BimRv SDK** as the write engine (member-licensed .rfa/.rvt read/write path —
[BimRv](https://www.opendesign.com/products/bimrv)); or (c) **Autodesk APS Automation API for
Revit** to bake families in Autodesk's cloud
([automation-apis](https://aps.autodesk.com/automation-apis); e.g.
[aps-create-revit-family](https://github.com/autodesk-platform-services/aps-create-revit-family)),
trading independence for platform terms + per-job cost. Spike (b) in parallel with the legal review;
do not rate any option "safe" on unread terms.

**Pipeline 1 — Parametric master families, our authorship (BUILD FIRST after Pipeline 0).**
Hand-author, once, a small set of *parametric masters* whose geometry and formulas are 100% ours,
one per equipment class the first customers need: **panelboard, switchboard, dry-type
transformer, disconnect, enclosed breaker, ATS** (the DDOT electrical rooms) and **recessed troffer
2×2/2×4, plenum-rated recessed downlight/linear** (Chicago plenum), plus **conduit/EMT, cable tray,
strut/hangers, receptacles, switches**. Each exposes TM-32 / COBie / IFC-mapped parameters (rows
31, 32, 35). Output: our library — USE/BUNDLE/EMBED all clear. Run the §5.5 design-patent/
trade-dress screen on this list before it ships. **This is the deliverable-unblocking work and the
product's content moat.**

**Pipeline 2 — Fact-driven instantiation from manufacturer specs.**
A *catalog-facts store* (dimensions, ratings, catalog numbers, connector counts, kVA, lumens/watts)
keyed by manufacturer part number, populated from cut sheets as **facts** — never their drawings,
prose, or .rfa. A generator maps facts → Pipeline-1 master → typed family (mfr/catalog as
*parameter values*, naming convention pending §5.4). Every fact stores its source URL for the
provenance ledger. **Collection posture per source is recorded first** (§5.2): where a site bans
automated collection (Cree, Focal Point, ABB, Siemens, CADdetails, NBS), populate by hand or seek
written permission; **default is manual entry until then.**

**Pipeline 3 — Photometry by reference.**
Set Revit's photometric-web parameter to the IES (LM-63) or GLDF file the **customer** supplies;
validate client-side; never redistribute manufacturer photometry (row 18). Support GLDF as the
neutral container (row 36). Any auto-fetched or vendor-hosted link is gated on §5.2 (Cree/RAB
link and commercial-use clauses).

**Pipeline 4 — Placeholder → customer-loaded .rfa swap (Tier B enablement).**
Dimensionally-correct placeholder + procurement manifest; when the customer loads the real family
in their own Revit, our tooling remaps types/parameters onto it. We never fetch or transmit the
.rfa. Every automated step ships **only** after §5.2 answers land.

**Pipeline 5 — Standards / deliverable-metadata layer.**
COBie population (row 31), IFC export (row 32), LOD-target tracking against the customer's
contract (cite the spec, don't reproduce it — row 33), and — behind a procured CSI license —
MasterFormat/OmniClass tagging (row 37). Generated BEPs from the CC BY-SA Penn State template with
attribution (row 34).

**What engineering builds first (order):**
1. **Sample-seed cutover gate + provenance ledger + CI gate** (§5.7, §1) — immediate; cheap;
   prevents the catastrophic failure that is currently *live*.
2. **Pipeline 0 decision** — counsel + build/buy, unblocked by an ODA BimRv spike run in
   parallel with the legal review.
3. **Pipeline 1** — the ~12–15 parametric masters (electrical distribution first: panelboard,
   switchboard, transformer, disconnect, breaker, ATS; then plenum lighting).
4. **Pipeline 2** — catalog-facts store + generator, starting with the customers' real specs
   (Eaton Pow-R-Line panelboards, plenum-rated recessed lighting), manual-entry until each source's
   collection posture is recorded.
5. **Pipelines 3, 4, 5** — as the first deliverables demand them, Tier-B steps gated on §5.2.

---

## 7. SOURCE CATALOG (appendix)

Electrical distribution manufacturers:
- Eaton — portal https://www.eaton.com/us/en-us/support/business-resources/consultants-engineers/consultant---engineer-resources-for-medium-voltage-power---eaton/bim-models-and-drawings.html ; terms https://www.eaton.com/us/en-us/company/policies-and-statements/terms-and-conditions.html (verified via archived raw capture; live page blocks scripted clients)
- Schneider Electric / Square D — https://www.se.com/us/en/work/support/resources-and-tools/cad-drawings/ ; ToU https://www.se.com/us/en/about-us/legal/terms-of-use/ (blocked to non-browser clients; corroborated via index extracts only — live browser read owed)
- Siemens BIMPOWER — App Store https://apps.autodesk.com/RVT/en/Detail/Index?id=7500015743078743753&appLang=en&os=Win64 ; siemens.com ToU https://www.siemens.com/en-us/terms-of-use/ (verified live, last updated 2025-10-27)
- ABB Electrification US — https://electrification.us.abb.com/your-business/consulting-design-engineer/bimfile ; current terms https://new.abb.com/provider-information (verified live; NOTE version drift vs. legacy terms at same URL)
- Legrand North America — https://www.legrand.us/resources/bim-models ; terms https://www.legrand.us/terms (verified via 2025 archive capture; last update 2011-03-16)
- Hubbell — https://www.hubbell.com/wiringdevice-kellems/en/technical-resources ; web terms https://www.hubbell.com/hubbell/en/web-terms (verified live; updated 2022-01-06)
- Emerson / Appleton — https://emerson-appleton-e.partcommunity.com/3d-cad-models/appleton?info=appleton_group&languageIso=en&countryIso=US ; emerson.com ToU https://www.emerson.com/en-us/terms-of-use (verified live); CADENAS PARTcommunity terms UNREAD
- nVent — https://www.nvent.com/en-us/building-information-modeling ; terms https://www.nvent.com/en-us/terms-use (verified live)
- Not yet researched (gap): Vertiv, ASCO Power, independent panel OEMs (IEM, Milbank, Point Eight), Leviton, Cooper B-Line, Unistrut/Atkore; GE Vernova negative finding unverified.

Lighting manufacturers:
- Acuity Brands — https://www.acuitybrands.com/resources/technical-resources/bim-downloads ; site terms https://www.acuitybrands.com/site-terms ; collateral policy https://www.acuityinc.com/en/resources/our-newsroom/usage-policies/product-collateral-usage-policy
- Cooper Lighting (Signify) — https://www.cooperlighting.com/global/revit-files ; ToU https://www.cooperlighting.com/global/terms-of-use
- Genlyte (Signify NA) — terms https://www.genlyte.com/en-ca/terms-of-use (summarizer-read; verify verbatim)
- Cree Lighting — https://www.creelighting.com/document-library/ ; ToU https://www.creelighting.com/terms-of-use/
- Current / HLI (Prescolite, Columbia) — https://www.currentlighting.com/document-library/type/bim-files-4526 ; terms https://www.gecurrent.com/terms → https://www.led.com/terms
- Focal Point — https://www.focalpointlights.com/resources/bim-revit-library ; ToU https://www.focalpointlights.com/terms-use
- Finelite (Legrand brand) — https://www.finelite.com/downloads (no site ToU; check Legrand corporate terms)
- USAI Lighting — https://www.usailighting.com/revit-files-for-our-recessed-and-surface-mount-light-fixtures (no ToU; Revit Family User Guide PDF unread)
- RAB Lighting — https://www.rablighting.com/ies ; terms https://www.rablighting.com/legal (summarizer-read; verify verbatim)

Aggregators / marketplaces:
- BIMobject / Bim.com — https://www.bimobject.com/en-us/categories/lighting ; EULA https://business.bimobject.com/terms-of-service-eula/ ; API docs https://github.com/bimobject/api-documentation (no API terms found)
- BIMsmith — https://market.bimsmith.com/category/Lighting_revit ; terms https://bimsmith.com/legal/terms-and-conditions ; Market EULA https://bimsmith.com/eula.html (unread)
- ARCAT — https://www.arcat.com/content-type/bim ; terms https://www.arcat.com/terms
- CADdetails — https://www.caddetails.com/ ; ToU https://www.caddetails.com/Content/PDF/TermsOfUse.pdf
- NBS Source / National BIM Library — https://source.thenbs.com/en/gb/bimlibrary ; site terms https://www.thenbs.com/terms-and-conditions ; NBS ID licence https://www.thenbs.com/legal/nbs-id-licence-agreement
- MEPcontent (Trimble) — https://www.mepcontent.com/en/ ; footer terms → https://www.trimble.com/Support/Terms_of_Sale.aspx (no content license located)
- Not yet researched (gap): MODLAR, SmartBIM, TraceParts, CADENAS/PARTcommunity/BIMcatalogs, UNIFI catalogs, MagiCAD Cloud, 3Dfindit
- Community: RevitCity — https://www.revitcity.com/downloads.php (no terms located)

Autodesk / format / law:
- General Terms — https://www.autodesk.com/company/terms-of-use/en/general-terms (403 to automated fetch; verify current version in a browser)
- Legacy LSA (verified) — https://download.autodesk.com/global/dlm_eula/English.html
- Where to find Revit content — https://www.autodesk.com/support/technical/article/caas/sfdcarticles/sfdcarticles/Where-to-find-Revit-Content-Libraries-to-download.html
- Trademark guidelines for use — https://www.autodesk.com/company/legal-notices-trademarks/trademarks/guidelines-for-use ; trademark list https://www.autodesk.com/company/legal-notices-trademarks/trademarks
- APS Automation API for Revit — https://aps.autodesk.com/automation-apis ; sample https://github.com/autodesk-platform-services/aps-create-revit-family
- Open Design Alliance BimRv SDK — https://www.opendesign.com/products/bimrv ; FAQ https://www.opendesign.com/faq/bimrv ; pricing https://www.opendesign.com/pricing (membership agreement UNREAD)
- 17 U.S.C. §1201 — https://www.law.cornell.edu/uscode/text/17/1201
- Feist v. Rural — https://supreme.justia.com/cases/federal/us/499/340/
- Internal factual record — docs/legal/provenance-memo.md ; docs/inbox/ecc-intel-Utility-2023_1_9.QUARANTINED.md

Government / owner:
- USACE CAD/BIM Technology Center — UBOL https://cadbimcenter.erdc.dren.mil/ubol ; templates https://cadbimcenter.erdc.dren.mil/bim-cim/ (verified: no terms on site)
- VA — https://www.cfm.va.gov/til/bim.asp ; https://vatilms.va.gov/vatilms/reports/PG-18-13 ; VA copyright policy https://department.va.gov/copyright-policy/ (verified)
- GSA — https://www.gsa.gov/system/files/BIM_Guide_07_v_1.pdf ; site policy https://www.gsa.gov/website-information/website-policies (verified)
- NAVFAC on WBDG — https://www.wbdg.org/navy/cad/titleblocks-revit
- SEPS2BIM — https://seps2bim.org/revit-families.html
- Mass DCAMM — https://www.mass.gov/info-details/dcamm-revit-template-overview ; policy https://www.mass.gov/policy-statement/permissions-to-reproduce-content-or-images
- PANYNJ BIM Standard — https://www.panynj.gov/content/dam/port-authority/pdfs/-available-engineering-documents/BIM-Standard.pdf
- DEN — https://cdn.flydenver.com/app/uploads/2023/09/14083414/DENDigitalFacilitiesInfrastructureIDSM-1.pdf ; LAWA https://www.lawa.org/lawa-businesses/lawa-documents-and-guidelines/lawa-design-and-construction-handbook
- Not yet researched (gap): DoD UFC/UFGS BIM requirements, FAA, state DOTs, and the actual **DDOT / DC public-works BIM standard** for the named use case.

Standards:
- NBIMS-US v4 / COBie — https://nibs.org/nbims/v4/ ; license https://www.nibs.org/nbims/user-license-agreement
- IFC / buildingSMART — https://www.buildingsmart.org/standards/bsi-standards/industry-foundation-classes/ ; bSDD https://www.buildingsmart.org/users/services/buildingsmart-data-dictionary/ ; bSDD license https://technical.buildingsmart.org/services/bsdd/license/
- BIMForum LOD Spec — https://bimforum.org/resource/lod-level-of-development-lod-specification/ ; Part I 2024 https://bimforum.org/wp-content/uploads/2024/11/LOD-Spec-2024-Part-I-official-English.pdf
- Penn State BIM PxP Guide — https://psu.pb.unizin.org/bimprojectexecutionplanning/
- ANSI/IES TM-32-24 — https://webstore.ansi.org/standards/iesna/ansiiestm3224 ; ANSI/IES LM-63-19 — https://webstore.ansi.org/standards/iesna/ANSIIESLM6319 (purchase licenses UNREAD)
- GLDF — https://gldf.io/ ; https://github.com/globallightingdata/gldf
- CSI classifications — https://theconstructionstandard.com/license-masterformat-construction-software ; EULA https://theconstructionstandard.com/eula (unread)

---

### Consolidated QUESTIONS FOR COUNSEL (blocking order)

1. **Format layer (§5.1):** legality of our re-derived .rvt/.rfa writer given the documented
   provenance (sample-file and update-package acquisition terms, the DLL-confirmation step, any
   licensed QA seat); §1201(f) *and* the §1201(a)(2)/(b) trafficking prongs; clean-room advisability;
   preservation vs. destruction of the quarantined DLL; read ODA BimRv membership terms and APS
   Automation-API terms and advise on replacing the writer.
2. **Product name (§5.3):** rename + clearance; approved compatibility/attribution language.
3. **Immediate shipping exposure (§1, §5.7):** deliverables currently seeded from Autodesk sample
   projects with Autodesk-authored families — remediation and any obligations regarding
   already-shipped files.
4. **Extraction-pipeline collection legality (§5.2, §5.5):** what facts may be collected from spec
   sheets and by what means, source by source; the fact/expression line; design-patent/trade-dress
   screen on the master families; compilation copyright; UK/EU database right.
5. **Manufacturer-name usage in families (§5.4)** and the download-on-demand automation boundary
   (§5.2: Cree/Focal Point/ABB/CADdetails/NBS automation bans, BIMobject §4.4(c)/§4.7 scope,
   §4.7(j) AI-training ban, inducement).
6. **CSI classification licensing (§5.6)** and any TM-32 GUID-mapping-file redistribution.
7. **Per-source UNKNOWNs to convert via written license (Tier C targets):** Eaton (open the ZIP
   EULAs), Schneider (LayoutFAST EULA + live ToU read), Siemens (BIMPOWER/App-Store EULA), ABB
   (which terms govern the electrification host), Legrand/Finelite, Hubbell, Emerson (CADENAS
   terms), nVent, Acuity, Signify (Cooper/Genlyte), Cree, USAI, MEPcontent, USACE ERDC (UBOL
   position).

### Known research gaps carried into this strategy

- **The autodesk-licensing and family-formats lens reports, and the tail of the government lens
  (PANYNJ, Mass.gov, BIMForum Part II, WBDG/NIBS corrections the verifier reported), were not
  present in this synthesis input.** §5.1 and §6 are built from verified clauses plus supplementary
  retrieval and the provenance memo; reconcile against those lens reports when they land, and
  re-verify the BIMForum Part I/Part II licenses and the PANYNJ ownership clause specifically.
- **Unread governing documents** (the decisive gap): in-package EULAs/READMEs inside every vendor's
  BIM downloads (Eaton ZIPs, Legrand, nVent, Hubbell, ABB, Signify), Schneider LayoutFAST EULA,
  Siemens BIMPOWER / Autodesk App Store publisher terms, CADENAS PARTcommunity terms, BIMsmith
  Market EULA, MEPcontent registration terms, Hubexo/NBS product terms, IES/ANSI webstore purchase
  license, CSI EULA, USAI Revit Family User Guide. **Someone authorized must download and open the
  packages — this cannot be done by scraping and should not be.**
- **Owed verbatim reads** (currently summarizer- or index-corroborated only): Schneider se.com ToU,
  Genlyte, RAB /legal, live Autodesk General Terms, bSDD per-dictionary licenses, GLDF MIT text.
- **Vendors not researched:** Vertiv, ASCO Power, independent panel OEMs, Leviton, B-Line,
  Unistrut/Atkore, Legrand corporate (parent of Finelite/Pinnacle/Kenall/Wattstopper);
  aggregators MODLAR, SmartBIM, TraceParts, CADENAS, UNIFI, MagiCAD Cloud, 3Dfindit.
- **Owner/agency coverage:** DoD UFC/UFGS, FAA, state DOTs, DDOT/DC public-works BIM standard.
- **Customer-side Autodesk EULA:** whether the customer's own Revit terms restrict files/services
  not originating from an Autodesk Offering — never read; add as a row.
