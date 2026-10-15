"""Display semantics shared by Endfield's safe documents and image layouts.

These keys describe presentation only; source facts and report schemas stay in
endfield_reports. Unknown categories retain the generic, measured layout.
"""

COLORS = {
    'background': '#0c1012', 'panel': '#161c1f', 'card': '#20282b',
    'soft': '#283237', 'border': '#3c494e', 'ink': '#f1f3ee',
    'muted': '#afbcc0', 'yellow': '#ffd000', 'cyan': '#58d5de',
}

SECTION_LABELS = {
    'ef_overview': 'OPERATOR STATUS', 'ef_tasks': 'DAILY OPERATIONS',
    'ef_todos': 'PENDING OBJECTIVES', 'ef_infrastructure': 'FIELD SUMMARY',
    'ef_training': 'TRAINING OVERVIEW', 'ef_roster': 'OPERATOR ROSTER',
    'ef_operator': 'OPERATOR DOSSIER', 'ef_provenance': 'OBSERVATION LOG',
    'ef_weapon': 'WEAPON SYSTEM', 'ef_gem': 'WEAPON ESSENCE',
    'ef_equipment': 'EQUIPMENT LOADOUT', 'ef_skills': 'COMBAT SKILLS', 'ef_tactical': 'TACTICAL ITEM',
    'ef_regions': 'REGIONAL DEVELOPMENT', 'ef_settlements': 'SETTLEMENT STATUS',
    'ef_collections': 'EXPLORATION RECORDS', 'ef_ship': 'DIJIANG OVERVIEW',
    'ef_room': 'ROOM ASSIGNMENTS', 'ef_gacha': 'HEADHUNTING REPORT',
    'ef_gacha_pool': 'RECORDED PULL HISTORY', 'ef_gacha_pools': 'POOL COVERAGE', 'ef_honor': 'PATH OF HONOR',
    'ef_medals': 'MEDAL COLLECTION', 'ef_honor_groups': 'CATEGORY COVERAGE',
    'ef_challenge': 'CHALLENGE OBSERVATIONS', 'ef_war': 'WAR RECORDS',
    'ef_monument': 'MONUMENT RECORDS', 'ef_crisis': 'CRISIS RECORDS',
}
