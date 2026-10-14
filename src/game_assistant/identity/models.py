"""Trusted internal identity supplied by authentication boundaries."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Principal:
    user_id: str
    is_admin: bool
