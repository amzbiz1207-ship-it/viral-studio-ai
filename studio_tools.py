"""Catalog and transparent no-key work aids for Viral Studio AI v2.

No fabricated live analytics, no video or image rendering. Every fallback is a
local, rule-based draft; optional AI uses Gemini in the host app.
"""
from __future__ import annotations

from dataclasses import dataclass
from core import demo_script, sample_hooks


@dataclass(frozen=True)
class Recipe:
    slug: str
    group: str
    ru: str
    en: str
    ru_desc: str
    en_desc: str
    kind: str = "generate"
    route: str = ""


RECIPES = [
    Recipe("reels_script", "Content", "Сценарий Reels / Shorts", "Reels / Shorts script", "Хук, кадры по секундам, озвучка и CTA", "Hook, timestamped scenes, voiceover and CTA"),
    Recipe("content_studio", "Content", "Контент-студия", "Content studio", "Идея → концепция, сценарий, подпись и промпты", "Idea → concept, script, caption and prompts"),
    Recipe("plan_30", "Content", "Контент-план на 30 дней", "30-day content plan", "Темы, форматы и цели публикаций", "Daily topics, formats and goals"),
    Recipe("hooks_30", "Content", "30 цепляющих начал", "30 scroll-stopping hooks", "Вопросы, ошибки, контрасты, истории", "Questions, mistakes, contrasts and stories"),
    Recipe("profile_audit", "Content", "Аудит профиля", "Profile audit", "Проверка контента без вымышленных метрик", "Profile checklist without made-up analytics"),
    Recipe("bio", "Content", "Профиль, который привлекает", "Profile that converts", "Пять вариантов bio и структура профиля", "Five bio options and profile structure"),
    Recipe("audience", "Content", "Портрет аудитории", "Know your audience", "Гипотезы о зрителях и вопросы для проверки", "Audience hypotheses and validation questions"),
    Recipe("short_story", "Videos", "Короткая видеоистория", "Short video story", "Сюжет, монтажный ритм и промпты на сцены", "Narrative, pacing and prompts for scenes"),
    Recipe("montage", "Videos", "План монтажа из моих видео", "Edit my footage — plan", "План монтажа, музыка и субтитры — не готовый файл", "Editing plan, audio and subtitles — not a video file"),
    Recipe("ai_avatar", "Videos", "AI-аватар и говорящая голова", "AI avatar / talking head", "Сценарий и рекомендации для генератора видео", "Script and prompts for external video tools"),
    Recipe("unboxing", "Videos", "Распаковка продукта", "Product unboxing", "Раскадровка и кадры для вертикального видео", "Storyboard for a vertical product video"),
    Recipe("carousel_idea", "Carousels", "Карусель из идеи", "Carousel from idea", "Слайды, тексты, визуальный стиль", "Slide copy, structure and visual direction"),
    Recipe("carousel_story", "Carousels", "Карусель-история", "Story carousel", "Сюжет с неожиданным поворотом", "Narrative carousel with a twist"),
    Recipe("carousel_sales", "Carousels", "Продающая карусель", "Sales carousel", "Боль, решение, выгоды, призыв", "Problem, solution, proof and CTA"),
    Recipe("trends_youtube", "Trends", "Реальный поиск YouTube", "Live YouTube discovery", "Поиск по нише через официальный API", "Real public video data via official API", kind="navigate", route="trends"),
    Recipe("reels_teardown", "Trends", "Разбор чужого ролика", "Video teardown", "Анализ ссылки, метрик и добавленного текста", "Analyze link, available metrics and supplied text", kind="navigate", route="review"),
    Recipe("weekly_plan", "Trends", "План на неделю", "Weekly content calendar", "Редактируемые темы, статусы и сценарии", "Editable topics, statuses and scripts", kind="navigate", route="week"),
    Recipe("image_prompts", "Images", "Промпты для изображений", "Image prompt studio", "Визуальные концепции для внешних генераторов", "Image concepts for external generators"),
    Recipe("thumbnail", "Images", "Обложка Shorts / Reels", "Video thumbnail", "Композиция, заголовок и английский промпт", "Layout, headline and English image prompt"),
    Recipe("brand_background", "Images", "Фирменные фоны", "Brand backgrounds", "Три стилистики под свой канал", "Three background directions for your brand"),
    Recipe("product_photo", "Images", "Предметная фотосъёмка", "Product photoshoot", "Студийные кадры и единый визуальный стиль", "Studio-photo concepts and consistent styling"),
    Recipe("keyword_bot", "Chatbots", "Бот по ключевому слову", "Keyword reply bot", "Схема ответов на комментарии и сообщения", "Comment and DM reply flow specification"),
    Recipe("funnel", "Chatbots", "Сценарий воронки", "Funnel builder", "Ветвления, сообщения и согласие пользователя", "Branches, messages and user consent"),
    Recipe("faq_bot", "Chatbots", "FAQ-помощник", "FAQ assistant", "Список вопросов, ответы и эскалация человеку", "FAQ responses and human handoff"),
]
GROUPS = ["All", "Videos", "Carousels", "Trends", "Content", "Images", "Chatbots"]
CATALOG = {r.slug: r for r in RECIPES}


