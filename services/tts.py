"""
Text-to-Speech service using gTTS (free, no API key required).

Audio speed is increased to ~1.1x via pydub to match the energetic
pace of short-form video content.
"""

import os
from typing import Literal

from gtts import gTTS
from pydub import AudioSegment

from utils.logger import get_logger

logger = get_logger()

LangCode = Literal["ko", "en"]

LANG_MAP: dict = {
    "korean": "ko",
    "english": "en",
    "ko": "ko",
    "en": "en",
    "youtube": "ko",
    "tiktok": "en",
}


class TTSService:
    """Generate and optionally speed-up TTS audio files."""

    def __init__(self, output_dir: str = "output") -> None:
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate_audio(
        self,
        text: str,
        language: str,
        filename: str,
        speed: float = 1.1,
    ) -> str:
        """
        Convert *text* to speech and save as *filename* inside output_dir.

        Parameters
        ----------
        text:     Narration text.
        language: 'korean' / 'ko' / 'english' / 'en' / 'youtube' / 'tiktok'.
        filename: Output filename (e.g. 'youtube_audio.mp3').
        speed:    Playback speed multiplier (default 1.1 ≈ 10% faster).

        Returns
        -------
        Absolute path to the generated audio file.
        """
        lang_code: str = LANG_MAP.get(language.lower(), "ko")
        output_path = os.path.join(self.output_dir, filename)
        temp_path = output_path.replace(".mp3", "_raw.mp3")

        logger.info(f"TTS: generating audio [{lang_code}] → {filename}")

        try:
            tts = gTTS(text=text, lang=lang_code, slow=False)
            tts.save(temp_path)

            if speed != 1.0:
                output_path = self._adjust_speed(temp_path, output_path, speed)
            else:
                os.replace(temp_path, output_path)

            logger.info(f"TTS: saved → {output_path}")
            return output_path

        except Exception as exc:
            logger.error(f"TTS generation failed: {exc}")
            # Clean up temp file if it exists
            if os.path.exists(temp_path):
                os.remove(temp_path)
            raise

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _adjust_speed(src: str, dst: str, speed: float) -> str:
        """
        Speed-adjust audio by resampling (pydub trick).

        This changes the perceived playback speed without pitch shift.
        The resulting file is exported at the original sample rate.
        """
        audio = AudioSegment.from_mp3(src)
        original_rate = audio.frame_rate
        new_rate = int(original_rate * speed)

        sped_up = audio._spawn(audio.raw_data, overrides={"frame_rate": new_rate})
        sped_up = sped_up.set_frame_rate(original_rate)
        sped_up.export(dst, format="mp3")

        if os.path.exists(src):
            os.remove(src)

        return dst
