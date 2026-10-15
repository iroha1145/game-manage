"""The explicit normalized role-detail envelope shared by archive consumers.

Outer role_id is an account UID. Only character_id and inner role.role_id identify
the game character. This helper never unwraps arbitrary payload/data recursion.
"""


def _identity(value):
    if type(value) not in (str,int):return None
    text=str(value)
    return text if text and text==text.strip() and len(text)<=256 and text.isprintable() else None


def role_detail_data(payload,character=None,*,allow_flat_missing_identity=False):
    if not isinstance(payload,dict):return None
    expected=_identity(character) if character is not None else None
    if character is not None and expected is None:return None
    if 'data' in payload:
        if (type(payload.get('schema_version')) is not int or payload['schema_version']!=1
                or _identity(payload.get('role_id')) is None or _identity(payload.get('server_id')) is None
                or not isinstance(payload.get('provenance'),dict)):return None
        declared=_identity(payload.get('character_id'))
        data=payload['data']
        if not isinstance(data,dict) or not isinstance(data.get('role'),dict):return None
        inner=_identity(data['role'].get('role_id'))
        if declared is None or declared!=inner or expected is not None and declared!=expected:return None
        return data
    # Explicit legacy flat role data is retained; unsupported wrappers fail closed.
    role=payload.get('role')
    if not isinstance(role,dict):return None
    inner=_identity(role.get('role_id'))
    if inner is None:
        return payload if allow_flat_missing_identity and 'role_id' not in role else None
    if expected is not None and inner!=expected:return None
    return payload


def archived_role_detail(rows,character):
    """Rows already originate from account/server-scoped history storage."""
    row=next((r for r in rows if role_detail_data(r.get('payload'),character) is not None),None)
    if row is None:return None,None
    # History deduplicates unchanged content: preserve the retained observation,
    # rather than falsely using a newer HTTP response time.
    return row['payload'],row.get('observed_at') or row.get('source_at')
