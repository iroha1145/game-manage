# Complete QQ Component Parity Implementation Plan

> **For agentic workers:** Use the established front/backend owners to implement this plan. The user has approved all basic QQ cards migrating before release; no additional design approval is required. Parent owns final integration and deployment.

**Goal:** All existing data and basic response images use shared light-theme Vue website components, including WuWa roster without detail cache.

**Architecture:** Cached scoped data crosses a strict display projection into offline Vue props. Existing calendar/role/gacha contracts remain; new `game_snapshot` carries capability panels and `notice` carries sanitized structural messages. No account scope enters the DOM; scope fingerprints and post-render grant checks remain in the backend envelope.

**Tech Stack:** Python cached query service, Playwright Chromium, Vue components, pytest and Node tests.

**Spec:** User authorization relayed by parent on 2026-10-15: complete base QQ parity before release, no legacy data-card fallback.

## Global Constraints

- No configuration, database, auth schema, original repository, upstream window or feature expansion.
- One complete DOM image, 1080px width, 1MiB output, 16M pixels, 16000px height and 10-second total budget. JPEG fallback preserves complete dimensions. Over-limit images fail explicitly.
- Unknown, zero, estimated, lower-bound and incomplete data remain distinct. Missing history/detail is not synthesized.
- Only safe anonymous image URLs, approved fields and sanitized user text reach DOM; no raw identity, account scope, credentials, source HTML or user paths.
- Calendar four-field compact rows and geometry are frozen.

## Contract

Existing schema envelope remains `{schema_version:1,kind,game,display_data,as_of,page,title,next_command,theme:'light'}`.

- `kind:'game_snapshot'`: `display_data:{panels:[{game,provider,capability,snapshot:{payload,fetched_at,state,complete,stale}}],notices:[string]}`. Single capability has one panel; overview/summary may contain multiple providers. Provider is only `kuro/tajiduo/skland/hypergryph`, never an identity. Capability-specific payload projections feed actual shared website components.
- `kind:'notice'`: `display_data:{title:string,sections:[{title:string,items:[string]}],notices:[string]}`. Used only for help, binding/authorization state, refresh receipts, missing data and role disambiguation. Normal game data must not be replaced by an independent QQ template.
- Endfield Skland account-derived panels carry safe normalized `base/stamina/operators/regions/ship/achievements/progress` account data; independently read stamina may be wrapped by the frontend. Named roles select only the resolved cached operator.
- Current/recent activity panels carry backend-filtered source event lists, retaining uncertain timing semantics; frontend uses the existing timeline template. News uses the shared article list.
- WuWa roster uses the existing role component in offline image mode and needs no detail cache. Existing named-detail contract stays available.

## Review Focus

- Multi-account/private fingerprint and revocation during rendering must not return another user's image.
- Nested credentials/paths, unsafe image URLs and unknown keys must not pass projection or validation.
- Zero and missing data must remain distinct in every new panel family.
- Filtered event results must not silently become the full version calendar.
- Full image limits and missing shared snapshots must never trigger the old Pillow data template.

## Tasks

- [x] Backend owner: add failing projection/routing tests, then implement panel/notice factories in `src/game_assistant/qq/render_snapshot.py`, strict new-kind validation in `browser_rendering.py` and cached routing in `query_routes.py`. Preserve existing capture/recheck logic and read windows.
- [x] Frontend owner: implement shared panel dispatch and read-only image props. Use NteDataCard/NteAssetsPanel; WuwaProfile/WuwaRoles/Card/Combat/Activities/Resources; EndfieldGachaPanel and extracted EndfieldRecordContent also used on the webpage; AnnouncementList and calendar timeline. Disable API, controls/dialog-only content and technical details in image mode.
- [x] Backend owner: focused pytest verifies projections, current/recent events, WuWa roster, Endfield panels, safe notices, shared-required fallback, cache separation and revocation. Frontend owner runs only necessary component/pagination tests.
- [x] Owners: final built Chromium verifies the new kinds, complete DOM and original limits. Freeze source and notify parent.
- [ ] Parent: create new SHA, package and deploy only after integrated checks.

