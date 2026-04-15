"""
Low-spec optimised video generator.

Strategy
--------
* Resolution : 720×1280 (9:16 vertical)
* FPS        : 24
* Clips      : ImageClip + AudioFileClip only (no complex animations)
* Effects    : none (no fade/zoom)
* Encoding   : libx264 ultrafast preset, 2 threads
* Memory     : every clip is .close()'d in a finally block
* Subtitles  : baked into PNG frames (12-second intervals, ≤12 lines/frame)
* CTA        : assets/follow.png inserted as last 3 seconds
"""

import os
import textwrap
from typing import List, Optional

from PIL import Image, ImageDraw

from utils.helpers import find_font, split_into_subtitles
from utils.logger import get_logger

logger = get_logger()

# Video dimensions (vertical short-form)
VIDEO_W, VIDEO_H = 720, 1280
FPS = 24
CTA_DURATION = 3          # seconds of CTA at the end
SUBTITLE_INTERVAL = 12    # seconds per subtitle slide


class VideoService:
    """Build optimised short-form videos from audio + subtitles."""

    def __init__(
        self,
        assets_dir: str = "assets",
        output_dir: str = "output",
    ) -> None:
        self.assets_dir = assets_dir
        self.output_dir = output_dir
        os.makedirs(self.assets_dir, exist_ok=True)
        os.makedirs(self.output_dir, exist_ok=True)
        self._ensure_default_assets()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate_video(
        self,
        audio_path: str,
        subtitles: List[str],
        platform: str,
        filename: str,
        script_text: str = "",
    ) -> str:
        """
        Generate a short-form video.

        Parameters
        ----------
        audio_path:  Path to the narration MP3.
        subtitles:   List of subtitle strings (one per slide).
        platform:    'youtube' or 'tiktok'.
        filename:    Output filename.
        script_text: Fallback text for auto-splitting subtitles.

        Returns
        -------
        Absolute path to the rendered video.
        """
        # Lazy import to avoid slow startup
        from moviepy.editor import (
            AudioFileClip,
            ImageClip,
            concatenate_videoclips,
        )

        output_path = os.path.join(self.output_dir, filename)
        bg_path = os.path.join(self.assets_dir, "bg.png")
        cta_path = os.path.join(self.assets_dir, "follow.png")

        # Ensure we have subtitle content
        if not subtitles:
            subtitles = split_into_subtitles(script_text) if script_text else [""]

        logger.info(f"Video: rendering {filename} ({len(subtitles)} subtitle slides)")

        audio: Optional[object] = None
        clips: List = []
        video = None

        try:
            audio = AudioFileClip(audio_path)
            total_dur = audio.duration
            content_dur = max(0.5, total_dur - CTA_DURATION)

            # ---- Subtitle clips ------------------------------------------------
            num_slides = len(subtitles)
            dur_per_slide = content_dur / num_slides

            for i, text in enumerate(subtitles):
                start = i * dur_per_slide
                slide_dur = min(dur_per_slide, content_dur - start)
                if slide_dur <= 0:
                    break

                frame_path = self._render_subtitle_frame(text, bg_path, i)
                clip = ImageClip(frame_path).set_duration(slide_dur)
                clips.append(clip)

            # ---- CTA clip -------------------------------------------------------
            cta_frame = self._render_cta_frame(cta_path, platform)
            cta_clip = ImageClip(cta_frame).set_duration(CTA_DURATION)
            clips.append(cta_clip)

            # ---- Assemble -------------------------------------------------------
            video = concatenate_videoclips(clips, method="compose")
            video = video.set_audio(audio)

            video.write_videofile(
                output_path,
                fps=FPS,
                codec="libx264",
                audio_codec="aac",
                preset="ultrafast",
                threads=2,
                verbose=False,
                logger=None,
            )

            logger.info(f"Video: saved → {output_path}")
            return output_path

        finally:
            # Release memory in order
            for c in clips:
                try:
                    c.close()
                except Exception:
                    pass
            if video is not None:
                try:
                    video.close()
                except Exception:
                    pass
            if audio is not None:
                try:
                    audio.close()
                except Exception:
                    pass

    # ------------------------------------------------------------------
    # Frame rendering (PIL)
    # ------------------------------------------------------------------

    def _render_subtitle_frame(self, text: str, bg_path: str, index: int) -> str:
        """Render subtitle text onto background; return path to PNG."""
        cache_name = f"_subtitle_{index}.png"
        frame_path = os.path.join(self.output_dir, cache_name)

        # Load or create background
        if os.path.exists(bg_path):
            img = Image.open(bg_path).convert("RGB").resize((VIDEO_W, VIDEO_H))
        else:
            img = Image.new("RGB", (VIDEO_W, VIDEO_H), (10, 10, 20))

        draw = ImageDraw.Draw(img)

        font = find_font(40)

        # Wrap text to fit width (approx 18 chars per line for 720px at size 40)
        lines = []
        for paragraph in text.splitlines():
            wrapped = textwrap.fill(paragraph.strip(), width=18)
            lines.extend(wrapped.splitlines())

        lines = lines[:12]  # Hard cap at 12 lines per spec

        # Position: vertically centred in the lower 40% of the frame
        line_h = 52
        block_h = len(lines) * line_h
        y = int(VIDEO_H * 0.58) - block_h // 2

        for line in lines:
            bbox = draw.textbbox((0, 0), line, font=font)
            text_w = bbox[2] - bbox[0]
            x = (VIDEO_W - text_w) // 2
            # Drop shadow
            draw.text((x + 2, y + 2), line, font=font, fill=(0, 0, 0))
            # Foreground
            draw.text((x, y), line, font=font, fill=(255, 255, 255))
            y += line_h

        img.save(frame_path, "PNG")
        return frame_path

    def _render_cta_frame(self, cta_asset: str, platform: str) -> str:
        """Render CTA frame; return path to PNG."""
        frame_path = os.path.join(self.output_dir, "_cta_frame.png")

        if os.path.exists(cta_asset):
            img = Image.open(cta_asset).convert("RGB").resize((VIDEO_W, VIDEO_H))
        else:
            # Create a simple text-based CTA
            img = Image.new("RGB", (VIDEO_W, VIDEO_H), (5, 5, 15))
            draw = ImageDraw.Draw(img)
            font = find_font(50, bold=True)
            small_font = find_font(34)
            cta_text = "팔로우하고 더 받기!" if platform == "youtube" else "Follow for more!"
            sub_text = "❤ Like & Follow"

            bbox = draw.textbbox((0, 0), cta_text, font=font)
            tw = bbox[2] - bbox[0]
            draw.text(
                ((VIDEO_W - tw) // 2, VIDEO_H // 2 - 60),
                cta_text,
                font=font,
                fill=(0, 255, 136),
            )
            bbox2 = draw.textbbox((0, 0), sub_text, font=small_font)
            tw2 = bbox2[2] - bbox2[0]
            draw.text(
                ((VIDEO_W - tw2) // 2, VIDEO_H // 2 + 20),
                sub_text,
                font=small_font,
                fill=(255, 255, 255),
            )

        img.save(frame_path, "PNG")
        return frame_path

    # ------------------------------------------------------------------
    # Asset initialisation
    # ------------------------------------------------------------------

    def _ensure_default_assets(self) -> None:
        """Create placeholder bg.png / follow.png if they do not exist."""
        bg_path = os.path.join(self.assets_dir, "bg.png")
        if not os.path.exists(bg_path):
            logger.info("Assets: creating default bg.png")
            img = Image.new("RGB", (VIDEO_W, VIDEO_H), (10, 10, 20))
            draw = ImageDraw.Draw(img)
            # Subtle grid
            for x in range(0, VIDEO_W, 60):
                draw.line([(x, 0), (x, VIDEO_H)], fill=(20, 20, 40), width=1)
            for y in range(0, VIDEO_H, 60):
                draw.line([(0, y), (VIDEO_W, y)], fill=(20, 20, 40), width=1)
            # Neon border
            draw.rectangle([(10, 10), (VIDEO_W - 10, VIDEO_H - 10)], outline=(0, 255, 136), width=2)
            img.save(bg_path, "PNG")

        follow_path = os.path.join(self.assets_dir, "follow.png")
        if not os.path.exists(follow_path):
            logger.info("Assets: creating default follow.png")
            img = Image.new("RGB", (VIDEO_W, VIDEO_H), (5, 5, 15))
            draw = ImageDraw.Draw(img)
            font = find_font(52, bold=True)
            text = "팔로우 & 좋아요!"
            bbox = draw.textbbox((0, 0), text, font=font)
            tw = bbox[2] - bbox[0]
            draw.text(((VIDEO_W - tw) // 2, VIDEO_H // 2 - 40), text, font=font, fill=(0, 255, 136))
            img.save(follow_path, "PNG")
