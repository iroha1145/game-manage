"""Compare verified role identities without conflating channel and server."""


CHANNELS = frozenset(('official', 'bilibili', 'unknown'))


def role_channel(role, credentials=None):
    # Grants written before channel support were scoped under 'official'. Keep
    # that storage identity until a new upstream verification supplies metadata.
    channel = role.get('channel', (credentials or {}).get('channel', 'official'))
    return channel if isinstance(channel, str) and channel in CHANNELS else None


def has_verified_role(credentials, role_id, server_id, channel):
    return any(str(role.get('role_id')) == role_id
               and str(role.get('server_id')) == server_id
               and role_channel(role, credentials) == channel
               for role in credentials.get('_verified_roles', []))
