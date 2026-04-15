"""
AI 숏폼 영상 생성 시스템 – 메인 진입점
=========================================

실행 흐름
---------
1. 주제 / 플랫폼 / 스타일 입력
2. 훅 3개 생성 → 사용자 선택
3. 스크립트 생성 → 사용자 검토
4. 썸네일 생성
5. TTS 음성 생성
6. 영상 생성 (720p 최적화)
7. Notion 저장

사용 예
-------
    python main.py
    python main.py --topic "파이썬 비동기" --platform youtube --style text
"""

import argparse
import os
import sys

from dotenv import load_dotenv

from services import ClaudeService, NotionService, ThumbnailService, TTSService, VideoService
from utils import CacheManager, get_logger, safe_filename, setup_logger

# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------

load_dotenv()
setup_logger()
logger = get_logger()

SUPPORTED_PLATFORMS = ("youtube", "tiktok", "both")
SUPPORTED_STYLES = ("text", "avatar")


# ---------------------------------------------------------------------------
# Input helpers
# ---------------------------------------------------------------------------


def prompt(message: str, default: str = "") -> str:
    """Read a line from stdin, falling back to *default*."""
    suffix = f" [{default}]" if default else ""
    try:
        value = input(f"{message}{suffix}: ").strip()
        return value if value else default
    except (EOFError, KeyboardInterrupt):
        print()
        return default


def choose_from_list(items: list, label: str = "선택") -> int:
    """Ask the user to pick an item by number; return 0-based index."""
    while True:
        raw = prompt(f"{label} (1-{len(items)})")
        try:
            idx = int(raw) - 1
            if 0 <= idx < len(items):
                return idx
        except ValueError:
            pass
        print(f"  ⚠  1~{len(items)} 사이의 숫자를 입력하세요.")


def confirm(message: str = "이대로 진행하시겠습니까?") -> bool:
    answer = prompt(f"{message} (y/n)", default="y").lower()
    return answer in ("y", "yes", "")


# ---------------------------------------------------------------------------
# Core pipeline
# ---------------------------------------------------------------------------


