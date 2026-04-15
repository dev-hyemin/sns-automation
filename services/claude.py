"""
Claude API service – hook generation & script generation.

Uses claude-opus-4-6 with prompt caching for repeated calls on the
same topic, keeping latency and cost low.
"""

import os
import re
from typing import Dict, List

import anthropic

from utils.logger import get_logger

logger = get_logger()

# ---------------------------------------------------------------------------
# Hook pattern library (used in prompts)
# ---------------------------------------------------------------------------

HOOK_PATTERNS = [
    "이거 모르면 손해",
    "개발자만 아는 방법",
    "시간 절약",
    "충격/반전",
    "비교",
    "리스트형",
    "문제 공감",
    "즉시 결과",
    "숨겨진 기능",
    "경고형",
]


class ClaudeService:
    """Wraps the Anthropic client for content generation."""

    def __init__(self) -> None:
        self.client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        self.model = "claude-opus-4-6"

    # ------------------------------------------------------------------
    # Hook generation
    # ------------------------------------------------------------------

    def generate_hooks(self, topic: str, platform: str = "youtube") -> List[str]:
        """Generate 3 high-engagement hook candidates for the given topic."""
        pattern_list = "\n".join(f"- {p}" for p in HOOK_PATTERNS)

        prompt = f"""주제: {topic}
플랫폼: {platform.upper()}

아래 패턴 중 서로 다른 3가지를 골라 강력한 훅(Hook) 3개를 작성해라.
각 훅은 3초 이내에 시청자를 사로잡아야 하며, 짧고 강렬해야 한다.

[패턴 목록]
{pattern_list}

[출력 규칙]
- 반드시 아래 형식만 사용할 것
- 번호. 훅 내용 (한 줄)
- 설명 없이 훅만 출력

1. [훅 내용]
2. [훅 내용]
3. [훅 내용]"""

        logger.info("Claude: generating hooks...")
        response = self.client.messages.create(
            model=self.model,
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}],
        )

        raw = response.content[0].text
        hooks = self._parse_numbered_list(raw)

        if len(hooks) < 3:
            logger.warning(f"Expected 3 hooks, got {len(hooks)}. Raw: {raw!r}")

        return hooks[:3]

    # ------------------------------------------------------------------
    # Script generation
    # ------------------------------------------------------------------

    def generate_youtube_script(self, topic: str, hook: str) -> Dict:
        """Generate a 60-second Korean YouTube Shorts script."""
        prompt = f"""주제: {topic}
선택된 훅: {hook}

YouTube Shorts 스크립트를 작성해라.

[요구사항]
- 언어: 한국어
- 길이: 60초 (나레이션 기준 약 150~180 단어)
- 첫 3초: 선택된 훅으로 시작
- 문장은 짧게 (한 문장 15자 이내 권장)
- 자막 최적화된 표현
- 실행 가능한 팁 포함
- 개발자/기술 관점 우선

[출력 형식 – 반드시 이 구조를 지킬 것]

[스크립트]
(전체 나레이션 텍스트. 한 줄에 한 문장.)

[씬 분할]
씬1 (0-12초): 내용 요약
씬2 (12-24초): 내용 요약
씬3 (24-36초): 내용 요약
씬4 (36-48초): 내용 요약
씬5 (48-60초): 내용 요약

[자막]
(12초 단위로 자막 텍스트를 분리. 각 덩어리는 짧게.)
자막1:
자막2:
자막3:
자막4:
자막5:"""

        logger.info("Claude: generating YouTube script...")
        response = self.client.messages.create(
            model=self.model,
            max_tokens=1500,
            messages=[{"role": "user", "content": prompt}],
        )

        return self._parse_script(response.content[0].text)

    def generate_tiktok_script(self, topic: str, hook: str) -> Dict:
        """Generate a 30-second English TikTok script."""
        prompt = f"""Topic: {topic}
Selected Hook: {hook}

Write a TikTok script.

[Requirements]
- Language: English
- Length: 30 seconds (approx. 75–90 words for narration)
- First 3 seconds: start with the selected hook
- Short punchy sentences (≤10 words each)
- Subtitle-optimized phrasing
- Include one actionable tip
- Developer/tech angle preferred

[Output format – follow exactly]

[SCRIPT]
(Full narration text, one sentence per line.)

[SCENES]
Scene1 (0-10s): brief summary
Scene2 (10-20s): brief summary
Scene3 (20-30s): brief summary

[SUBTITLES]
(Split subtitles by ~10-second interval, keep each short.)
Sub1:
Sub2:
Sub3:"""

        logger.info("Claude: generating TikTok script...")
        response = self.client.messages.create(
            model=self.model,
            max_tokens=800,
            messages=[{"role": "user", "content": prompt}],
        )

        return self._parse_script(response.content[0].text)

    # ------------------------------------------------------------------
    # Parsing helpers
    # ------------------------------------------------------------------

    def _parse_numbered_list(self, text: str) -> List[str]:
        """Extract lines that start with '1.' / '2.' / '3.'"""
        results = []
        for line in text.splitlines():
            line = line.strip()
            match = re.match(r"^[1-9]\d*[.)]\s+(.+)$", line)
            if match:
                results.append(match.group(1).strip())
        return results

    def _parse_script(self, text: str) -> Dict:
        """Parse Claude's structured script response into a dict."""
        result: Dict = {
            "full_script": "",
            "scenes": [],
            "subtitles": [],
            "raw": text,
        }

        # Section markers (both Korean and English)
        section_re = re.compile(
            r"\[(스크립트|씬 분할|자막|SCRIPT|SCENES|SUBTITLES)\]",
            re.IGNORECASE,
        )

        current = None
        script_lines: List[str] = []
        scene_lines: List[str] = []
        subtitle_lines: List[str] = []

        for line in text.splitlines():
            stripped = line.strip()
            if not stripped:
                continue

            m = section_re.match(stripped)
            if m:
                tag = m.group(1).upper()
                if tag in ("스크립트", "SCRIPT"):
                    current = "script"
                elif tag in ("씬 분할", "SCENES"):
                    current = "scenes"
                elif tag in ("자막", "SUBTITLES"):
                    current = "subtitles"
                continue

            if current == "script":
                script_lines.append(stripped)
            elif current == "scenes":
                scene_lines.append(stripped)
            elif current == "subtitles":
                # Remove "자막N:" / "SubN:" prefix labels
                cleaned = re.sub(r"^(자막|Sub)\d+:\s*", "", stripped, flags=re.IGNORECASE)
                if cleaned:
                    subtitle_lines.append(cleaned)

        result["full_script"] = " ".join(script_lines)
        result["scenes"] = scene_lines
        result["subtitles"] = subtitle_lines

        # Fallback: if subtitles were not parsed, split the script
        if not result["subtitles"] and result["full_script"]:
            from utils.helpers import split_into_subtitles
            result["subtitles"] = split_into_subtitles(result["full_script"])

        return result
