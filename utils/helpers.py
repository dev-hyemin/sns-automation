import os
import re
import textwrap
from typing import List

from PIL import ImageFont


# ---------------------------------------------------------------------------
# Filename safety
# ---------------------------------------------------------------------------

def safe_filename(name: str, max_len: int = 50) -> str:
    """Strip unsafe characters and truncate to produce a filesystem-safe name."""
    name = re.sub(r'[\\/*?:"<>|]', "", name)
    name = re.sub(r"\s+", "_", name.strip())
    return name[:max_len]


# ---------------------------------------------------------------------------
# Subtitle splitting
# ---------------------------------------------------------------------------

def split_into_subtitles(text: str, chars_per_slide: int = 60) -> List[str]:
    """Split a script into short subtitle chunks suitable for on-screen display."""
    sentences = re.split(r"(?<=[.!?。！？])\s+", text.strip())
    slides: List[str] = []
    current: List[str] = []
    current_len = 0

    for sentence in sentences:
        if not sentence:
            continue
        if current_len + len(sentence) > chars_per_slide and current:
            slides.append(" ".join(current))
            current = []
            current_len = 0
        current.append(sentence)
        current_len += len(sentence) + 1

    if current:
        slides.append(" ".join(current))

    # Fallback: split by word count if no sentence boundaries were found
    if not slides:
        words = text.split()
        chunk_size = max(8, len(words) // 5)
        slides = [" ".join(words[i : i + chunk_size]) for i in range(0, len(words), chunk_size)]

    return slides


# ---------------------------------------------------------------------------
# Font discovery
# ---------------------------------------------------------------------------

_FONT_CANDIDATES = [
    # Korean (Nanum)
    "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf",
    "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
    "/usr/share/fonts/opentype/nanum/NanumGothicBold.otf",
    "/usr/share/fonts/opentype/nanum/NanumGothic.otf",
    # macOS Korean
    "/System/Library/Fonts/AppleSDGothicNeo.ttc",
    "/Library/Fonts/Arial Unicode.ttf",
    # Generic Latin fallbacks
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
]


def find_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    """Return the best available font for the given size, preferring Korean fonts."""
    candidates = _FONT_CANDIDATES if not bold else _FONT_CANDIDATES
    if bold:
        # Prefer bold variants first
        bold_candidates = [p for p in _FONT_CANDIDATES if "Bold" in p or "bold" in p]
        candidates = bold_candidates + [p for p in _FONT_CANDIDATES if p not in bold_candidates]

    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue

    # Last resort – PIL default (tiny, no size control)
    return ImageFont.load_default()
