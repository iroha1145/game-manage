# QQ shared Vue image runtime

Calendar, cached Wuwa role details, NTE roles and Wuwa/NTE gacha images use the
website's real Vue content components. Build both entries with `npm ci && npm run
build` in `frontend`. The screenshot entry is `dist/render.html`; it needs no
public screenshot service and does not grant anonymous API access. Existing
cloud static validation accepts its HTML/JS/CSS files. Source maps, credentials,
account profiles and private database files must never be placed in `dist`.

Install the explicitly optional Python extra (`uv sync --extra qq-render`) during
deployment preparation. The locked runtime is Playwright 1.58.0. Install its
matching Chromium and OS libraries in that preparation step, never at service
runtime. Set `qq_browser_render_executable_path` only to the service's dedicated
installed Chromium, or leave empty to use that Playwright installation's default
browser. No user's Chrome/Edge profile or bundled Codex runtime is selected.

`qq_browser_render_enabled` defaults true; `qq_browser_render_dist_path` defaults
to the repository's `frontend/dist`. Configure `qq_image_font_path` to a
service-readable Noto Simplified Chinese font, obtained under its own license.
No Windows font is bundled. Both modes reuse `--font-sans` and the application's
theme tokens; image mode loads those explicit font bytes and validates real CJK
glyphs. Keep the website's Noto family installed/available when comparing modes.
Missing build, font or browser produces the existing text fallback. Game panels
and notices use the same runtime; no Pillow card renderer remains.

Every job gets a new browser context, no storage state, cookies or account token,
timezone Asia/Shanghai, fixed width 1080, reduced motion and blocked service
workers. Only the fixed `https://render.invalid/render.html`, its built assets,
configured font and pre-sanitized public asset cache can resolve. API requests,
external navigation and unexpected resources abort; attempts at active requests
invalidate rendering. Optional missing images show placeholders; required font
or unstable/omitted content fails readiness. The job/fingerprint marker must
match before a selected complete page is captured.

The existing queue admits at most ten requests and runs one worker. The total
caller budget remains at most ten seconds. Cancelling an HTTP await does not free
the worker until the browser job finishes/closes its context. Shutdown drains the
queue and closes Chromium/Playwright. Cache entries include user/account/role,
all grants/snapshot fingerprints, payload/page/theme, font contents and built
component contents. Invalidation prevents results from being inserted again.
Final link/grant checks still occur after render; this alone is not an atomic
guarantee across QQ upload/send or concurrent revocation on the remote platform.

The outbound protocol remains one image with `msg_seq=1`. Complete content blocks
paginate into at most 100 pages; page numbers and next commands are visible in
the image and response text. Out-of-range requests report the available range.
Calendar receives the complete authorized public activity snapshot before legacy
text-card truncation. Wuwa gacha currently reads the existing ledger window of
at most 500 items/gold rows; its full aggregate is preserved, with an explicit
visible window notice when rows exceed that window. NTE imported ledger content
is currently a summary, separately from community S-record details. Neither
mode invents missing history or claims complete official calendar coverage.

Before deployment, measure this exact Linux Chromium/font build under the
existing systemd memory/task/CPU limits, verify its sandbox works without adding
`--no-sandbox`, and check shutdown. Windows isolated PNG evidence is not proof of
Linux resource limits, production installation or real QQ receipt.

For local browser acceptance, set `QQ_RENDER_TEST_EXECUTABLE` and
`QQ_RENDER_TEST_FONT`, build frontend, then run
`pytest -q tests/test_qq_browser_rendering.py`. Without these explicit paths,
real-browser tests skip and must not be reported as browser acceptance.
