# Legal groundwork and website: SpaceMissionStudio

> **How to use:** save this file as `SpaceMissionStudio/docs/LEGAL_AND_WEBSITE.md`. Optionally commit the claude.ai draft as `SpaceMissionStudio/site/index.html` first. Start Claude Code in plan mode (Shift+Tab) and send: *"Read SpaceMissionStudio/docs/LEGAL_AND_WEBSITE.md and follow it. Do Phase 1 only, then stop for my review."* After approving the plan, run one milestone per session: *"Implement milestone M1 from the approved plan. Stop when its acceptance criteria pass."*

## Role and goal

You are the engineer who built SpaceMissionStudio, working in `basilisk-SpaceMissionStudio`. SpaceMissionStudio is **my personal, non-commercial open-source project**. I am a private individual living in Germany. No employer or company has rights to it.

This work has two parts:

1. **Legal groundwork for the project:** make the third-party licence situation in every package complete and correct, change the app's licence, handle AI authorship properly, and find and reduce every other legal risk, documented in a risk register.
2. **A project website** that presents the app to mission analysts and systems engineers, looks like the same product as the app, and is hosted in the EU with as little visitor data as possible.

My aim is to carry as little legal risk as possible. **Implement every reasonable measure that protects me from legal problems, in the project, the packages, the repository and the website, including measures this file does not name.** When two options are otherwise equal, choose the more cautious one. You are not a lawyer, and you must not present anything as legal advice. You build the structure, checks and safeguards and you collect the facts; I supply or approve every legal text and every decision with legal effect, and I will have a lawyer review the risk register described in 1.4.

Before planning, read `CLAUDE.md`, `SpaceMissionStudio/CONTRIBUTING.md`, `docs/DECISIONS.md`, the UI overhaul document (`docs/ui/UI_OVERHAUL.md` or wherever it now lives), the theme package, the root `README.md`, `docs/reference/capabilities.md`, `docs/reference/limitations.md`, `CHANGELOG.md`, the packaging folder and any existing SBOM or licence report.

## Hard rules for both parts

