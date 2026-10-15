# PR integration acceptance

## Scope and reconciliation

- PR #12, `4a52fc0387ceeb31f9775079e3452356d0c1f33e`: retain contributor history and integrate Endfield reports, operator/loadout, ship, honor, challenges, nullable gacha scan state, and opt-in public-asset DNS. Default DNS remains system resolution.
- Draft PR #11, `57965798c79e8367bb6025d3e837ddd6b3519c64`: adopt applicable Linux sandbox CI and shared-component verification ideas. Its alternate renderer, dark theme, first-page truncation, and fixed 30-day calendar do not replace the accepted renderer.
- Preserve light QQ output, shared Vue components/font sizes, all current-payload pools and rows, compact version calendar, post-render authorization checks, and whole-image failure fallback. No rankings, proactive QQ reminders, or site reminder settings are introduced.
- Original checkout has four untracked planning documents, not pending product-code changes. Preserve these documents and original configuration/login/database state. Local preview uses its existing isolated copies on port 18010.

## Review findings repaired

1. Compare internal account/role identifiers separately from upstream UID in Endfield gacha reports.
2. Preserve region collection keys/labels and known region/settlement counts through QQ projection.
3. Preserve each challenge category's own observation time and stale status; do not substitute query time.
4. Preserve nullable scan coverage as unknown instead of converting it to false.
5. Remove legacy Pillow clipping notices from complete shared-component gacha images.
6. Named operator detail projects only the selected operator, including the report training rows.
7. User-facing Endfield news copy avoids raw diagnostic and data-quality information.

## Verification and limits

- Frontend full run: 568 passed. Later challenge timestamp/state repair: 12 focused passed. Final news wording has separate focused coverage and fresh local/cloud builds.
- Backend full run before final focused closures: 2416 passed, 2 failed, 45 skipped. Selected-operator projection repair: 39 focused passed and 16 cache/scope/renewal/revocation checks passed. The other failure was an outdated browser fixture/runtime/caption assertion; explicit-browser sequence passed after preserving its original binding, cache, deduplication, independent media-upload and message-order assertions against the actual image DOM. Browser absence remains an explicit skip.
- Seven Endfield command browser cases passed across targeted runs, including 35 roster entries, 17 pools, independent cached detail, challenge timestamps, ship, honor and region labels/counts. Fixtures are synthetic; this does not establish real upstream-account data or friend-group delivery.
- Existing local synthetic old/new/old/new ledger compatibility passed. Cloud release additionally requires actual shard-copy migration and unchanged backup-helper restore, candidate static startup with zero database opens, and serial renders under the retained service sandbox/resource limits.
- Deployment preserves the same live data root, credentials, identity database, QQ state, original release/drop-ins and backup helper. Back up stopped writers before cutover; rollback changes code against the current database and does not restore a stale snapshot.
- Public publication retains the existing privacy hook. Preserve internal local history under an archive ref, then publish the identical accepted tree with the reviewed public PR #12 head as parent. This retains public contributor ancestry and permits ordinary fast-forward publication without disclosing private local commit metadata.

Cloud technical acceptance and exact deployed/published revision are recorded separately in release evidence. Real QQ receipt and authenticated cloud-page acceptance require their respective real sessions; passing source or synthetic checks must not be described as those outcomes.