def title(slug: str, lang: str) -> str:
    r = CATALOG[slug]
    return r.ru if lang == "RU" else r.en


def route_request(message: str) -> str:
    t = message.casefold()
    for words, recipe in [
        (("youtube", "ютуб", "найди видео", "найти видео", "поиск ролик", "тренд", "viral video"), "trends_youtube"),
        (("разбор", "проанализируй видео", "анализ ролик", "teardown", "competitor"), "reels_teardown"),
        (("карусел", "carousel", "слайды", "слайд"), "carousel_idea"),
        (("30 дней", "30-day", "контент-план", "content plan", "календарь пост"), "plan_30"),
        (("неделю", "7 дней", "week", "weekly"), "weekly_plan"),
        (("хук", "первых фраз", "hooks", "hook"), "hooks_30"),
        (("аватар", "говорящ", "avatar", "talking head"), "ai_avatar"),
        (("монтаж", "смонтир", "edit footage", "montage"), "montage"),
        (("обложк", "thumbnail", "cover"), "thumbnail"),
        (("картин", "изображен", "image", "photo"), "image_prompts"),
        (("чатбот", "чат-бот", "бот", "chatbot", "funnel"), "keyword_bot"),
        (("профиль", "bio", "шапк", "profile"), "bio"),
        (("аудитори", "audience"), "audience"),
        (("истори", "story"), "short_story"),
    ]:
        if any(w in t for w in words):
            return recipe
    return "reels_script"