- **No change to what the app computes.** Do not change calculations, CLI behaviour, scenario formats or generated outputs. Licence texts, file headers, notices, metadata, the About dialog, the first-start notice in 1.4, packaging contents, CI, repository files and documentation may change as this file describes. Every existing test must still pass.
- **Do not touch upstream Basilisk.** Everything outside `SpaceMissionStudio/` and this fork's own README section and workflows stays as upstream ships it, including the root `LICENSE` (Basilisk's ISC licence) and the root `docs/` folder (Basilisk's Sphinx docs).
- **Stay non-commercial.** Add nothing that makes the project a commercial activity: no prices, sales, paid support, sponsorship or donation buttons, `FUNDING.yml`, advertising, affiliate links, newsletters or "hire me" notes, on the website or in the repository. If such a thing already exists, list it in the plan. Under the EU Product Liability Directive and the Cyber Resilience Act, free and open-source software supplied outside a commercial activity is treated differently from commercial software, and I want to stay clearly on that side.
- **No invented facts and no legal text from you.** Every statement must trace to a file in the repository or a source you cite. Where a legal text is needed, create a clearly marked placeholder and ask me.
- **Official sources for legal facts.** Take legal facts from primary or official sources: EUR-Lex, gesetze-im-internet.de, BAFA, DPMA, EUIPO, the licence stewards (SPDX, the Interoperable Europe portal, the FSF and OSI) and each provider's own terms and privacy policy. Cite the link and the date you read it. Mark anything taken from a secondary source as unverified. Never rely on memory for a legal fact; if you cannot reach a source, say so and list it as open.
- **Stop and ask** whenever a step would publish something, change a licence, rewrite git history, delete published material, add user-facing legal wording, or rely on an assumption about a third party's terms that you could not verify from an official source.
- **Leave evidence.** Record every check, its date, the source you used and the result, so that I can later show that I acted with care.

## Part 1: Legal groundwork

### 1.1 Third-party licences in every package

Audit the wheel, the Linux `.deb` and the Windows setup program, not just `pyproject.toml`. Installers bundle a Python runtime, Qt and Qt WebEngine (which includes Chromium), Basilisk and its own third-party code, plotly.js, fonts, icons and reference data.

- **Inventory.** Generate an SBOM (SPDX or CycloneDX) for each package from what is actually inside it: every library, runtime, font, icon set, JavaScript asset and data file, with version, source, licence and copyright holder.
- **Obligations.** For each component, list what its licence requires when we redistribute it (licence text, notices, attribution, source availability, the right to replace a library) and how the package meets that requirement. Pay special attention to LGPL components (Qt, PySide6): ship them as separate replaceable libraries, include their licence texts, and make the exact corresponding source available. The safest way is to attach the matching source archives to each release; propose this in the plan.
- **Reference data.** For every bundled data set (planetary ephemerides and other SPICE kernels, Earth orientation parameters, space weather, gravity and atmosphere models, anything else), record the provider, the terms of use, whether redistribution is allowed, and any required citation. If redistribution permission is unclear, stop and ask; do not keep bundling it on an assumption.
- **Notices in the product.** Ship a complete `THIRD_PARTY_NOTICES` file and all licence texts in every package, and show them in the app (for example, Help › About › Third-party licences).
- **Keep it correct.** Add a CI check that regenerates the inventory for each package and fails on a component without a known licence, on a licence not on an allowlist, or on a missing notice.

### 1.2 Licence: change the app to EUPL-1.2

I have chosen the **European Union Public Licence v1.2 (EUPL-1.2)** for SpaceMissionStudio, starting with the next release. Reasons, for `docs/DECISIONS.md`: it is written for EU law and is official in all EU languages, including German; its warranty and liability clauses are designed to work under EU member-state law; and it makes the law of the licensor's EU country (Germany) apply. It replaces ISC for the app only.

- **Respect Basilisk's licence.** The app builds on Basilisk, which is ISC-licensed. ISC allows use, modification and distribution for any purpose, including under a different licence for our own code, on one condition: Basilisk's copyright notice and permission notice must appear in all copies. So:
  - Confirm Basilisk's licence and copyright holders from the `LICENSE` file of the exact Basilisk version the app pins (2.12.0 now), and record them.
  - Find every file or fragment in `SpaceMissionStudio/` that was copied or adapted from Basilisk (its `src/`, `examples/`, documentation, `supportData/` or tests). Compare against the Basilisk sources, not just by name. Each such file keeps Basilisk's copyright and ISC notice: unchanged files stay `SPDX-License-Identifier: ISC`; adapted files carry both notices and `SPDX-License-Identifier: EUPL-1.2 AND ISC`. List them all in `THIRD_PARTY_NOTICES`.
  - Every package that bundles Basilisk ships Basilisk's `LICENSE` unchanged, and the notices for Basilisk's own bundled third-party components found in 1.1.
  - The EUPL-1.2 applies only to my own work in `SpaceMissionStudio/`. Say this plainly in the README licence section: SpaceMissionStudio is EUPL-1.2; Basilisk, which it uses, remains ISC under its own copyright holders.
- **Check authorship first.** List every human author of commits that touch `SpaceMissionStudio/` (ignore bots and `Co-Authored-By: Claude` trailers). If anyone other than me appears, stop and tell me; their contributions cannot be relicensed without consent.
- **Use the official text.** Take the EUPL-1.2 text from an official source (the Interoperable Europe portal of the European Commission, or the SPDX licence list), byte for byte. Do not type it from memory. Add the English text as `SpaceMissionStudio/LICENSE` and the official German text as `SpaceMissionStudio/LICENSE.de`. If you cannot download them, stop and ask me for the files.
- **Apply it consistently:** the notice "Licensed under the EUPL" after my copyright notice, `SPDX-License-Identifier: EUPL-1.2` headers in the app's own source files, the package metadata (`license` field and classifiers), the About dialog, the README licence section and badge, `CONTRIBUTING.md` (contributions are accepted under EUPL-1.2), and every other place that says the app is ISC-licensed "like Basilisk".
- **Be clear about history.** Releases up to and including 1.3.0 stay under ISC. Say so in the README licence section and the CHANGELOG.
- **Check compatibility.** Confirm that EUPL-1.2 for the app is compatible with every dependency and bundled component found in 1.1, and record the result.

### 1.3 AI authorship

- **Transparency stays.** Keep the README note that Claude wrote the code, tests and documentation through Claude Code and that I reviewed and approved the work. Use the same wording on the website.
- **Check for copied code.** Run a licence and code-provenance scan (for example ScanCode Toolkit) over `SpaceMissionStudio/` to find licence texts, copyright notices or code fragments that came from third-party projects. Report every match with file and line, and propose removal, rewrite or correct attribution for each.
- **No overstated rights.** Copyright and licence notices name me as the licensor. Add nothing that claims more than that, and nothing that suggests Anthropic's involvement or endorsement. Mention Claude and Anthropic only to state the fact of authorship.

### 1.4 Every other legal risk: register and measures

Create `SpaceMissionStudio/docs/legal/RISK_REGISTER.md`: one entry per risk area with the facts you found, the measures you implemented, the evidence (file, command, source, date), what is still open, and what needs a lawyer or an authority. Cover at least the areas below, add any others you find, and implement every measure that is in your power and within the hard rules.

- **Liability for use of results.** Propose (for my approval) a short notice that the software is provided without warranty and is not intended for operational or flight use without independent verification, shown in the README, the documentation, the About dialog and once on first start (acknowledged, then not shown again). Give the flight-software export (the generated C project) its own, stronger notice wherever it is offered and in the generated project's README. Adding text to generated outputs would change them, so only propose it; do not do it without my approval.
- **Export control.** The app concerns spacecraft simulation, attitude control and flight-software generation. Do not judge legality. Collect the facts I need to check with BAFA or a lawyer: which features could fall under EU dual-use categories (in particular category 9) or US rules, that the code and documentation are publicly available in an open repository, and that nothing is distributed privately. Measures in your power: keep everything public, add nothing that is distributed only to specific people or countries, and offer no tailored technical help to specific foreign organisations through the project.
- **Third-party data inside the repository.** Check every template, test fixture and example for data with its own terms: orbital elements of real satellites (for example TLEs from Space-Track or CelesTrak, whose terms may restrict redistribution), outputs or scripts from GMAT or other tools, mission data from agencies or companies. Record the source and terms for each; replace data whose redistribution rights are unclear with synthetic data, and ask me before each replacement.
- **Standards and other copyrighted documents.** Check the documentation, compliance matrix and audit records for verbatim text, tables or figures from ECSS, CCSDS, ISO or other standards and publications. Keep references and short quotations with source; flag longer reproductions and propose paraphrases with a reference.
- **Name and trademarks.** Search the DPMA, EUIPO, USPTO and WIPO Global Brand Database records for marks identical or similar to "SpaceMissionStudio" in Nice classes 9 and 42, and report what you find with links. Do not register anything. Check that names of other products and organisations appear only to state facts.
- **Personal data and secrets in the repository.** Scan the working tree and the full git history (for example with gitleaks) for secrets, tokens, e-mail addresses, real names, user names, home-directory paths, host names and internal information, including logs, screenshots, test fixtures and notebooks. Fix the working tree. For history, only report: rewriting published history needs my decision.
- **Privacy inside the app.** Verify that the app sends nothing over the network except on an explicit user action (such as fetching reference data), list every such action with its destination, and document it in the user manual. Confirm there is no telemetry, crash upload or update check. Check what the logs record (the log path contains the user name) and make sure no log or export includes personal data unless the user puts it there.
- **Security and supply chain.** Add `SECURITY.md` with private vulnerability reporting through GitHub, publish SHA-256 checksums for every release asset, sign release artifacts (for example with Sigstore) if it needs no paid certificate, pin dependencies, and add dependency vulnerability scanning in CI. Propose measures that cost money (for example Windows code signing) without adopting them.
- **Contributions.** Require a Developer Certificate of Origin sign-off on every contribution and state in `CONTRIBUTING.md` and the pull-request template that contributions are accepted under EUPL-1.2. Enforce the sign-off in CI.
- **Repository presentation.** Check the README, About box, topics and release notes for the same things as the website: no unverified claims, no commercial elements, no third-party logos, correct licence statements.
- **Anything else.** If you find a risk not listed here, add it to the register with a proposed measure.

## Part 2: Website

### 2.1 Design and assets

The site and the app must look like one product. Use the real assets you already have: the theme package tokens, the bundled Inter and JetBrains Mono fonts, the Lucide icons of the navigation rail, the app icon, `SpaceMissionStudio/docs/images/banner.svg`, the screenshot harness and the documentation.

- **Starting point.** If `SpaceMissionStudio/site/index.html` exists, it is a draft made in claude.ai without repository access. Use it for structure and copy only. Replace its hand-copied colours, placeholder logo mark, guessed icons, system-font fallback, hard-coded version number and the screenshot loaded from `raw.githubusercontent.com`. The draft is not fit to publish as it is.
- **One source of truth.** A stdlib-only Python script (for example `SpaceMissionStudio/site/build.py`) generates the CSS custom properties from the theme tokens, copies the icons the page uses from the bundled Lucide set, copies the fonts with their OFL licence texts, reads the app version, the Basilisk version and the template count from the code, and writes the finished site to a build folder. No colour, font name, icon path or version is typed into the site by hand. CI fails when the committed site is out of date.
- **Same icons, same meaning.** Each app area uses exactly the icon the navigation rail uses for it.
- **Real screenshots**, made with the screenshot harness from a template after a run, in light and dark, at 2× scale, served with `<picture>` so dark-mode visitors see the dark version. Compress them (WebP with PNG fallback), set `width` and `height`, and lazy-load below the first screen. Run the harness with a neutral temporary user profile and home directory.
- **Design language** from the UI overhaul: calm, dense and precise; neutral surfaces; one accent for primary actions, selection and focus; status colours only for status, always with an icon or text; Inter and JetBrains Mono; 6 px and 8 px radii; 1 px subtle borders; shadows only on floating elements; 120–180 ms motion that respects `prefers-reduced-motion`; light and dark following the OS. A web page may use larger headings and more spacing, but type scale, colours, components and icon style must clearly match the app.
- **Plain web.** Static HTML and CSS, a few kilobytes of plain JavaScript at most, no framework, no Node build step.

### 2.2 Page outline

Propose changes in the plan if the real assets suggest a better order.

1. **Header:** app icon and name; links to the app section, Get started and Docs; a text link to the source on GitHub and a Download button.
2. **Hero:** headline, one-sentence description, primary "Download for Linux or Windows" (to the latest release), secondary "Install from source", a note on the licence and the offline installers, and a release pill naming what the current version added (from the CHANGELOG). The draft has an orbit diagram with an unnamed ground station; keep it, replace it with a real app element, or drop it, and say which in the plan.
3. **Product screenshot** in a window frame drawn in the app's style.
4. **Four short facts:** the Basilisk version, validation against GMAT, the number of templates, offline installers.
5. **The app, area by area,** following the navigation rail: each area with its rail icon, one sentence and two to four points from `capabilities.md`, plus one or two more screenshots (Results overview, Timeline) if they help.
6. **Get started:** the first-run steps from the README (template, Run with `Ctrl+R`, Results › Plots, Timeline), without naming the ground station, beside install tabs for Linux, Windows and From source with copy buttons that leave out the `$` prompts, and the requirements.
7. **Documentation:** the six most useful documents, then a line with the rest.
8. **Footer:** project links; the AI-authorship note; the licence (EUPL-1.2, earlier releases ISC); the fork relationship and the Basilisk credit; licence credits for fonts and icons; the non-affiliation and no-warranty sentences once I approve them; links to Impressum and Datenschutz.

Copy is natural and specific, in sentence case, with British spelling as in the README. Use the app's own names for screens and actions.

### 2.3 Legal safety of the site

- **No Berlin.** The site never names Berlin or any other real place as the ground station. Template 22 uses Berlin, and changing it would be an app change, so do not edit the template. If a screenshot would show the station name, raise it in the plan with options (another template for that screenshot, or a crop) and let me decide.
- **Impressum and Datenschutz.** Create `impressum.html` and `datenschutz.html`, linked from the footer of every page with exactly those labels, so they are easy to recognise, directly reachable and always available. Their content comes from Markdown files I provide in `SpaceMissionStudio/site/legal/`. Do not write, translate, shorten or edit legal text. Until I provide the files, the pages show a clear placeholder, and **the build fails in deploy mode while any placeholder remains**.
- **Data fact sheet.** Write `SpaceMissionStudio/site/legal/DATA_FACTS.md` for me and the person or generator that writes my privacy text. State exactly, and only as verified in the built site and in the host's official documentation: the host's name, legal form, address and server location; what the host logs (IP address, user agent, time, URL) and for how long; that the site sets no cookies, stores nothing in the browser, loads nothing from other hosts and has no forms; and that external links lead to github.com and the other sites they name.
- **No visitor data beyond the host's minimum.** No cookies, `localStorage`, `sessionStorage`, analytics, CDNs, external fonts or scripts, `preconnect` hints, embedded maps, videos or social widgets, and no contact forms. Downloads stay links to the GitHub releases page; nothing on the site loads from GitHub.
- **Third-party marks.** No logos, marks or mascots of anyone else, including NASA, ESA, the AVS Lab, the University of Colorado, GitHub and Anthropic. Link to GitHub with text only. Name other organisations and tools only to state facts.
- **Non-affiliation and no warranty.** Draft two short footer sentences for my approval: that SpaceMissionStudio is an independent personal project, not affiliated with or endorsed by the organisations named on the page; and that it is provided free of charge under EUPL-1.2 without warranty, so results must be verified independently before use for a real mission.
- **Careful claims.** No superlatives, no comparisons with commercial tools, no "certified", "qualified", "flight-proven", "validated" or standards-compliance claims (ECSS, CCSDS or other) unless the documentation states exactly that; then use its wording and link to the evidence.
- **No personal or internal data.** Before using any image, check it for user names, home-directory paths, host names, e-mail addresses, company or internal project names, real people's names and the ground-station name. The only personal data on the site is what I put in the Impressum.
- **Nothing new is published.** The site states only what is already public in the repository and adds no technical data, examples or downloads beyond the existing releases.

### 2.4 Hosting in the EU

Do not use GitHub Pages: GitHub logs the IP address of every visitor to a Pages site, and GitHub is a US company. Host the site in the EU instead, with the shortest log retention available.

- **Default:** Codeberg Pages, run by Codeberg e.V., a non-profit association in Germany. Verify from Codeberg's own current documentation and privacy policy: that the service is available and maintained, its terms for this kind of project, what it logs, for how long, and where the servers are. If anything there argues against it, say so.
- **Alternative for the plan:** a German web host that offers static hosting with access logging disabled or IP addresses anonymised. Give me facts and the yearly cost, without choosing a provider for me.
- **Deployment.** The GitHub Actions workflow builds the site and pushes the build output to the host (for Codeberg, a `pages` branch of a Codeberg repository I create), using an access token stored as a GitHub secret with the narrowest scope available. It runs on pushes to `develop` that touch the site, the theme tokens, the icons or the version, on published releases, and manually. Do not enable GitHub Pages for the repository.
- **Links.** Add a "Website" link near the top of the root README (in the part this fork owns), and tell me what to put in the Website field of the repository's About box.

## Process

**Phase 1: plan, no code.** Deliver:

- the inventory approach for each package, and a first list of components and data sets whose licence or redistribution terms need attention;
- the authorship check for the licence change;
- the provenance scan approach;
- the list of real assets for the site with paths (tokens, fonts, rail icon per area, app icon, banner, screenshot set);
- every fact the site will state, with its source file;
- the final page outline and which screenshot goes where;
- the hosting comparison (Codeberg Pages and one German alternative) with verified facts;
- anything commercial you found that should be removed;
- a first version of the risk register (1.4), with the facts you could collect without changing anything;
- the milestones, for example: **M1** third-party licence inventory, notices and CI check; **M2** licence change; **M3** provenance scan and fixes; **M4** risk register measures (data, documents, secrets, app privacy, security, contributions, notices); **M5** website build; **M6** EU hosting and deployment;
- your questions, including: the Impressum and Datenschutz texts (after `DATA_FACTS.md` exists); approval of the non-affiliation, no-warranty and not-for-operational-use wording; the hosting choice; a custom domain or not (this changes the data facts, so ask before setting one up); whether the licence change gets its own release.

Stop and wait for my approval.

**Then one milestone per session.** Record each decision in `docs/DECISIONS.md` with a one-line rationale. Add CHANGELOG entries under "Unreleased". Update the risk register at the end of every milestone.

**Things only I can do.** Ask me for these when you reach them, and prepare everything else so that each takes me as little time as possible:

- approve the plan, every user-facing legal wording and the hosting choice;
- supply the Impressum and Datenschutz texts;
- create the hosting account and repository and add the deployment token as a GitHub secret;
- change repository settings on GitHub (About box, private vulnerability reporting, branch rules);
- decide on any git history rewrite, data replacement or licence question you raise;
- have a lawyer review the risk register, and contact BAFA if the register says so.

## Verification

- All existing tests pass, and nothing in upstream Basilisk changed.
- Every package contains the EUPL-1.2 text for the app, the ISC text for Basilisk, `THIRD_PARTY_NOTICES` and every required licence text; the licence CI check passes; LGPL source archives are attached or the plan's alternative is in place.
- The provenance scan report has no open findings.
- The built site renders well at 390, 768, 1280 and 1920 px wide in light and dark (check with headless Chromium and look at the screenshots).
- Headless Chromium confirms the site makes no request to any host other than its own origin, sets no cookies and writes nothing to browser storage.
- Every internal anchor and repository link resolves; the HTML validates; text and background pairs pass WCAG 2.2 AA.
- The Impressum and Datenschutz links are on every page, and deploy mode fails while a legal placeholder remains.
- No published image contains personal or internal data or the ground-station name.
- The secret and personal-data scan of the working tree is clean, and history findings are reported.
- Every entry in the risk register has evidence and a status, and every open item names who must resolve it.

## Definition of done

The app is licensed under EUPL-1.2 from the next release, with a clear record that earlier releases are ISC. Every package states every third-party licence correctly and a CI check keeps it that way. No third-party code or data is included without the right to do so. A risk register records every legal risk area, the measures taken and the evidence, ready for a lawyer's review. The website is unmistakably the same product as the app, states only traceable facts, updates itself when the version or design changes, is hosted in the EU, loads nothing from third parties, stores nothing in the visitor's browser, and cannot go online without the Impressum and Datenschutz texts I supplied.
