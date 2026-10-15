"""Public, game-scoped linguistic catalog; no account reads or side effects."""
import json
from pathlib import Path
import re
import unicodedata

_CATALOG = json.loads(Path(__file__).with_name('character-search-catalog.json').read_text(encoding='utf-8'))

def normalize_search(value):
    return re.sub(r'[\s.·・•‧]', '', unicodedata.normalize('NFKC', str(value if value is not None else '')).lower())

def character_id(entry):
    for key in ('character_id', 'role_id', 'id'):
        if entry.get(key) is not None:
            return str(entry[key]).strip()
    return ''

def catalog_entries(game):
    return [row for row in _CATALOG['characters'] if row['game'] == game]

def character_label(game, entry):
    row = next((row for row in catalog_entries(game) if row['character_id'] == character_id(entry)), None)
    if row:
        return row['canonical_name']
    form = entry.get('form') or entry.get('attribute') or ''
    return str(entry.get('canonical_name') or entry.get('name') or '') + ('·' + str(form) if form else '')

def _terms(game, entry):
    row = next((row for row in catalog_entries(game) if row['character_id'] == character_id(entry)), None)
    values = [character_id(entry), entry.get('canonical_name') or entry.get('name'), character_label(game, entry)]
    if row:
        values += [row['canonical_name'], *row['aliases'], *row['pinyin'], *row['initials']]
    return {key for value in values if (key := normalize_search(value))}

def _one_edit(a, b):
    if abs(len(a)-len(b)) > 1:
        return False
    i = j = edits = 0
    while i < len(a) and j < len(b):
        if a[i] == b[j]:
            i += 1; j += 1; continue
        edits += 1
        if edits > 1:
            return False
        if len(a) >= len(b): i += 1
        if len(b) >= len(a): j += 1
    return edits + int(i < len(a) or j < len(b)) <= 1

def search_characters(game, query, entries=None):
    key = normalize_search(query)
    if not key:
        return []
    found = []
    for entry in catalog_entries(game) if entries is None else entries:
        if not isinstance(entry, dict): continue
        values = _terms(game, entry)
        score = (0 if key in values else 1 if any(key in value for value in values) else
                 2 if len(key) >= 2 and not re.search(r'\d',key) and any(len(v) >= 2 and not re.search(r'\d',v) and _one_edit(key, v) for v in values) else 3)
        if score < 3:
            found.append(dict(entry=entry, character_id=character_id(entry), canonical_name=character_label(game,entry), match=('exact','partial','suggestion')[score], score=score))
    exact = [item for item in found if item['score']==0]
    if exact: return exact
    if any(row['game']!=game and key in _terms(row['game'],row) for row in _CATALOG['characters']):
        return []
    return sorted(found, key=lambda item:item['score'])

def resolve_character(game, query, entries):
    candidates = search_characters(game,query,entries)
    exact = [item for item in candidates if item['match'] == 'exact']
    status = 'resolved' if len(exact)==1 else 'ambiguous' if exact else 'candidates' if candidates else 'none'
    return dict(status=status, entry=exact[0]['entry'] if len(exact)==1 else None, candidates=exact or candidates)