## Backend Implementation and Verification

Source is frozen after the following focused verification; this is local source/browser evidence, not deployment or real QQ receipt evidence.

- Added explicit game/capability payload allowlists and a second per-panel projection equality check. Provider/capability combinations, exact envelope keys, safe image URLs, limits and private-key rejection remain enforced. Account UID, account scope, credentials, paths and source HTML do not reach DOM.
- `game_snapshot` handles overview/summary/basic capabilities, filtered activities, news, Endfield roles/gacha and WuWa roster. Existing shared calendar/NTE/selected WuWa detail/gacha contracts remain. Structural responses use typed `notice`. Every migrated image requires a shared snapshot; no old Pillow card is used as an image fallback.
- Overview keeps separate Endfield providers. Role overview shows at most six compact entries with an explicit full-role command; gacha overview retains aggregates, removing history/records/rich details with an explicit summary boundary. Explicit role/gacha commands retain the entire current supplied input. Existing cache/ledger read windows are unchanged.
- News uses the existing webpage list's **180-character excerpt plus `…`**, preferring the source summary and otherwise deriving plain text from body. All article rows remain; full bodies/HTML do not enter the snapshot or DOM. Images explicitly state “摘要，全文请到原文或看板查看”. This is an article list, not article full text. Non-news business fields retain the unchanged 8000-character validation boundary.
- Current/recent activity selection matches the existing event view for phases, timezone interpretation, unknown/invalid endpoints and the inclusive 168-hour boundary; legitimate phase-specific names remain distinct.
- Typed image prefetch only visits actually mounted component image fields and deduplicates safe URLs; hidden legacy/card/overview assets are not prefetched. Original scope fingerprints and post-render binding/grant-version checks remain in place.
- Typed full snapshots use the original presentation notices, not the old text-card clipping output. Bare cache-quality metadata is omitted, so a complete shared image does not falsely say fields were truncated.

Final command: `python -m pytest tests/test_qq_complete_parity.py tests/test_qq_unified_queries.py -q --basetemp=.superpowers/calendar-compact/complete-parity-final` — **76 passed in 6.09s**. Raw output: `.superpowers/calendar-compact/complete-parity-final.log`.

The final run includes three actual `QqQueryService → projection → RenderQueue → BrowserRenderer` cases. Each checks the first/last required content, absence of private fields, complete displayed DOM block counts, 1080px width, byte/pixel limits, one page and closed browser contexts. WuWa roster requires no detail cache/read. Selected Endfield operator retains cached weapon, gem terms, equipment and skills, including zero/unknown values. Artifacts are under `.superpowers/calendar-compact/complete-parity-final/test_real_basic_command_throug{0,1,2}/` as PNG and JSON state/text.

| Final backend bridge | Dimensions | Bytes | Complete DOM blocks |
|---|---:|---:|---:|
| WuWa 21-role roster | 1080×714 | 91309 | 22/22 |
| Selected Endfield operator | 1080×457 | 45072 | 3/3 |
| Help notice | 1080×1485 | 104002 | 32/32 |

Frontend-owner independent native probe: `.superpowers/cloud-hotfix-20261015/complete-qq-native/metrics.json`, with full mixed capability panels and a long notice, no XHR/fetch and no DOM block outside the image. It is synthetic frontend readiness evidence; the backend bridge above separately proves actual projection/routing integration. Parent owns final source SHA, package, deployment and QQ acceptance.

## News-only Follow-up After the Linux Product Gate

