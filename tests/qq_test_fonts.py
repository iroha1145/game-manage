"""Existing system CJK fonts for real Pillow tests on Windows, Linux and macOS.

No font is downloaded and no bitmap fallback is substituted. Tests still skip
when none of the known installed fonts can render the required Chinese glyphs.
"""
from pathlib import Path

from PIL import ImageFont
import pytest


FONT_PATHS = (
    'C:/Windows/Fonts/msyh.ttc',
    '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc',
    '/System/Library/Fonts/Hiragino Sans GB.ttc',
    '/System/Library/Fonts/STHeiti Medium.ttc',
)


def _load(path, size=30):
    # Match SummaryRenderer's Simplified Chinese face in the Noto collection.
    index = 2 if Path(path).name == 'NotoSansCJK-Regular.ttc' else 0
    return ImageFont.truetype(path, size, index=index)


def cjk_font_path():
    for path in FONT_PATHS:
        if not Path(path).is_file():
            continue
        try:
            font = _load(path)
            tofu = bytes(font.getmask('\uffff'))
            if all(bytes(font.getmask(char)) != tofu for char in '鸣潮未知账号等级终末地'):
                return path
        except (OSError, ValueError):
            continue
    pytest.skip('Install a supported system CJK font to verify real QQ image rendering')