def run_pipeline(
    topic: str,
    platform: str,
    style: str,
    claude: ClaudeService,
    tts: TTSService,
    video_svc: VideoService,
    thumbnail_svc: ThumbnailService,
    notion: NotionService,
    cache: CacheManager,
) -> dict:
    """
    Execute the full generation pipeline for one platform.

    Returns a dict with paths to generated files.
    """
    outputs: dict = {}
    slug = safe_filename(topic)
    lang = "korean" if platform == "youtube" else "english"

    print(f"\n{'='*55}")
    print(f"  플랫폼: {platform.upper()}  |  스타일: {style}")
    print(f"{'='*55}")

    # ── Step 1: Hook generation ────────────────────────────────────────
    print("\n[1/6] 훅 생성 중...")

    hooks = cache.get(topic, platform, "hooks")
    if hooks:
        print("  (캐시에서 로드)")
    else:
        hooks = claude.generate_hooks(topic, platform)
        cache.set(hooks, topic, platform, "hooks")

    print("\n[훅 후보]")
    for i, h in enumerate(hooks, 1):
        print(f"  {i}. {h}")

    hook_idx = choose_from_list(hooks, "훅 선택")
    selected_hook = hooks[hook_idx]
    print(f"  ✔ 선택된 훅: {selected_hook}")

    # ── Step 2: Script generation ──────────────────────────────────────
    print("\n[2/6] 스크립트 생성 중...")

    cache_key_parts = (topic, platform, "script", selected_hook)
    script_data = cache.get(*cache_key_parts)
    if script_data:
        print("  (캐시에서 로드)")
    else:
        if platform == "youtube":
            script_data = claude.generate_youtube_script(topic, selected_hook)
        else:
            script_data = claude.generate_tiktok_script(topic, selected_hook)
        cache.set(script_data, *cache_key_parts)

    print("\n[생성된 스크립트]")
    print("-" * 50)
    print(script_data["full_script"])
    print("-" * 50)

    # ── Step 3: User review ────────────────────────────────────────────
    print("\n[3/6] 스크립트 검토")
    if not confirm():
        new_script = prompt("수정된 스크립트를 입력하세요 (Enter로 기존 유지)")
        if new_script:
            script_data["full_script"] = new_script
            cache.invalidate(*cache_key_parts)

    # ── Step 4: Thumbnail ──────────────────────────────────────────────
    print("\n[4/6] 썸네일 생성 중...")
    thumb_path = thumbnail_svc.generate_thumbnail(
        topic=topic,
        hook=selected_hook,
        filename=f"{slug}_thumbnail.png",
    )
    outputs["thumbnail"] = thumb_path
    print(f"  ✔ 썸네일 → {thumb_path}")

    # ── Step 5: TTS ────────────────────────────────────────────────────
    print("\n[5/6] 음성 생성 중...")
    audio_filename = f"{slug}_{platform}_audio.mp3"
    audio_path = tts.generate_audio(
        text=script_data["full_script"],
        language=lang,
        filename=audio_filename,
        speed=1.1,
    )
    outputs["audio"] = audio_path
    print(f"  ✔ 음성 → {audio_path}")

    # ── Step 6: Video rendering ────────────────────────────────────────
    print("\n[6/6] 영상 생성 중... (시간이 걸릴 수 있습니다)")

    if style == "avatar":
        logger.warning("Avatar 스타일은 HeyGen API 연동 후 사용 가능합니다. text 모드로 전환합니다.")

    video_filename = f"{platform}.mp4"
    video_path = video_svc.generate_video(
        audio_path=audio_path,
        subtitles=script_data.get("subtitles", []),
        platform=platform,
        filename=video_filename,
        script_text=script_data["full_script"],
    )
    outputs["video"] = video_path
    print(f"  ✔ 영상 → {video_path}")

    # ── Step 7: Notion ─────────────────────────────────────────────────
    print("\n[7/7] Notion 저장 중...")
    saved = notion.save_content(
        topic=topic,
        hook=selected_hook,
        script=script_data["full_script"],
        platform=platform,
    )
    if saved:
        print("  ✔ Notion 저장 완료")
    else:
        print("  ⚠  Notion 저장 건너뜀 (토큰/DB ID 미설정 또는 오류)")

    outputs["hook"] = selected_hook
    outputs["script"] = script_data["full_script"]
    return outputs


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="AI 숏폼 영상 생성 시스템",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--topic", type=str, help="생성할 주제")
    parser.add_argument(
        "--platform",
        choices=SUPPORTED_PLATFORMS,
        default=None,
        help="플랫폼 선택 (youtube | tiktok | both)",
    )
    parser.add_argument(
        "--style",
        choices=SUPPORTED_STYLES,
        default="text",
        help="영상 스타일 (text | avatar)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    print("\n" + "=" * 55)
    print("   AI 숏폼 영상 자동 생성 시스템")
    print("=" * 55)

    # ── Gather inputs ──────────────────────────────────────────────────
    topic = args.topic or prompt("주제를 입력하세요 (예: 파이썬 비동기 프로그래밍)")
    if not topic:
        print("주제를 입력해야 합니다.")
        sys.exit(1)

    platform_input = args.platform or prompt(
        "플랫폼 선택", default="both"
    ).lower()
    if platform_input not in SUPPORTED_PLATFORMS:
        platform_input = "both"

    style = args.style or prompt("스타일 선택 (text/avatar)", default="text").lower()
    if style not in SUPPORTED_STYLES:
        style = "text"

    # ── Initialise services ────────────────────────────────────────────
    try:
        claude = ClaudeService()
    except KeyError:
        print("\n❌  ANTHROPIC_API_KEY 가 설정되지 않았습니다. .env 파일을 확인하세요.")
        sys.exit(1)

    tts = TTSService(output_dir="output")
    video_svc = VideoService(assets_dir="assets", output_dir="output")
    thumbnail_svc = ThumbnailService(output_dir="output")
    notion = NotionService()
    cache = CacheManager()

    # ── Run pipeline ───────────────────────────────────────────────────
    platforms = ["youtube", "tiktok"] if platform_input == "both" else [platform_input]
    all_outputs: dict = {}

    for plt in platforms:
        try:
            result = run_pipeline(
                topic=topic,
                platform=plt,
                style=style,
                claude=claude,
                tts=tts,
                video_svc=video_svc,
                thumbnail_svc=thumbnail_svc,
                notion=notion,
                cache=cache,
            )
            all_outputs[plt] = result
        except KeyboardInterrupt:
            print("\n\n⚠  사용자가 중단했습니다.")
            sys.exit(0)
        except Exception as exc:
            logger.error(f"{plt.upper()} 파이프라인 오류: {exc}", exc_info=True)
            print(f"\n❌  {plt.upper()} 생성 중 오류 발생: {exc}")

    # ── Summary ────────────────────────────────────────────────────────
    print("\n" + "=" * 55)
    print("   생성 완료 요약")
    print("=" * 55)
    for plt, out in all_outputs.items():
        print(f"\n  [{plt.upper()}]")
        print(f"  영상      : {out.get('video', '-')}")
        print(f"  썸네일    : {out.get('thumbnail', '-')}")
        print(f"  음성      : {out.get('audio', '-')}")
        print(f"  선택된 훅 : {out.get('hook', '-')}")
    print()


if __name__ == "__main__":
    main()
