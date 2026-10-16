# Changelog

## Unreleased

- Faster start: game pages and their icon/guide catalogs load on first visit (initial script 697 kB → 162 kB, styles 196 kB → 69 kB); a tab left open across an update shows a refresh prompt instead of a blank game page. Opening LoL analysis on a large archive no longer stalls other requests.
- Calendar and sources: Bilibili notices without a year get the right year around New Year; an impossible time in an Endfield notice no longer breaks official news, the calendar or `/api/status`; rejected anonymous NTE feeds are a source error, not "登录已失效"; an upstream SMS rate limit keeps its cooldown (429).
- Dashboard fixes: the chosen Wuwa resource period survives the minute refresh; Escape on an ⓘ tip no longer closes the dialog behind it; Bilibili login keeps its session while the account is typed; NTE guides "只看已拥有" works; the NTE rule form only offers savable rules; an open LoL match stays open on refresh; source and sync panels follow the selected game and count unconfigured items; the local service being down reads in Chinese.
- Safety: one byte-counting body limit now covers every login route, chunked requests included; deeply nested JSON and mistyped gacha fields return 4xx instead of 500.
- Removed unreachable code: GameCard's generic capability map and StatsCard, unused helpers, exports, props and about 30 dead CSS selectors.
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
