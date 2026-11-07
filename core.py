"""Pure helpers for Viral Studio AI. No network and no secrets."""
from __future__ import annotations
from datetime import datetime, timezone
from urllib.parse import parse_qs, urlparse
import re

DAYS_RU = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
DAYS_EN = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def youtube_id(url: str) -> str | None:
    """Extract an eleven-character YouTube ID from supported public YouTube links."""
    try:
        p = urlparse(url.strip())
        host = (p.hostname or "").lower()
        if host in {"youtu.be", "www.youtu.be"}:
            candidate = p.path.strip("/").split("/")[0]
        elif host in {"youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com"}:
            chunks = [x for x in p.path.split("/") if x]
            if p.path == "/watch":
                candidate = parse_qs(p.query).get("v", [""])[0]
            elif chunks and chunks[0] in {"shorts", "embed", "live", "v"} and len(chunks) > 1:
                candidate = chunks[1]
            else:
                return None
        else:
            return None
        return candidate if re.fullmatch(r"[A-Za-z0-9_-]{11}", candidate or "") else None
    except (ValueError, AttributeError):
        return None


def format_num(number: int | str | None) -> str:
    try:
        n = int(number or 0)
    except (ValueError, TypeError):
        return "—"
    if n >= 1_000_000:
        return f"{n/1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n/1_000:.1f}K"
    return str(n)


def iso_duration(value: str | None) -> int:
    match = re.fullmatch(r"P(?:\d+D)?T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", value or "")
    if not match:
        return 0
    h, m, s = (int(x or 0) for x in match.groups())
    return h * 3600 + m * 60 + s


def days_since(published: str | None) -> float:
    try:
        dt = datetime.fromisoformat((published or "").replace("Z", "+00:00"))
        return max(1.0, (datetime.now(timezone.utc) - dt).total_seconds() / 86400)
    except ValueError:
        return 1.0


def sample_hooks(topic: str, niche: str, lang: str) -> list[tuple[str, str]]:
    t = topic.strip() or ("эта тема" if lang == "RU" else "this topic")
    if lang == "RU":
        return [
            ("Вопрос", f"А вы знаете, что на самом деле происходит, когда {t.lower()}?"),
            ("Ошибка", f"Большинство неправильно понимает тему «{t}»."),
            ("Сцена", f"Представьте: прямо сейчас перед вами — «{t}»."),
            ("Конкретика", f"За 30 секунд покажу главное про «{t}»."),
            ("Неожиданность", f"Самое удивительное в теме «{t}» — не то, что кажется."),
        ]
    return [
        ("Question", f"Do you know what really happens when we look at {t.lower()}?"),
        ("Mistake", f"Most people misunderstand this about {t}."),
        ("Scene", f"Picture this: you're watching {t} unfold up close."),
        ("Specific", f"Here's what matters about {t} in 30 seconds."),
        ("Surprise", f"The most surprising thing about {t} isn't what you think."),
    ]


def demo_script(topic: str, niche: str, lang: str, duration: int = 30) -> str:
    """Rule-based writing aid, intentionally labeled as a TEMPLATE rather than AI output."""
    hook = sample_hooks(topic, niche, lang)[0][1]
    duration = max(12, min(int(duration), 60))
    a, b, c = 3, round(duration * 0.35), round(duration * 0.7)
    if lang == "RU":
        return (f"### Шаблон сценария: {topic}\n\n"
                f"**0–{a} с · Хук:** {hook}\n\n"
                f"**Кадр:** крупный план главного объекта. **Текст на экране:** «Посмотрите ближе».\n\n"
                f"**{a}–{b} с · Контекст:** Покажите исходное состояние. В озвучке объясните, почему это важно вашей аудитории ({niche}).\n\n"
                f"**{b}–{c} с · Демонстрация:** Покажите процесс крупным планом, без повторов; добавьте проверенный факт или конкретный пример.\n\n"
                f"**{c}–{duration} с · Финал:** Короткий вывод и призыв: «Сохраните, чтобы не забыть».\n\n"
                "**Для генератора видео (EN prompt):** Vertical 9:16, realistic documentary style, clear close-ups, purposeful quick cuts, consistent lighting, no captions rendered in the footage, no fantasy elements.\n\n"
                "*Это редактируемый шаблон, не проверенная аналитика трендов и не генерация ИИ.*")
    return (f"### Script template: {topic}\n\n"
            f"**0–{a}s · Hook:** {hook}\n\n"
            "**Visual:** a clear, close-up view of the main subject. **On-screen text:** “Look closer.”\n\n"
            f"**{a}–{b}s · Context:** Show the starting state and explain why this matters to your audience ({niche}).\n\n"
            f"**{b}–{c}s · Demonstration:** Show the process up close, with no repeated approach shots. Add one verified fact or concrete example.\n\n"
            f"**{c}–{duration}s · Finish:** Summarize and invite viewers to save the clip.\n\n"
            "**Video generation prompt:** Vertical 9:16, realistic documentary style, clear close-ups, purposeful quick cuts, consistent lighting, no captions rendered in footage, no fantasy elements.\n\n"
            "*Editable template only: not an AI-generated script or verified trend analysis.*")


def demo_week(niche: str, lang: str) -> list[dict]:
    if lang == "RU":
        topics = [
            f"Самый неожиданный факт о теме «{niche}»",
            f"Три ошибки новичка: {niche}",
            f"Как это устроено: {niche}",
            f"Миф или правда: {niche}",
            f"Один процесс изнутри: {niche}",
            f"Вопрос подписчика о теме «{niche}»",
            f"Самое интересное за неделю: {niche}",
        ]
    else:
        topics = [
            f"The most surprising fact about {niche}",
            f"Three beginner mistakes in {niche}",
            f"How it works: {niche}",
            f"Myth vs reality: {niche}",
            f"Inside a process: {niche}",
            f"A viewer question about {niche}",
            f"The week's most interesting insight in {niche}",
        ]
    return [{"day": i, "topic": title, "format": "Shorts / Reels", "status": "planned"} for i, title in enumerate(topics)]


def data_export(projects: dict, current: str, library: list, videos: list) -> dict:
    return {"schema": 1, "projects": projects, "current": current, "library": library, "videos": videos}
