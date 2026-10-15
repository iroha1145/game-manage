# Changelog

## Unreleased

- Endfield report continuity: shared challenge pages for the dashboard and cloud account details, independent category timestamps, stale-data retention on retry failure, and cleared views on identity/category changes. Added a separately scoped passport headhunting summary, explicit history coverage and unknown-rarity counts. QQ headhunting reports prioritize every pool's statistics and distribute bounded history rows fairly; challenge reports reserve all three category summaries before details. Text fallbacks retain the corresponding coverage and source times. Parser compatibility now accepts observed scalar officer IDs and the legacy regional currency alias. Validation: `docs/superpowers/plans/2026-10-15-endfield-report-continuity.md`.
- Endfield dashboard refinement: compact account controls and grouped navigation; industrial panels, independent loadout freshness and return-to-roster filters; full honor medal reports and QQ commands. Added reviewed official portraits for 35 operators with bounded image caching and avatar fallbacks, plus eight QQ report cards. QQ challenge queries now reuse scoped default-query caches with separate category timestamps, without loading credentials or fetching upstream data. Headhunting scans distinguish unvisited pools, completed empty pools and unknown legacy state, including migration compatibility. Synthetic browser and image validation: `docs/superpowers/plans/2026-10-15-endfield-dashboard-refinement.md`.
- Endfield Phase 1: shared web/QQ reports for daily overview, operator loadouts, roster training, regional development, Dijiang ship and headhunting history. Added filters, known-progress todos, collection deficits, source timestamps and explicit unknown/partial-history states; verified official-site catalog covers 35 operator avatars. Integrated current local login/UI changes with the scoped cloud/QQ branch. Validation uses synthetic account data, not live QQ delivery. Plan: `docs/superpowers/plans/2026-10-15-endfield-web-qq-phase-one.md`.
- Endfield: one-click Skland connection from the Hypergryph SMS login. The passport token is exchanged for a Skland session without a device id, the passport's own role is selected automatically, an expired session is exchanged again once, and the session is dropped when the passport logs out or switches account. Pasting a Skland cred remains as the manual fallback. Verified with a live official-server account on 2026-10-14 together with SMS login and headhunting sync; attendance sign-in is not yet verified. Design: `docs/superpowers/specs/2026-10-14-endfield-skland-passport-connect-design.md`.
- Fixed game navigation labels and icons disappearing after selection: animated backgrounds now keep their own stacking context when Vue updates theme classes. Game-specific colors remain intact in both themes.
- Refined the shared surfaces, navigation, game headers and overview cards using Option Pro's paper styling, with subtle hover lighting, restrained entrance motion and animated progress updates. Pointer effects respect reduced-motion preferences; navigation motion cleans up pending frames on unmount.
- Kept the compact activity timeline with inline labels, striped event bands and circular today markers. Aligned weekday, date and today text without overlap, while preserving exact date proportions, source details and per-game colors.
- Motion refinements preserve the initial PR's compact cards and centered Wuwa/NTE dialogs: selected mobile tabs stay visible, dialogs open and close with short transitions, and focus and scrolling are restored reliably. References and interaction rules are in `docs/frontend-motion.md`.
- Endfield toolbox: official-site news/calendar with stale-cache fallback, public map search and marker details, encrypted local Skland connection with explicit role selection, profile/operator/region/ship and challenge views, manual attendance, official reference tools, and local blueprint CRUD/export. Shared dashboard themes and controls are preserved.
- Added the official `E_CharacterGachaPoolType_Rerun` headhunting category. Public news/map reads and the official record-page enum were verified on 2026-09-28; private account flows were first verified with a live account on 2026-10-14 (attendance sign-in still unverified). See `docs/endfield-toolbox.md`.
- Arknights: Endfield (official server): Hypergryph account SMS login, account card, headhunting records synced from the official API into a local ledger (seqId de-duplication, resumable first sync, gap-aware pity counts), record list and export.
- Endfield Bilibili source (UID 1265652806) with an announcement parser for version-name titles, relative starts, “until the next version update” ends resolved from the next maintenance notice, dependent ends and multi-phase times.
- Bilibili rule version 5 keeps Endfield notices whose body mentions web events.
- Existing installations must add `endfield = "1265652806"` under `[bilibili_sources]` in `config.toml`.

## 0.1.0 — 2026-09-19

First public source release of the Windows localhost game dashboard.

- Vue dashboard and compact activity timeline for Wuthering Waves, NTE and League of Legends.
- Community login, source-backed account data, public announcements and local data storage.
- Consistent API Host/Origin checks and explicit write-request headers.
- Reproducible dependency lock, clean installation CI, optional OCR dependencies and frontend dependency fingerprinting.
- GPL-3.0-only licensing, third-party notices and original game identifier icons.
- Synthetic test identities and sanitized published Git history.

This release supports Windows local single-user use. Linux, public multi-user hosting, real SMS flows for arbitrary accounts and upstream data accuracy are not certified by automated tests. NTE stamina/city activity can be delayed by the official data source. See README for installation, upgrade and current feature boundaries.