The real cached WuWa news list has 39 articles. Read-only diagnostics found two sanitized text fields above the unchanged 8000-character boundary, with a maximum of 10054 characters; total text was only 193360 UTF-8 bytes and 355 nodes. This proves the failure was the unnecessary full-body expansion, not a list-size or total-payload limit. NTE has 40 articles and Endfield 10. Diagnostic evidence contains counts only: `.superpowers/cloud-hotfix-20261015/news-projection-a5617e67dca50caec29da4d64657565df72d328f.json`.

The follow-up restores shared webpage article-list semantics: project every article's title/category/date, a bounded explicit excerpt, public deduplication ID and safe original link; omit full body. Public post IDs are strictly bounded business identifiers and do not use the general numeric identity mask. Original anchors are restricted to the repository's existing official/community/Bilibili builder hosts, reject credentials/query/fragment/local paths, never enter asset prefetch and do not expand image CDN rules. No rendering limit is increased and no article-count sampling is introduced.

Backend news-only command: `python -m pytest tests/test_qq_complete_parity.py -q -k 'news_public_ids or news_keeps or large_public_body or rich_business'` — **4 passed, 21 deselected**. Log: `.superpowers/cloud-hotfix-20261015/news-excerpt-backend.log`. Synthetic 39-row long-body regression verifies all first/last articles, summary priority, 180+ellipsis, no body/HTML in the snapshot, distinct public IDs, safe links and no image prefetch. This is not a claim that the real Linux list has already passed the successor release gate.

Frontend owner reports **8 passed** with the same existing list excerpt rule and explicit summary label; evidence: `.superpowers/cloud-hotfix-20261015/news-excerpt-frontend-report.md`. Other previously accepted images are not re-run for this news-only correction. Parent creates a successor SHA and owns the remaining real Linux news/other pending direct-card gate and cold-run evidence.

## Cold WuWa Roster Deadline Follow-up

The successor `0e64c65a18e6719d718db15bbcbf8aa1dea7fd57` passed all 37 direct cards, including real news lists, but its 47-role cold query pipeline exceeded the unchanged 10-second total deadline. This remains a failed cold-pipeline gate until the next source SHA is verified; the successful direct cards are distinct evidence.

Read-only phase traces (`ww-trace-03.json`, `ww-trace-04.json` under `.superpowers/cloud-hotfix-20261015/`) isolated the main cost: `FontFace.load` 4.6127s, including font response `Route.fulfill` 4.2987s for the original 16,437,296-byte OTF. All 47 avatar decodes completed in about 1.281s; `document.fonts.ready` was effectively immediate. Python glyph validation, hashing and page layout were not the bottleneck. There were no XHR/fetch requests, OOMs or remaining child processes.

The Linux font-only comparison (`font-transport-05.json`) measured original-byte `body` loading at 4.2749s and original-file `path` loading at 2.7525s; both loaded the unchanged full font with identical public Chinese text width. A separate local gzip-header experiment failed font loading and was rejected. No compressed sidecar, font subset, runtime converter or new dependency was introduced.

The product change is **one line** in `browser_rendering.py`: the fixed font URL is fulfilled from the existing, validated `font_path` using `path=...` instead of manually reading an inline byte body. Font validation, raw font hash/cache semantics, CSP, network isolation, serial queue, asset handling, original bytes, content, image bounds and all budgets are unchanged.

Focused real-Chromium verification: `python -m pytest tests/test_qq_browser_rendering.py -q -k 'font_transport_uses or missing_font_and_timeout'` — **2 passed, 28 deselected in 1.91s**, log `.superpowers/cloud-hotfix-20261015/font-path-focused.log`. It verifies the original-file transport, ready complete one-page DOM, context cleanup and missing-font fallback. Parent and shell own the successor-SHA **actual 47-role cold query pipeline** check; the 37 completed direct-card cases are not repeated for this transport-only delta. Deployment is not authorized by this report.

## Complete WOFF2 Preparation After the Path-only Cold Gate

