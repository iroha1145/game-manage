"""Probe six fixed public icons with production cache security, never accounts.

Run with the package available on PYTHONPATH and a new, dedicated output folder:
  python probe_public_qq_assets.py --output /tmp/public-qq-assets-unique
No SSH, service mutation, proxy, credentials or arbitrary URL argument exists.
"""
import argparse
import asyncio
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from game_assistant.qq.assets import PublicAssetCache
from game_assistant.qq.public_asset_catalog import MANIFEST

PUBLIC_PROBES = (
    ('wuthering_waves', 'role', '忌炎',
     'https://prod-alicdn-community.kurobbs.com/forum/181ae6af195245f288248482021c5e2020240811.png'),
    ('wuthering_waves', 'weapon', '苍鳞千嶂',
     'https://prod-alicdn-community.kurobbs.com/forum/e99be3c12c4d499e94ed7e1018d9aa2020240515.png'),
    ('wuthering_waves', 'skill', '1405::共鸣技能',
     'https://web-static.kurobbs.com/adminConfig/36/role_skill_icon/1716030912550.png'),
    ('nte', 'role', '早雾',
     'https://webstatic.tajiduo.com/bbs/pic/player_003_256.png'),
    ('nte', 'weapon', '勿忘伞',
     'https://webstatic.tajiduo.com/bbs/yh-game-records-web-source/character/fork/fork_yuren.png'),
    ('nte', 'skill', '1003::普通攻击',
     'https://webstatic.tajiduo.com/bbs/yh-game-records-web-source/character/skill/ga_sagiri_melee.png'),
)


async def probe(output):
    output.mkdir(parents=True, exist_ok=False)
    cache = PublicAssetCache(request_timeout=5)
    record = {'created_at':datetime.now(timezone.utc).isoformat(),
              'scope':'Six fixed public icons plus owned game emblems; no account or live QQ verification.',
              'source_manifest':MANIFEST, 'assets':[]}
    refs = []
    for game, kind, name, url in PUBLIC_PROBES:
        ref = cache.register_url(url)
        if not ref or ref != cache.ref_for(game, kind, name):
            raise ValueError('Probe is no longer bound to the audited public catalog')
        refs.append(ref)
        record['assets'].append(dict(game=game, kind=kind, name=name, url=url, ref=ref))
    try:
        await cache.prefetch(refs, budget_seconds=5)
        for game in ('all', 'wuthering_waves', 'nte', 'endfield'):
            ref = cache.ref_for(game, 'game', game)
            record['assets'].append(dict(game=game, kind='game', name=game, ref=ref,
                source='Original GPL-3.0-only geometric emblem by game-manage contributors; not official art.'))
        for item in record['assets']:
            image = cache.get_image(item['ref'])
            item['available'] = image is not None
            if image is not None:
                filename = item['ref'] + '.png'
                image.save(output / filename, 'PNG')
                item.update(path=filename, size=list(image.size),
                    sha256=hashlib.sha256((output / filename).read_bytes()).hexdigest())
            else:
                item['status'] = 'Unavailable within bounded public-only fetch; no security rule bypassed.'
        (output/'manifest.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps({'manifest':str(output/'manifest.json'),
                          'public_icons_available':sum(item['available'] for item in record['assets'] if item['kind'] != 'game'),
                          'owned_emblems_available':sum(item['available'] for item in record['assets'] if item['kind'] == 'game')},ensure_ascii=False))
    finally:
        await cache.aclose()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    asyncio.run(probe(args.output.resolve()))