def ai_prompts(slug: str, idea: str, profile: dict, language: str) -> tuple[str, str]:
    """Prescriptive prompt that does not claim access to proprietary accounts/data."""
    if slug not in CATALOG:
        raise ValueError("Unknown recipe")
    p = profile
    lang = "Russian" if language == "RU" else "English"
    system = (
        "You are an experienced social-video producer and practical editor. "
        "Create original, detailed, immediately usable content. "
        f"Respond in {lang} except visual/video GENERATION PROMPTS, which must always be in English. "
        f"Creator niche: {p.get('niche','not specified')}. Audience: {p.get('audience','not specified')}. "
        f"Voice: {p.get('tone','not specified')}. Platform: {p.get('platform','not specified')}. "
        f"Duration: {p.get('duration',30)} seconds. Goal: {p.get('goal','not specified')}. "
        "Do not fabricate real competitor data, published videos, account metrics, quotes, study findings, "
        "trend status, external tool actions, or claimed performance. Mark speculative claims as hypotheses. "
        "Do not promise virality. Do not repeat proprietary marketing copy. "
        "Use clean markdown. If important inputs are absent, state assumptions explicitly. "
        "For video: 9:16; provide close-ups, concrete actions and no repeated approach shots. "
        "For Flow-like generation, split prompts into independent max-8-second clips. "
    )
    directives = {
        "reels_script": "5 distinct hook styles; complete timed scene table with visual, voiceover, on-screen copy and CTA; English generation prompts per clip.",
        "content_studio": "3 creative concepts, choose the strongest with rationale, produce 1 full short script, 5 hooks, caption, hashtags, 9:16 visual prompts, and posting checklist.",
        "plan_30": "Create EXACTLY 30 specific, unique daily ideas in a markdown table: day, topic, video or carousel format, hook, purpose. These are proposals, not claimed live trends.",
        "hooks_30": "Create EXACTLY 30 genuinely distinct, concise 1-3s hooks grouped by question, visual tension, misconception, contrast, specificity and relatable moment. Include filming instructions.",
        "profile_audit": "Audit only user-provided profile facts. If no accessible profile metrics, state that limitation. Return a practical checklist with evidence vs hypotheses and a 14-day improvement plan.",
        "bio": "Provide 5 distinct social-bio options, profile picture advice, highlights/pinned content plan, clear conversion-friendly CTA. Avoid invented qualifications.",
        "audience": "Provide 3 audience hypotheses, triggers, content needs, what evidence would validate them, and 10 audience interview questions.",
        "short_story": "Write realistic, humorous or educational short film: opening, twist, shot-by-shot timeline, sound design, natural dialogue, English 8-second video prompts and continuity notes.",
        "montage": "Plan editing of user footage based only on footage described in text; do not claim to have edited or viewed files. Provide cut list, pacing, music cues, captions and handoff instructions.",
        "ai_avatar": "Write 25-35 second presenter script, 5 hooks, expression/gesture directions, 3 camera setups, English generation prompts and authenticity caveats.",
        "unboxing": "Make an 18-30s realistic vertical unboxing storyboard, sound beats, 5 tight shots, smooth transitions, product photography prompt and caption.",
        "carousel_idea": "Write 8-slide carousel with exact slide text, engagement-driven progression, practical visual descriptions and 8 English image prompts with cohesive style.",
        "carousel_story": "Write 8-slide engaging narrative carousel; relatable hook, suspense, reveal, takeaway; exact on-slide copy and visual descriptions.",
        "carousel_sales": "Write 8-slide persuasive but truthful sales carousel with pain, mechanism, key benefits, grounded proof placeholders and one CTA. No made-up results.",
        "image_prompts": "Provide 5 detailed English prompts for image generators for this creator's idea; lighting, framing, 9:16 ratio, consistent subject and negative constraints. Do not claim images were generated.",
        "thumbnail": "Provide three thumbnail concepts: short readable headline, visual hierarchy, color direction, and detailed English image prompts. Do not claim image created.",
        "brand_background": "Propose three coherent brand backgrounds with English image prompts and design usage notes; avoid accidental text in generated images.",
        "product_photo": "Propose 4 premium product studio scenes with English prompts; consistency, lighting, props, camera and truthful product representation.",
        "keyword_bot": "Draft a platform-agnostic keyword-response bot specification with trigger, opt-in, reply, FAQ, human handoff, privacy safeguards. Do not pretend it is deployed.",
        "funnel": "Draft an ethical lead funnel with 3-5 steps, branching rules, messages, consent and opt-out, measurements and human handoff. Do not pretend it is deployed.",
        "faq_bot": "Draft FAQ bot content, intent table, suggested responses, fallback, escalation and privacy practices. Do not pretend it is deployed.",
    }
    return system, (f"Tool: {title(slug, language)}. User idea/background: {idea}. " + directives.get(slug, "Create a useful original deliverable."))


def _hook_draft(topic: str, lang: str) -> str:
    pairs = sample_hooks(topic, "creator", lang)
    return "\n".join(f"- **{label}** — {hook}" for label, hook in pairs)


def _calendar(topic: str, lang: str) -> str:
    angles_ru = [
        "Миф и реальность", "Что происходит внутри", "Ошибка новичка", "Один крупный план", "До и после", "Три важных факта",
        "Вопрос подписчика", "Неожиданный ракурс", "Всё за 15 секунд", "История из жизни", "Как это работает", "Сравнение двух способов",
        "Честный эксперимент", "Разбираем пример", "Главная деталь", "Факт или заблуждение", "Самая частая проблема", "Быстрый разбор",
        "Мини-инструкция", "Реакция зрителя", "Кейс без приукрашивания", "Один полезный совет", "Секрет процесса", "Путь от А к Б",
        "5 вопросов", "Ошибки за 30 секунд", "Визуальное объяснение", "Что случится, если...", "Короткий тест", "Итоги и лучший момент",
    ]
    angles_en = [
        "Myth vs reality", "Inside the process", "A beginner mistake", "One revealing close-up", "Before and after", "Three useful facts",
        "Audience question", "A new perspective", "Explained in 15 seconds", "Everyday story", "How it works", "Two methods compared",
        "Honest experiment", "One example explained", "The crucial detail", "Fact or misconception", "Most common problem", "Quick breakdown",
        "Mini tutorial", "Viewer reaction", "Grounded real-world case", "One practical tip", "Process secrets", "From A to B",
        "Five questions", "Common pitfalls in 30s", "Visual explanation", "What happens if...", "Quick test", "Month recap",
    ]
    angles = angles_ru if lang == "RU" else angles_en
    head = "День | Формат | Предложенная тема | Цель" if lang == "RU" else "Day | Format | Proposed topic | Goal"
    rows = [f"| {head.replace(' | ', ' | ')} |", "|---|---|---|---|"]
    for i, angle in enumerate(angles, 1):
        typ = "Shorts / Reels" if i % 5 else "Carousel"
        goal = ("Объяснить" if i % 3 else "Вовлечь") if lang == "RU" else ("Explain" if i % 3 else "Engage")
        rows.append(f"| {i} | {typ} | {angle}: {topic} | {goal} |")
    return "\n".join(rows)