The actual cold gate for path-only SHA `4065005` still failed at 10.0169s (`cold-06.json`), despite the font-only comparison. It is not deployment evidence. The final change therefore adds a **complete-font WOFF2 container prepared before candidate guards**, using `scripts/cloud/prepare_render_font.py --font ORIGINAL_OTF --dist CANDIDATE_DIST` in an independent FontTools 4.63.0/Brotli 1.2.0 build environment. No runtime package, conversion, glyph subset, configured font or queue change is introduced.

The tool refuses existing output files and writes only fixed `render-font.woff2` and `render-font.json` in the explicit candidate dist. It disables optional WOFF2 table transformations and verifies the converted font against the original: complete raw CFF/CFF2 outline bytes, complete raw cmap table, all glyph names/order, all horizontal metrics and glyph count must match; the original file must remain byte-identical. The manifest binds both exact file hashes and sizes to those full-font proof hashes.

Runtime keeps `_font()` validation and the original font cache hash. Only exact-schema, safe fixed-path, non-symlink sidecars with matching source/target hashes, counts and WOFF2 signature are used. Every missing/malformed/stale/ineligible sidecar falls back to the original configured font. The existing build fingerprint includes both sidecar files. The operator must generate both files **before** `prepared_hashes`/precheck collection and include them in those guards.

Focused tests are in `tests/test_qq_font_sidecar.py`; build-tool tests use only `.superpowers/font-build-deps` locally and the separate release tool environment on Linux. Original runtime environments are unchanged. Actual full-OTF conversion/FontFace loading and the final 47-role cold product gate are separately recorded by shell/parent; the 37 accepted direct cases remain a carried difference check rather than a repeated matrix.

Final focused result: **10 passed, 1 skipped in 0.23s** (`font-sidecar-focused.log`); the skip is the Windows host's lack of permission to create a symlink, with runtime symlink rejection still explicit in source. The source/target/manifest/signature/count guards, original-file fallback, sidecar cache invalidation and full-CFF build proof all passed. No runtime environment received FontTools.

Actual Linux proof is recorded in `.superpowers/cloud-hotfix-20261015/font-woff2-proof-07.json`: the complete unchanged OTF was **16,437,296 bytes**, the WOFF2 is **11,427,576 bytes**; offline preparation took **62.987s**, outside query processing. All **65,535 glyphs**, original CFF outline-table bytes, full cmap-table bytes, glyph order and horizontal metrics matched. `FontFace.load` succeeded in **2.5465s** (fulfill 2.1013s), and public Chinese text width **240.00045776367188** matched the original. Resource peak was 548,925,440 bytes/99 tasks, with zero OOM, remaining children or external requests. This proof used an independent temporary output directory, leaving existing candidates, original font and runtime environments untouched. Product/tool/tests/plan are frozen for the parent to commit; only the successor-SHA 47-role cold query gate remains before a deployment decision.

## Fixed Font Manifest Static-UI Integration

Deployment startup exposed an integration gap: `validate_dist` rejected the prepared root `render-font.json`. The fixed root file is now an exact build-metadata exception, while it is excluded from static route installation and explicitly rejected by the file-serving helper. It remains available to the renderer through disk access; GET/HEAD return 404. WOFF2 uses the existing public font extension rule. Other JSON, nested/case-variant manifest names, API/private paths and symlink checks retain their existing restrictions.

Focused command: `python -m pytest tests/test_cloud_operations.py -q -k 'static_ui'` — **7 passed, 22 deselected**; log `.superpowers/cloud-hotfix-20261015/font-manifest-static-focused.log`. The new regression first reproduced `Unexpected static artifact`, then verified `validate_dist`, actual `build_app(frontend_dist=...)` installation and TestClient lifespan startup/health with cloud index, WOFF2 and manifest fixtures. It also checks public WOFF2 delivery, absent manifest route, GET/HEAD denial and rejection of unrelated JSON. This delta changes no font, rendering, queue, content or budget behavior; the already accepted image/cold-pipeline evidence is carried forward, and the parent/shell own the successor package and real service-start gate.
