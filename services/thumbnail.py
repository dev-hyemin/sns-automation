"""
Thumbnail generator – dark background + neon (#00ff88) accent.

Output: 1280×720 PNG optimized for YouTube / TikTok thumbnails.
Uses only Pillow (no browser dependency) for low-spec compatibility.
"""

import os
from typing import Tuple

from PIL import Image, ImageDraw

from utils.helpers import find_font, safe_filename
from utils.logger import get_logger

logger = get_logger()

# Design constants
BG_COLOR: Tuple[int, int, int] = (5, 5, 15)
GRID_COLOR: Tuple[int, int, int] = (20, 20, 40)
NEON: Tuple[int, int, int] = (0, 255, 136)
WHITE: Tuple[int, int, int] = (255, 255, 255)
DARK: Tuple[int, int, int] = (5, 5, 15)

THUMB_W, THUMB_H = 1280, 720


class ThumbnailService:
    """Generate promotional thumbnails with a dark/neon aesthetic."""

    def __init__(self, output_dir: str = "output") -> None:
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate_thumbnail(
        self,
        topic: str,
        hook: str,
        filename: str = "thumbnail.png",
    ) -> str:
        """Render and save a thumbnail image.

        Returns the absolute path to the saved file.
        """
        output_path = os.path.join(self.output_dir, filename)
        logger.info(f"Thumbnail: generating → {filename}")

        img = Image.new("RGB", (THUMB_W, THUMB_H), color=BG_COLOR)
        draw = ImageDraw.Draw(img)

        self._draw_grid(draw)
        self._draw_border(draw)
        self._draw_neon_divider(draw)
        self._draw_topic(draw, topic)
        self._draw_hook(draw, hook)
        self._draw_badge(draw, "SHORTS")

        img.save(output_path, "PNG", optimize=True)
        logger.info(f"Thumbnail: saved → {output_path}")
        return output_path

    # ------------------------------------------------------------------
    # Drawing helpers
    # ------------------------------------------------------------------

    def _draw_grid(self, draw: ImageDraw.Draw) -> None:
        for x in range(0, THUMB_W, 80):
            draw.line([(x, 0), (x, THUMB_H)], fill=GRID_COLOR, width=1)
        for y in range(0, THUMB_H, 80):
            draw.line([(0, y), (THUMB_W, y)], fill=GRID_COLOR, width=1)

    def _draw_border(self, draw: ImageDraw.Draw) -> None:
        draw.rectangle([(20, 20), (THUMB_W - 20, THUMB_H - 20)], outline=NEON, width=3)

    def _draw_neon_divider(self, draw: ImageDraw.Draw) -> None:
        """Subtle horizontal accent line at vertical centre."""
        y = THUMB_H // 2
        draw.line([(60, y), (THUMB_W - 60, y)], fill=(*NEON, 40), width=1)

    def _draw_topic(self, draw: ImageDraw.Draw, topic: str) -> None:
        font = find_font(68, bold=True)
        text = topic[:22] if len(topic) > 22 else topic

        # Glow effect: draw 3 offset copies with decreasing alpha
        for offset, alpha in [(4, 60), (2, 120), (1, 180)]:
            glow = (*NEON, alpha)
            self._centered_text(draw, text, THUMB_H // 3, font, glow)

        # Sharp main layer
        self._centered_text(draw, text, THUMB_H // 3, font, WHITE)

    def _draw_hook(self, draw: ImageDraw.Draw, hook: str) -> None:
        font = find_font(38)
        text = hook[:48] if len(hook) > 48 else hook
        self._centered_text(draw, text, int(THUMB_H * 0.56), font, NEON)

    def _draw_badge(self, draw: ImageDraw.Draw, label: str) -> None:
        font = find_font(30, bold=True)
        bx, by = THUMB_W - 110, 65
        draw.rectangle([(bx - 70, by - 24), (bx + 70, by + 24)], fill=NEON)
        self._centered_text(draw, label, by, font, DARK, x=bx)

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    @staticmethod
    def _centered_text(
        draw: ImageDraw.Draw,
        text: str,
        y: int,
        font,
        fill,
        x: int = THUMB_W // 2,
    ) -> None:
        """Draw text centred on *x*."""
        try:
            bbox = draw.textbbox((0, 0), text, font=font)
            text_w = bbox[2] - bbox[0]
            draw.text((x - text_w // 2, y), text, font=font, fill=fill)
        except Exception:
            # Fallback for older Pillow without textbbox
            draw.text((x, y), text, font=font, fill=fill)
