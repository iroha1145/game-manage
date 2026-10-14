"""Current cloud schema dispatcher; legacy versioned initializers stay strict."""
from .cloud_v4 import migrate_qq_redemption_schema


def initialize_cloud_schema(connection):
    return migrate_qq_redemption_schema(connection)
