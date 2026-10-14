"""Explicit cloud schema migrations; never run from the local entry point."""

from .cloud_v1 import migrate_cloud_schema

__all__ = ["migrate_cloud_schema"]