def fallback_draft(slug: str, idea: str, profile: dict, language: str) -> str:
    """A local, clearly-labeled editable skeleton, never framed as AI or actual trend analytics."""
    if slug not in CATALOG:
        raise ValueError("Unknown recipe")
    if CATALOG[slug].kind == "navigate":
        raise ValueError("This tool opens a dedicated page")
    topic = idea.strip() or profile.get("niche", "your idea")
    ru = language == "RU"
    prefix = "*Черновик без подключения ИИ. Заполни конкретными фактами — статистика и тренды не проверялись.*\n\n" if ru else "*Editable non-AI draft. Add verified facts; live metrics and trends were not checked.*\n\n"
    heading = f"## {title(slug, language)} — {topic}\n\n"
    if slug == "plan_30":
        return heading + prefix + _calendar(topic, language)
    if slug == "hooks_30":
        seeds = [
            "Знаете ли вы, почему…?", "Посмотрите на эту деталь", "Обычно мы ошибаемся вот здесь", "Сравним два варианта",
            "За 15 секунд покажу принцип", "Попробуем на простом примере", "Чего мы не замечаем?", "Всё начинается с…",
            "Вот неожиданный момент", "Проверим популярный миф", "Один вопрос меняет взгляд", "Два кадра — вся разница",
            "Что происходит дальше?", "Не пропустите этот этап", "Почему это важно?", "Сначала кажется, что…",
            "Видели такое раньше?", "Давайте заглянем внутрь", "Ошибка №1 — это…", "Покажу по шагам",
            "А теперь крупный план", "Вот как это выглядит на самом деле", "А что, если наоборот?", "Секунда до результата",
            "Этого никто не ожидает", "Проверим вместе", "Самый простой способ понять", "Как отличить одно от другого?",
            "Вот короткий ответ", "Сохраните этот пример",
        ] if ru else [
            "Have you ever wondered why…?", "Look at this detail", "Here's where people go wrong", "Let's compare two versions",
            "Here's the core idea in 15s", "Watch this simple example", "What are we missing?", "It starts with…",
            "Now watch the unexpected part", "Let's test a common myth", "One question changes everything", "Two frames reveal the difference",
            "What happens next?", "Don't miss this step", "Why does it matter?", "It looks simple at first…",
            "Seen this before?", "Let's look inside", "Mistake number one is…", "Here's the step-by-step",
            "Now zoom in", "This is what it actually looks like", "What if we tried the opposite?", "One second before the reveal",
            "Nobody expects this moment", "Let's check together", "An easier way to understand it", "How do you tell these apart?",
            "Here's the short answer", "Save this example",
        ]
        return heading + prefix + "\n".join(f"{i}. **{seed}** — {topic}" for i,seed in enumerate(seeds,1))
    if slug in {"reels_script", "content_studio", "short_story", "unboxing", "ai_avatar", "montage"}:
        b = demo_script(topic, profile.get("niche",""), language, profile.get("duration",30))
        details = ("\n\n### Монтаж\n- Ракурс 9:16; каждая сцена короткая и меняет информацию.\n- Длинные кадры из Google Flow разделить на клипы до 8 секунд.\n- Субтитры и озвучку добавлять отдельно.\n- Видео этим шаблоном не создаётся."
                   if ru else "\n\n### Production notes\n- 9:16 frame, purposeful concise cuts.\n- Keep Flow-compatible clips at 8 seconds or less.\n- Add subtitles and voiceover separately.\n- This draft does not render video.")
        return heading + prefix + "### 5 hooks\n" + _hook_draft(topic, language) + "\n\n" + b + details
    if slug.startswith("carousel"):
        slides_ru = [
            ("Титульный слайд", f"{topic}: что стоит знать?"),
            ("Проблема", "Что часто остаётся непонятным?"),
            ("Контекст", "Один короткий пример из жизни"),
            ("Объяснение", "Главный принцип — в 1–2 предложениях"),
            ("Доказательство", "Добавь проверенный факт или собственный пример"),
            ("Полезный шаг", "Что зритель может попробовать сегодня"),
            ("Итог", "Повтори главную мысль простыми словами"),
            ("Призыв", "Сохраните или расскажите о своём опыте"),
        ]
        slides_en = [
            ("Cover", f"{topic}: what matters most?"),
            ("Problem", "What people often misunderstand"),
            ("Context", "One concrete everyday example"),
            ("Explanation", "Core insight in 1–2 lines"),
            ("Proof", "Insert a verified fact or your own example"),
            ("Action", "One thing to try today"),
            ("Takeaway", "Restate the most useful idea"),
            ("CTA", "Save or share your experience"),
        ]
        slides = slides_ru if ru else slides_en
        return heading + prefix + "\n".join(f"### {i}. {name}\n{copy}\n\n**Visual prompt (EN):** Vertical 4:5 premium editorial design, single clear subject illustrating '{topic}', visual continuity across a carousel, high contrast, space for overlay text, no baked-in text.\n" for i,(name,copy) in enumerate(slides,1))
    if slug in {"image_prompts", "thumbnail", "brand_background", "product_photo"}:
        styles = [("Editorial", "soft studio daylight, balanced editorial composition"), ("Cinematic", "dramatic directional side light, careful depth of field"), ("Clean studio", "seamless background, realistic sharp product texture"), ("Lifestyle", "believable everyday context, natural tactile details"), ("Macro", "macro close-up with accurate surface details")]
        prompts = [f"**{style}:** Realistic vertical 9:16 photograph of {topic}, {lighting}, premium composition, physically coherent details, consistent subject and colors, no logos unless supplied by user, no watermark, no text generated inside image." for style,lighting in styles]
        intro = "*Готовые английские промпты для внешнего генератора. Изображения здесь не создаются.*\n\n" if ru else "*English prompts for an external generator; this does not create images.*\n\n"
        return heading + prefix + intro + "\n\n".join(prompts)
    if slug in {"keyword_bot", "funnel", "faq_bot"}:
        if ru:
            return heading + prefix + ("### Схема (для будущего подключения через официальный API)\n1. Триггер: пользователь добровольно пишет ключевое слово.\n2. Ответ: «Привет! Вот материал по теме: [ссылка]».\n3. Уточнение: «Хочешь получить ещё один полезный пример?»\n4. При согласии: отправить соответствующий материал.\n5. Если вопрос сложный: передать человеку.\n6. Команда «Стоп»: прекратить сообщения.\n\n**Важно:** это техническое задание, а не запущенный бот. Массовые рассылки и ответы без согласия не настроены.")
        return heading + prefix + ("### Flow specification (requires an authorized platform integration)\n1. Trigger: follower voluntarily sends a keyword.\n2. Reply: 'Hi! Here's the resource you asked for: [link].'\n3. Follow-up: 'Would you like an additional example?'\n4. Send relevant content only on affirmative response.\n5. Escalate complex questions to a human.\n6. Respect STOP / opt-out.\n\n**Note:** Specification only; no active bot or unsolicited messaging.")
    if slug in {"profile_audit", "bio", "audience"}:
        if ru:
            return heading + prefix + ("### Предварительные рекомендации\n- Определи одно конкретное обещание канала (какую пользу получает зритель).\n- Закрепи 3 ролика: знакомство, лучший обучающий пример, ответ на частый вопрос.\n- Добавь короткую шапку профиля: «[Для кого] — [о чём] — [зачем подписываться]».\n- Проверь на реальных данных удержание, досмотры и переходы в профиль.\n- Подготовь 5 вопросов своей аудитории, чтобы не гадать о её интересах.\n\n**Метрики пока не анализировались:** подключение аккаунта или ручная загрузка данных потребуется отдельно.")
        return heading + prefix + ("### Initial recommendations\n- Express a clear audience promise.\n- Pin 3 videos: introduction, useful example, common question.\n- Bio: '[Who it's for] — [What you cover] — [Why follow]'.\n- Validate hypotheses using real retention, completion and profile-visit data.\n- Ask the audience 5 direct questions before assuming preferences.\n\n**Metrics have not been reviewed:** connect authorized data or provide exports.")
    return heading + prefix + ("Заполни описание идеи и доработай этот план с Gemini." if ru else "Add your idea and refine this outline with Gemini.")
