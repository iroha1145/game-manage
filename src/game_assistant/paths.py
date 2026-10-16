"""Private files are never reached through a symlink or a Windows junction."""
from pathlib import Path
import stat


def through_link(path):
    """True when the path or any of its parents is a symlink or a reparse point (junction)."""
    path = Path(path).absolute()
    return any(item.is_symlink() or (item.exists() and getattr(item.lstat(), 'st_file_attributes', 0)
               & getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 0x400)) for item in (path, *path.parents))
