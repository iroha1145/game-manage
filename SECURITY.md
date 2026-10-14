# Security and supported use

The local launcher is a **single-user local application**, bound to `127.0.0.1:8010`. Do not expose this local app through a public listener, port-forward or unauthenticated reverse proxy. Origin/Host checks protect local requests; they are not account authorization for a shared server.

The separate `game_assistant.cloud_runtime --config <explicit-file>` entrypoint implements website sessions, CSRF, account ownership and a dedicated one-worker scheduler. Deployment/recovery tools and synthetic QA are implemented, but Linux/production HTTPS, real QQ/mobile acceptance and 24-hour operation remain unverified. Follow [cloud operations](docs/cloud-operations.md), use separate data and an external owner-only key, and deny `/internal/*` at public reverse proxies. Never expose the local app as a substitute for this boundary. Online backups are consistent per SQLite file; whole-system consistency requires recorded writer quiescence. Keys are backed up separately.

Credentials, databases and runtime logs belong in the ignored `data/` directory. Windows encrypts community credentials with the current user's DPAPI. Back up local data privately; do not attach configuration files, cookies, login responses or database copies to public issues. Use synthetic identifiers in tests and screenshots.

Please report suspected vulnerabilities using GitHub's private vulnerability reporting for this repository when available. If it is unavailable, open a minimal issue requesting a private contact method, without exploit details, credentials or personal data. Never post tokens or SMS codes.

Refreshes query external community services whose data can be delayed or inaccurate. A successful HTTP response or recent local read does not prove that the game state is current. In particular, NTE stamina/city activity may lag behind the game.
