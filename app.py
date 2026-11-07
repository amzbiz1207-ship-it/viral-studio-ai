"""Viral Studio AI — independent Streamlit prototype, RU/EN."""
from __future__ import annotations
import json
import os
import hmac
from html import escape as safe_html
from datetime import datetime
from pathlib import Path
import streamlit as st
from core import DAYS_RU, DAYS_EN, sample_hooks, demo_script, demo_week, format_num, youtube_id, data_export
from services import ApiError, get_youtube_video, search_youtube, gemini_generate
from studio_tools import RECIPES, CATALOG, GROUPS, title as recipe_title, route_request, fallback_draft, ai_prompts

st.set_page_config(page_title="Viral Studio AI", page_icon="🎬", layout="wide", initial_sidebar_state="expanded")

# Personal access gate. Set APP_PASSWORD only in Streamlit Community Cloud > App settings > Secrets.
# There is intentionally no fallback or hard-coded demo password.
def _get_app_password() -> str:
    try:
        configured = st.secrets.get("APP_PASSWORD", "")
    except (FileNotFoundError, OSError):
        configured = ""
    return str(configured or os.environ.get("APP_PASSWORD", ""))


_APP_PASSWORD = _get_app_password()
if not _APP_PASSWORD:
    st.error(
        "🔒 Доступ закрыт: администратор пока не добавил APP_PASSWORD в Secrets. "
        "Access locked: configure APP_PASSWORD in Streamlit Secrets."
    )
    st.stop()

if not st.session_state.get("_viral_authenticated", False):
    st.markdown("## 🎬 Viral Studio AI")
    st.subheader("🔒 Личный вход / Private access")
    st.caption("Для работы с приложением введите личный пароль. / Enter your password.")
    with st.form("viral_private_login"):
        entered_password = st.text_input("Пароль / Password", type="password")
        login_clicked = st.form_submit_button("Войти / Sign in", type="primary")
    if login_clicked:
        if hmac.compare_digest(entered_password.encode("utf-8"), _APP_PASSWORD.encode("utf-8")):
            st.session_state["_viral_authenticated"] = True
            st.rerun()
        else:
            st.error("Неверный пароль / Incorrect password")
    st.stop()


CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700;800&display=swap');
:root {color-scheme: dark;}
html,body,[class*="css"],.stApp {font-family:'DM Sans',sans-serif;}
.stApp {background:radial-gradient(ellipse at 75% -12%, #263250 0, #0d1320 40%, #0a101b 78%); color:#eaf0f8;}
[data-testid="stSidebar"] {background:#0a1020; border-right:1px solid #293146;}
h1,h2,h3 {letter-spacing:-.035em;}
h1 {font-weight:800!important;} h3 {font-weight:700!important;}
.stButton>button[kind="primary"],.stDownloadButton>button[kind="primary"] {background:linear-gradient(90deg,#a3fad1,#77d9db);border:0;color:#091824;font-weight:800;}
.stButton>button {border-radius:12px;}
[data-testid="stMetric"] {background:#151e30;border:1px solid #303c54;border-radius:16px;padding:18px;}
[data-testid="stMetricValue"]{color:#a3fad1;}
[data-testid="stExpander"] {border:1px solid #28364b; border-radius:12px; background:#111928;}
.stTextInput input,.stTextArea textarea {background:#121c2b!important;}
.v-hero{background:linear-gradient(115deg,#1e3348,#17213a 65%,#253454);border:1px solid #3b4b63;border-radius:24px;padding:30px 34px;margin-bottom:24px;}
.v-kicker{color:#a3fad1;font-size:12px;letter-spacing:.18em;font-weight:800;text-transform:uppercase;}
.v-hero h1{font-size:40px;line-height:1.12;margin:7px 0 12px;}
.v-hero p{color:#cad4e5;font-size:16px;margin:0;}
.v-card{background:#141d2c;border:1px solid #303e50;border-radius:18px;padding:22px;margin:8px 0 18px;min-height:118px;}
.v-card h3{margin:0 0 12px;font-size:19px;}.v-card p{margin:4px 0;color:#c4cddd;}
.v-tag{display:inline-block;background:#203c40;color:#a4f5ce;font-size:12px;padding:5px 10px;border-radius:99px;letter-spacing:.01em;margin:0 5px 8px 0;}
.v-muted{color:#8c9bb2;font-size:13px;}
.v-line{border-top:1px solid #26334c;margin:18px 0;}

.studio-hero{background:radial-gradient(circle at 87% 0,#226e74 0,transparent 36%),linear-gradient(110deg,#111d30,#19293a 65%,#153c45);border:1px solid #34515e;border-radius:23px;padding:35px;margin:14px 0 13px;}
.studio-kicker{font-size:12px;font-weight:800;letter-spacing:.19em;color:#9bf3d9;}
.studio-hero h1{font-size:clamp(31px,4vw,47px);letter-spacing:-.045em;line-height:1.1;margin:12px 0 15px;max-width:750px;color:#f7fbff;}
.studio-hero p{color:#d2dfe9;font-size:16px;line-height:1.5;max-width:720px;margin:0;}
.studio-tile{margin:8px 0 7px;min-height:142px;border:1px solid #334b59;border-radius:16px;padding:17px 17px 12px;background:linear-gradient(155deg,#1c2839,#111b2b);}
.studio-category{display:inline-block;font-size:10px;font-weight:800;letter-spacing:.12em;text-transform:uppercase;color:#93e6d2;margin-bottom:10px;}
.studio-tiletitle{font-size:17px;font-weight:800;line-height:1.28;color:#f6fbfe;}
.studio-tiledesc{margin-top:7px;font-size:13px;line-height:1.35;color:#a9bcca;}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

S = st.session_state
if "projects" not in S:
    S.projects = {"My channel": {"niche":"How things work / Как это устроено", "audience":"Curious viewers aged 12+", "tone":"Clear, lively, scientifically accurate", "platform":"YouTube Shorts", "goal":"More organic views", "language":"EN", "duration":30, "handle":"", "week":[], "members":[]}}
if "current" not in S: S.current = "My channel"
if "library" not in S: S.library = []
if "videos" not in S: S.videos = []
if "results" not in S: S.results = []
if "script" not in S: S.script = ""
if "script_title" not in S: S.script_title = ""
if "review" not in S: S.review = ""
if "selected_topic" not in S: S.selected_topic = ""
if "page" not in S: S.page = "studio"
if "studio_recipe" not in S: S.studio_recipe = "reels_script"
if "studio_output" not in S: S.studio_output = ""
if "studio_output_type" not in S: S.studio_output_type = ""
if "studio_group" not in S: S.studio_group = "All"


def tr(ru: str, en: str) -> str:
    return ru if S.ui_lang == "RU" else en


def secret(name: str) -> str:
    try:
        return str(st.secrets.get(name, os.environ.get(name, "")))
    except (FileNotFoundError, AttributeError):
        return os.environ.get(name, "")


def make_prompt(kind: str, subject: str, extra: str = "") -> tuple[str,str]:
    p = S.projects[S.current]
    base = (f"Creator profile: niche={p['niche']}; target audience={p['audience']}; "
            f"tone={p['tone']}; platform={p['platform']}; goal={p['goal']}; "
            f"output_language={'Russian' if S.ui_lang == 'RU' else 'English'}. "
            "Avoid factual claims without evidence, guarantees of virality, and copied wording from competitor videos. "
            "Create original, executable material. For factual content, highlight what must be verified.")
    if kind == "script":
        system = "You are a meticulous short-video producer and storyboard writer. " + base
        prompt = (f"Create a {p['duration']}-second script for this topic: {subject}. "
                  "Output: 5 distinct hook options (question, surprising fact, scene, mistake, specific promise), "
                  "then a tight timestamped scene-by-scene storyboard (every 2-5 seconds), visuals, "
                  "voiceover, on-screen captions, final CTA, and precise ENGLISH production prompts "
                  "for vertical 9:16 AI-video tools such as Flow/Kling. "
                  "Avoid repeated establishing shots, invented statistics, impossible visual anatomy, or copyrighted imagery. "
                  f"Extra preferences: {extra}")
    elif kind == "week":
        system = "You are a short-video content strategist and planner. " + base
        prompt = ("Make a seven-day, achievable editorial calendar. Return ONLY a JSON array of 7 objects, "
                  "each with keys topic, format (Shorts / Reels or Carousel), status (always planned). "
                  "Give specific original ideas; do not imply they are empirically trending or currently viral "
                  "without evidence. No markdown code fences. " + extra)
    else:
        system = "You analyze video content strictly on provided evidence, never on imagined video footage. " + base
        prompt = (f"Analyse the following creator-provided source, and separate OBSERVED from HYPOTHESIS. "
                  f"If a transcript is missing, clearly state that the footage, spoken hook, "
                  f"editing, and retention cannot be checked. Explain possible structural hooks, "
                  f"CTA opportunities and 3 original adaptation ideas. Source: {subject}. {extra}")
    return system, prompt


with st.sidebar:
    st.markdown("## 🎬 Viral Studio **AI**")
    if st.button("🔒 Выйти / Sign out", key="private_logout"):
        st.session_state["_viral_authenticated"] = False
        st.rerun()
    st.caption("Independent creator workspace · MVP 2.0")
    S.ui_lang = st.segmented_control("Language / Язык", ["RU", "EN"], default="RU", key="language_ui")
    names = list(S.projects)
    idx = names.index(S.current) if S.current in names else 0
    chosen = st.selectbox(tr("Проект", "Project"), names, index=idx)
    if chosen != S.current:
        S.current = chosen
        S.results = []
        S.script = ""
        st.rerun()
    menu = [
        ("studio",tr("✨ AI-студия и шаблоны", "✨ AI studio & templates")),
        ("dashboard",tr("🏠 Обзор", "🏠 Overview")),
        ("profile",tr("🎯 Анкета и проекты", "🎯 Profile & projects")),
        ("trends",tr("🔥 Поиск видео", "🔥 Video discovery")),
        ("scripts",tr("✍️ Сценарии и хуки", "✍️ Scripts & hooks")),
        ("week",tr("🗓️ План на неделю", "🗓️ Weekly plan")),
        ("review",tr("🔍 Разбор по ссылке", "🔍 Analyze a link")),
        ("library",tr("📚 Библиотека", "📚 Library")),
        ("metrics",tr("📈 Мои результаты", "📈 My results")),
        ("team",tr("👥 Команда", "👥 Team")),
        ("settings",tr("⚙️ Настройки", "⚙️ Settings")),
    ]
    label_to_id = {label:key for key,label in menu}
    selected = st.radio(tr("Разделы", "Sections"), [label for key,label in menu], index=next((i for i,(key,_) in enumerate(menu) if key==S.page),0))
    S.page = label_to_id[selected]
    st.divider()
    with st.expander(tr("🔑 Подключения API", "🔑 API connections")):
        S.gemini_key = st.text_input("Gemini API key", type="password", value=S.get("gemini_key", "") or secret("GEMINI_API_KEY"), help="Private session input; not included in exports")
        S.youtube_key = st.text_input("YouTube Data API key", type="password", value=S.get("youtube_key", "") or secret("YOUTUBE_API_KEY"))
        S.gemini_model = st.text_input("Gemini model", value=S.get("gemini_model", "") or secret("GEMINI_MODEL") or "gemini-2.5-flash")
        st.caption(tr("Ключи вводятся в этой сессии и не включаются в экспорт.", "Keys stay in this session and are not exported."))
    st.caption(tr("Демонстрационный кабинет · без регистрации и оплаты", "Prototype workspace · no sign-up or payments"))

p = S.projects[S.current]


def header(kicker: str, title: str, caption: str):
    st.markdown(f'<div class="v-hero"><div class="v-kicker">{kicker}</div><h1>{title}</h1><p>{caption}</p></div>', unsafe_allow_html=True)


def add_library(kind: str, title: str, body: str, url: str = ""):
    S.library.append({"type":kind, "title":title, "content":body, "url":url, "added":datetime.now().strftime("%Y-%m-%d %H:%M")})


def run_ai(kind: str, subject: str, extra: str = "") -> str:
    if not S.gemini_key:
        raise ApiError(tr("Добавь Gemini API key в боковой панели. Без него доступен только шаблон.", "Add a Gemini API key in the sidebar. Without it, only templates are available."))
    system, prompt = make_prompt(kind, subject, extra)
    return gemini_generate(S.gemini_key, S.gemini_model, system, prompt)


if S.page == "studio":
    if S.ui_lang == "RU":
        st.markdown("""<div class="studio-hero"><div class="studio-kicker">VIRAL STUDIO AI / CREATOR WORKSPACE</div><h1>Создавай то, что хочется досмотреть</h1><p>Одна идея → сценарий, карусель, контент-план или визуальный промпт. Все инструменты в одном месте.</p></div>""", unsafe_allow_html=True)
    else:
        st.markdown("""<div class="studio-hero"><div class="studio-kicker">VIRAL STUDIO AI / CREATOR WORKSPACE</div><h1>Make content worth watching</h1><p>One idea → a script, carousel, content calendar or visual prompt. All in one workspace.</p></div>""", unsafe_allow_html=True)
    st.caption(tr("Рабочая версия: бесплатные черновики без API; интеллектуальная генерация при подключении Gemini; живой поиск — через YouTube API.",
                  "Working prototype: free editable drafts without API; AI generation with Gemini; live discovery through YouTube API."))
    idea_text = st.text_area(tr("Расскажи, что хочешь сделать", "Describe your idea"),
                            key="studio_idea",
                            placeholder=tr("Например: 30-секундный Shorts о том, как курица формирует яйцо. Реалистично, быстрые кадры, английская озвучка.",
                                           "For example: make a 30-second Short explaining how a hen forms an egg. Realistic, close-ups, English voiceover."),
                            height=110)
    a,b,c=st.columns([1.35,1,1])
    with a:
        if st.button(tr("✨ Подобрать инструмент по идее", "✨ Match tool to idea"), type="primary", use_container_width=True):
            if not idea_text.strip():
                st.warning(tr("Сначала напиши идею в поле выше.", "Start by entering your idea above."))
            else:
                chosen = route_request(idea_text)
                r=CATALOG[chosen]
                if r.kind=="navigate":
                    S.page = r.route
                    if chosen=="reels_teardown": S.review = ""
                else:
                    S.studio_recipe = chosen
                st.rerun()
    with b:
        if st.button(tr("🔍 Найти реальные видео", "🔍 Find real videos"), use_container_width=True):
            S.page="trends"
            st.rerun()
    with c:
        if st.button(tr("📅 Мой контент-план", "📅 My content calendar"), use_container_width=True):
            S.page="week"
            st.rerun()

    st.markdown("### " + tr("Выбери инструмент", "Explore tools"))
    display = {"All":tr("Все", "All"), "Videos":tr("Видео", "Videos"),
               "Carousels":tr("Карусели", "Carousels"), "Trends":tr("Тренды", "Trends"),
               "Content":tr("Контент", "Content"), "Images":tr("Изображения", "Images"),
               "Chatbots":tr("Чат-боты", "Chatbots")}
    chosen_group=st.segmented_control(tr("Категория", "Category"), GROUPS, format_func=lambda g: display[g], key="studio_group", label_visibility="collapsed")
    shown=[r for r in RECIPES if chosen_group=="All" or r.group==chosen_group]
    if chosen_group=="All":
        feature_order=["reels_script","trends_youtube","carousel_idea","content_studio","plan_30","hooks_30","short_story","image_prompts","reels_teardown","thumbnail","montage","keyword_bot"]
        shown=[CATALOG[k] for k in feature_order]
        st.caption(tr("Подборка популярных задач · остальные инструменты доступны по категориям выше.",
                      "Featured tools · explore the other categories to see all tools."))
    for start in range(0,len(shown),3):
        cols=st.columns(3)
        for col,r in zip(cols,shown[start:start+3]):
            with col:
                active = r.slug == S.studio_recipe
                st.markdown(f'<div class="studio-tile"><span class="studio-category">{safe_html(r.group)}</span>'
                            f'<div class="studio-tiletitle">{safe_html(r.ru if S.ui_lang=="RU" else r.en)}</div>'
                            f'<div class="studio-tiledesc">{safe_html(r.ru_desc if S.ui_lang=="RU" else r.en_desc)}</div></div>',
                            unsafe_allow_html=True)
                if st.button(tr("Открыть →", "Open →") if not active else tr("✓ Выбрано", "✓ Selected"),
                             key="recipe_"+r.slug, use_container_width=True):
                    if r.kind=="navigate":
                        S.page=r.route
                    else:
                        S.studio_recipe=r.slug
                        S.studio_output=""
                    st.rerun()

    selected=CATALOG.get(S.studio_recipe,CATALOG["reels_script"])
    st.divider()
    st.subheader(tr("Мастерская: ", "Workshop: ") + recipe_title(selected.slug,S.ui_lang))
    st.caption(selected.ru_desc if S.ui_lang=="RU" else selected.en_desc)
    if not idea_text.strip():
        st.info(tr("Напиши идею в поле вверху. Можно использовать тему канала, если конкретная идея ещё не готова.",
                   "Enter an idea above. Your channel niche can be used as a starting point."))
    gen_a,gen_b=st.columns(2)
    with gen_a:
        if st.button(tr("Создать бесплатный черновик", "Create free draft"), use_container_width=True):
            S.studio_output=fallback_draft(selected.slug,idea_text or p["niche"],p,S.ui_lang)
            S.studio_output_type="draft"
    with gen_b:
        if st.button(tr("✨ Создать с Gemini", "✨ Generate with Gemini"),type="primary",use_container_width=True):
            if not S.gemini_key:
                st.warning(tr("Для интеллектуальной генерации нужен Gemini API key. Добавь его в разделе «Подключения API» слева.",
                              "AI generation needs a Gemini API key. Add it under API connections in the sidebar."))
            else:
                sys_msg,prompt=ai_prompts(selected.slug,idea_text or p["niche"],p,S.ui_lang)
                try:
                    with st.spinner(tr("Готовим результат с Gemini…", "Creating with Gemini…")):
                        S.studio_output=gemini_generate(S.gemini_key,S.gemini_model,sys_msg,prompt)
                        S.studio_output_type="gemini"
                except ApiError as e:
                    st.error(str(e))
    if S.studio_output:
        if S.studio_output_type=="draft":
            st.info(tr("Это шаблонный черновик без AI-генерации и без проверки трендов.", "This is a rule-based draft, not an AI generation or trend report."))
        else:
            st.caption(tr("Результат Gemini. Проверь факты, даты и пригодность сценария перед публикацией.",
                          "Gemini output. Verify claims, dates and production details before publishing."))
        with st.container(border=True):
            st.markdown(S.studio_output)
        da,db=st.columns(2)
        with da:
            st.download_button(tr("↓ Скачать в Markdown", "↓ Download Markdown"),S.studio_output,
                               file_name="viral_studio_result.md",mime="text/markdown",use_container_width=True)
        with db:
            if st.button(tr("♡ Сохранить в библиотеку", "♡ Save to library"), key="save_studio", use_container_width=True):
                add_library(selected.slug,(idea_text.strip() or p["niche"])[:90],S.studio_output)
                st.toast(tr("Сохранено в библиотеку", "Saved to library"))
    st.caption(tr("Видео, изображения и работающие чат-боты здесь пока не создаются. Для них подключим отдельные инструменты и официальные интеграции.",
                  "Rendering video or images and deploying chatbots require separate integrations, not available in this version."))

elif S.page == "dashboard":
    header("CREATOR COMMAND CENTER", tr("От идеи до готового сценария", "From idea to finished script"),
           tr("Твой контент, тренды, сценарии и план публикаций — в одном кабинете.", "Your trends, scripts and publishing calendar — in one workspace."))
    col1,col2,col3,col4=st.columns(4)
    col1.metric(tr("Проектов", "Projects"),len(S.projects))
    col2.metric(tr("Идей в библиотеке", "Saved ideas"),len(S.library))
    col3.metric(tr("Дней в плане", "Planned days"),len(p.get("week",[])))
    col4.metric(tr("Роликов с метриками", "Tracked videos"),len(S.videos))
    left,right=st.columns([1.15,1])
    with left:
        st.markdown(f'<div class="v-card"><span class="v-tag">{safe_html(p["platform"])}</span><h3>{tr("Твой профиль", "Your profile")}</h3><p><b>{tr("Ниша", "Niche")}:</b> {safe_html(str(p["niche"]))}</p><p><b>{tr("Аудитория", "Audience")}:</b> {safe_html(str(p["audience"]))}</p><p><b>{tr("Стиль", "Tone")}:</b> {safe_html(str(p["tone"]))}</p></div>', unsafe_allow_html=True)
        st.subheader(tr("Быстрый сценарий", "Quick script"))
        quick = st.text_input(tr("Тема следующего ролика", "Next video topic"), value=S.selected_topic or "How a chicken egg forms")
        if st.button(tr("Открыть редактор сценария →", "Open script editor →"),type="primary"):
            S.selected_topic=quick
            S.page="scripts"
            st.rerun()
    with right:
        st.markdown(f'<div class="v-card"><h3>{tr("Что действительно работает в этой версии", "What works in this version")}</h3><p>✓ {tr("Анкета, план, шаблоны и библиотека", "Profiles, plans, templates and library")}</p><p>✓ {tr("Настоящие данные YouTube при наличии API-ключа", "Real YouTube data when API is connected")}</p><p>✓ {tr("AI-сценарии при наличии Gemini API", "AI scripts when Gemini API is connected")}</p></div>', unsafe_allow_html=True)
        st.info(tr("Автопубликация, анализ Instagram/TikTok, многопользовательский доступ и генерация видео пока не подключены.", "Auto-posting, Instagram/TikTok analytics, multiuser access and video generation are not integrated yet."))

elif S.page == "profile":
    header("01 / CREATOR DNA",tr("Анкета автора", "Creator profile"),tr("Эти ответы определяют стиль будущих сценариев.", "Your answers shape the scripts and calendar."))
    new_name = st.text_input(tr("Название нового проекта", "New project name"), placeholder="Second channel")
    if st.button(tr("＋ Создать проект", "＋ Create project")):
        name = new_name.strip()
        if not name: st.warning(tr("Введите название.", "Enter a name."))
        elif name in S.projects: st.warning(tr("Такой проект существует.", "This project exists."))
        else:
            S.projects[name]={**{k:v for k,v in p.items() if k not in {"week","members"}}, "week":[], "members":[]}
            S.current=name
            st.rerun()
    a,b=st.columns(2)
    with a:
        p["niche"] = st.text_input(tr("Ниша", "Niche"), value=p["niche"])
        p["audience"] = st.text_area(tr("Кто смотрит", "Target audience"), value=p["audience"], height=90)
        p["tone"] = st.text_area(tr("Манера речи и стиль", "Tone of voice"), value=p["tone"], height=90)
        p["handle"] = st.text_input(tr("Ссылка на канал (для справки)", "Channel URL (reference only)"),value=p.get("handle",""))
    with b:
        p["platform"] = st.selectbox(tr("Главная платформа", "Main platform"),["YouTube Shorts","Instagram Reels","TikTok","Telegram","Pinterest"],index=["YouTube Shorts","Instagram Reels","TikTok","Telegram","Pinterest"].index(p["platform"]) if p["platform"] in ["YouTube Shorts","Instagram Reels","TikTok","Telegram","Pinterest"] else 0)
        p["goal"] = st.text_input(tr("Цель", "Goal"),value=p["goal"])
        p["duration"] = st.slider(tr("Длина видео (сек)", "Video duration (sec)"),min_value=12,max_value=60,value=int(p["duration"]))
    st.success(tr("Изменения сохраняются в текущей сессии. Экспорт доступен в Настройках.", "Changes are saved in your current session. Export in Settings."))

elif S.page == "trends":
    header("02 / DISCOVER", tr("Поиск популярных видео", "Discover high-performing videos"),
           tr("Данные YouTube, а не придуманные показатели. Приближённые сигналы, не гарантия вирусности.", "Real YouTube data, not invented metrics. Signals are not proof of virality."))
    st.info(tr("Для реального поиска нужен YouTube Data API key в боковой панели. Instagram и TikTok пока не подключены.", "Add a YouTube Data API key in the sidebar for live search. Instagram and TikTok aren't connected."))
    c1,c2,c3=st.columns([2,1,1])
    with c1: query = st.text_input(tr("Ниша / поисковый запрос", "Niche / search query"),value=p["niche"])
    with c2: days = st.selectbox(tr("За период", "Published within"),[7,14,30,90],format_func=lambda n:tr(f"{n} дней",f"{n} days"))
    with c3: language = st.selectbox(tr("Язык поиска", "Search language"),["en","ru","es","de","fr"],index=0 if S.ui_lang=="EN" else 1)
    if st.button(tr("Найти реальные видео", "Search real videos"),type="primary"):
        if not S.youtube_key: st.warning(tr("Сначала добавь YouTube API key.", "First add a YouTube API key."))
        else:
            try:
                with st.spinner(tr("Получаем данные YouTube...", "Fetching YouTube data...")):
                    S.results=search_youtube(query,S.youtube_key,days=days,language=language)
            except ApiError as e: st.error(str(e))
    if S.results:
        st.caption(tr("Сортировка: средние просмотры в день (примерная оценка на основе даты публикации).", "Sorted by estimated views per day since publication."))
        results=sorted(S.results,key=lambda x:x["views_per_day"],reverse=True)
        for v in results:
            with st.container(border=True):
                a,b=st.columns([1,2.4])
                with a:
                    if v["thumbnail"]: st.image(v["thumbnail"],use_container_width=True)
                with b:
                    st.markdown(f"**{v['title']}**")
                    st.caption(f"{v['channel']} · {v['published'][:10]} · {v['duration_s']}s")
                    st.write(f"👁 {format_num(v['views'])} · {tr('в день','per day')} {format_num(v['views_per_day'])} · {tr('просмотры/подписчики','views/subscribers')}: {v['view_to_subscriber'] if v['view_to_subscriber'] is not None else '—'}")
                    st.link_button(tr("Открыть ролик", "Open video"),v["url"])
                    if st.button(tr("Сохранить в библиотеку", "Save to library"),key="save_"+v["id"]):
                        add_library("youtube",v["title"],f"Channel: {v['channel']}. Views: {v['views']}. Published: {v['published']}.",v["url"])
                        st.toast(tr("Добавлено", "Saved"))
    else:
        st.markdown(f'<div class="v-card"><h3>{tr("Пустая лента — никаких фиктивных трендов", "No made-up trends")}</h3><p>{tr("После подключения официального YouTube API здесь появятся реальные ролики, просмотры и ссылки.", "After connecting the official YouTube API, real videos, views and links will appear here.")}</p></div>',unsafe_allow_html=True)

elif S.page == "scripts":
    header("03 / SCRIPT LAB",tr("Сценарист и 5 хуков", "Script lab & 5 hooks"),tr("Короткие, точные кадры, таймкоды и промпты для видео.", "Compact scenes, timing and prompts for AI-video tools."))
    topic=st.text_input(tr("Тема ролика", "Video topic"),value=S.selected_topic or "How a chicken egg forms")
    extra=st.text_area(tr("Дополнительные пожелания", "Extra instructions"),placeholder=tr("Реалистично, научно точно, без повторов...", "Realistic, scientifically accurate, no repeated shots..."),height=90)
    st.subheader(tr("Пять вариантов начала", "Five alternative hooks"))
    hooks=sample_hooks(topic,p["niche"],S.ui_lang)
    for i,(kind,h) in enumerate(hooks):
        st.markdown(f'<div class="v-card" style="min-height:40px;padding:13px 18px;margin:7px 0"><span class="v-tag">{i+1:02} · {safe_html(kind)}</span> {safe_html(h)}</div>',unsafe_allow_html=True)
    a,b=st.columns(2)
    with a:
        if st.button(tr("Создать шаблон бесплатно", "Create free template"),use_container_width=True):
            S.script=demo_script(topic,p["niche"],S.ui_lang,p["duration"])
            S.script_title=topic
    with b:
        if st.button(tr("✨ Сгенерировать сценарий с Gemini", "✨ Generate with Gemini"),type="primary",use_container_width=True):
            try:
                with st.spinner(tr("Создаём сценарий...", "Generating script...")):
                    S.script=run_ai("script",topic,extra)
                    S.script_title=topic
            except ApiError as e: st.error(str(e))
    if S.script:
        st.divider()
        st.markdown(S.script)
        st.download_button(tr("↓ Скачать сценарий .md", "↓ Download script .md"),S.script,file_name="viral_studio_script.md",mime="text/markdown")
        if st.button(tr("♡ Сохранить в библиотеку", "♡ Save in library")):
            add_library("script",S.script_title,S.script)
            st.toast(tr("Сценарий сохранён", "Script saved"))

elif S.page == "week":
    header("04 / EDITORIAL CALENDAR",tr("План на семь дней", "Seven-day calendar"),tr("Меняй темы, отмечай готовность и открывай сценарии одним нажатием.", "Edit topics, track progress and jump into script writing."))
    a,b=st.columns(2)
    with a:
        if st.button(tr("Создать шаблон недели", "Build week template"),use_container_width=True):
            for i in range(7):
                S.pop(f"topic_{S.current}_{i}", None)
                S.pop(f"status_{S.current}_{i}", None)
            p["week"]=demo_week(p["niche"],S.ui_lang)
    with b:
        if st.button(tr("✨ План недели с Gemini", "✨ Create AI week plan"),type="primary",use_container_width=True):
            try:
                with st.spinner(tr("Составляем план...", "Planning...")):
                    raw=run_ai("week",p["niche"])
                parsed=json.loads(raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip())
                if not isinstance(parsed,list) or len(parsed)!=7: raise ValueError("Model returned an unexpected calendar format")
                for i in range(7):
                    S.pop(f"topic_{S.current}_{i}", None)
                    S.pop(f"status_{S.current}_{i}", None)
                p["week"]=[{"day":i,"topic":str(item["topic"]),"format":str(item.get("format","Shorts / Reels")),"status":"planned"} for i,item in enumerate(parsed)]
            except (ApiError,ValueError,KeyError,TypeError) as e: st.error(str(e))
    if not p["week"]:
        st.info(tr("Нажми кнопку выше, чтобы получить план. Шаблон не использует живые тренды.", "Use a button above to create your plan. The template does not use live trends."))
    else:
        labels=DAYS_RU if S.ui_lang=="RU" else DAYS_EN
        status_options=["planned","filming","review","published"]
        status_labels={"planned":tr("План", "Planned"),"filming":tr("Снимаем", "Filming"),"review":tr("Правки", "Review"),"published":tr("Опубликовано", "Published")}
        for i,item in enumerate(p["week"]):
            with st.container(border=True):
                top,stat,open_button=st.columns([3.6,1.4,1.2])
                with top:
                    st.caption(labels[i])
                    item["topic"]=st.text_input(tr("Тема", "Topic"),value=item["topic"],key=f"topic_{S.current}_{i}",label_visibility="collapsed")
                with stat:
                    item["status"]=st.selectbox(tr("Статус", "Status"),status_options,index=status_options.index(item.get("status","planned")),format_func=lambda x:status_labels[x],key=f"status_{S.current}_{i}")
                with open_button:
                    st.caption(" ")
                    if st.button(tr("Сценарий →", "Script →"),key=f"scriptday_{S.current}_{i}"):
                        S.selected_topic=item["topic"]
                        S.page="scripts"
                        st.rerun()
        done=sum(x["status"]=="published" for x in p["week"])
        st.progress(done/7,text=tr(f"Опубликовано {done} из 7",f"Published {done} of 7"))

elif S.page == "review":
    header("05 / VIDEO DECONSTRUCTION",tr("Разбор чужого ролика", "Video link analysis"),tr("Отделяем измеренные показатели от гипотез — без выдуманной транскрибации.", "We separate measured metrics from hypotheses and never invent a transcript."))
    url=st.text_input(tr("Ссылка YouTube Shorts, Reels или TikTok", "YouTube Shorts, Reels or TikTok URL"),placeholder="https://www.youtube.com/shorts/...........")
    transcript=st.text_area(tr("Транскрибация / описание кадров (необязательно)", "Transcript / visual notes (optional)"),height=135,placeholder=tr("Вставь текст речи или свои заметки по кадрам", "Paste spoken dialogue or your own frame notes"))
    vid=youtube_id(url) if url else None
    if url and not vid:
        st.warning(tr("Автоматическая статистика сейчас доступна только для YouTube. Можно анализировать вручную вставленный текст других платформ.", "Automatic statistics currently support YouTube only. You can still analyze your own pasted text from other platforms."))
    if st.button(tr("Получить факты о видео", "Get video facts")):
        if not vid: st.warning(tr("Укажи корректную ссылку YouTube.", "Enter a valid YouTube video link."))
        elif not S.youtube_key: st.warning(tr("Добавь YouTube API key слева.", "Add a YouTube API key on the left."))
        else:
            try:
                S.last_video=get_youtube_video(vid,S.youtube_key)
                if not S.last_video: st.warning(tr("Видео не найдено или недоступно.", "Video not found or unavailable."))
            except ApiError as e: st.error(str(e))
    if S.get("last_video") and S.last_video.get("id")==vid:
        v=S.last_video
        st.markdown(f"**{v['title']}** · {v['channel']}")
        a,b,c=st.columns(3)
        a.metric(tr("Просмотры", "Views"),format_num(v["views"]))
        b.metric(tr("Лайки", "Likes"),format_num(v["likes"]) if v["likes"] is not None else "—")
        c.metric(tr("В день (оценка)", "Per day (estimate)"),format_num(v["views_per_day"]))
    if st.button(tr("✨ Анализировать через Gemini", "✨ Analyze with Gemini"),type="primary"):
        video = S.get("last_video") if vid and (S.get("last_video") or {}).get("id")==vid else None
        metadata=(f"URL: {url}. Video title: {video.get('title','')}. Description: {video.get('description','')}. "
                  f"Views: {video.get('views','not known')}. Published: {video.get('published','not known')}" if video else f"URL: {url}. Metadata unavailable")
        try:
            with st.spinner(tr("Анализируем доступные данные...", "Analyzing available evidence...")):
                S.review=run_ai("review",metadata,f"User-supplied transcript/scene notes: {transcript or 'NOT PROVIDED'}")
        except ApiError as e: st.error(str(e))
    if S.review:
        st.markdown(S.review)
        st.download_button(tr("↓ Скачать разбор", "↓ Download review"),S.review,file_name="viral_studio_analysis.md",mime="text/markdown")
        if st.button(tr("Сохранить разбор", "Save analysis")):
            add_library("analysis",url or "Video analysis",S.review,url)
            st.toast(tr("Сохранено", "Saved"))

elif S.page == "library":
    header("06 / CREATIVE VAULT",tr("Библиотека идей", "Saved content library"),tr("Сценарии и интересные ролики не теряются в переписке.", "Keep scripts, links and ideas together."))
    if not S.library: st.info(tr("Пока нет сохранённых материалов. Добавь ролик или сценарий.", "Nothing saved yet. Save a video or a script."))
    for i,item in reversed(list(enumerate(S.library))):
        with st.expander(f"{item['type'].upper()} · {item['title']} · {item['added']}"):
            if item.get("url"): st.link_button(tr("Открыть источник", "Open source"),item["url"])
            st.markdown(item["content"])
            st.download_button(tr("Скачать текст", "Download text"),item["content"],file_name=f"saved_{i}.md",key=f"download_{i}")
            if st.button(tr("Удалить", "Delete"),key=f"delete_{i}"):
                S.library.pop(i); st.rerun()

elif S.page == "metrics":
    header("07 / PERFORMANCE",tr("Мои результаты", "My performance"),tr("Записывай реальные цифры опубликованных видео; никаких вымышленных графиков.", "Record real performance data from your published videos."))
    with st.form("video_metrics"):
        a,b=st.columns(2)
        with a:
            title=st.text_input(tr("Название ролика", "Video title"))
            video_url=st.text_input(tr("Ссылка", "URL"))
            views=st.number_input(tr("Просмотры", "Views"),min_value=0,step=1)
        with b:
            likes=st.number_input(tr("Лайки", "Likes"),min_value=0,step=1)
            comments=st.number_input(tr("Комментарии", "Comments"),min_value=0,step=1)
            saves=st.number_input(tr("Сохранения", "Saves"),min_value=0,step=1)
        if st.form_submit_button(tr("Добавить результат", "Add result"),type="primary"):
            if title.strip():
                S.videos.append({"title":title.strip(),"url":video_url,"views":int(views),"likes":int(likes),"comments":int(comments),"saves":int(saves),"project":S.current})
                st.success(tr("Результат добавлен", "Result added"))
            else: st.warning(tr("Укажи название.", "Enter a title."))
    own=[v for v in S.videos if v["project"]==S.current]
    if own:
        rows=[]
        for v in own:
            engagement=round(100*(v["likes"]+v["comments"]+v["saves"])/v["views"],2) if v["views"] else 0
            rows.append({tr("Ролик", "Video"):v["title"],tr("Просмотры", "Views"):v["views"],tr("Лайки", "Likes"):v["likes"],tr("Комментарии", "Comments"):v["comments"],"Interactions / views %":engagement})
        st.dataframe(rows,use_container_width=True,hide_index=True)
        st.caption(tr("Показатель interactions/views — простое отношение введённых взаимодействий к просмотрам, не официальный ER платформы.", "Interactions/views is a basic ratio of entered interactions to views, not a platform's official engagement rate."))

elif S.page == "team":
    header("08 / WORKSPACE",tr("Команда проекта", "Project team"),tr("Подготовка ролей продюсера, автора и монтажёра.", "Track producer, creator and editor roles."))
    st.warning(tr("В этой версии роли — только локальный список. Приглашения, права доступа и общая работа потребуют базы данных и авторизации.", "These are local role labels only. Real invitations and shared access require authentication and a database."))
    with st.form("team_form"):
        name=st.text_input(tr("Имя участника", "Member name"))
        role=st.selectbox(tr("Роль", "Role"),["Creator","Producer","Editor","SMM"])
        if st.form_submit_button(tr("Добавить в список", "Add to list")) and name.strip():
            p["members"].append({"name":name.strip(),"role":role})
    for member in p.get("members",[]): st.markdown(f"- **{member['name']}** · {member['role']}")

elif S.page == "settings":
    header("09 / DATA & PRIVACY",tr("Настройки и экспорт", "Settings & export"),tr("Сохрани свои проекты в файл, чтобы не потерять данные между сессиями.", "Export your projects so that they survive browser sessions."))
    st.warning(tr("Вход защищён общим паролем, но это не многопользовательский кабинет и не облачная база данных. Данные сессии могут исчезнуть после перезапуска; регулярно скачивай резервную копию.", "A shared password protects entry, but this is not multi-user authentication or durable cloud storage. Session data may disappear on restart; export backups regularly."))
    payload=data_export(S.projects,S.current,S.library,S.videos)
    st.download_button(tr("↓ Скачать все данные JSON", "↓ Export all data as JSON"),data=json.dumps(payload,ensure_ascii=False,indent=2),file_name="viral_studio_backup.json",mime="application/json",type="primary")
    f=st.file_uploader(tr("Восстановить из JSON-файла", "Restore from JSON backup"),type="json")
    if f and st.button(tr("Восстановить данные", "Restore data")):
        try:
            content=json.load(f)
            assert content.get("schema")==1 and isinstance(content.get("projects"),dict) and content["projects"]
            S.projects=content["projects"]
            S.current=content.get("current") if content.get("current") in S.projects else next(iter(S.projects))
            S.library=content.get("library",[])
            S.videos=content.get("videos",[])
            S.results=[]
            st.success(tr("Данные восстановлены", "Backup restored"))
            st.rerun()
        except (ValueError,AssertionError,TypeError,KeyError) as e:
            st.error(tr("Некорректный файл резервной копии.", "Invalid backup file."))
    st.subheader(tr("Что подключим дальше", "Future integrations"))
    st.markdown(tr("**Позже:** безопасные аккаунты, база данных, Instagram/TikTok с официальным доступом, полноценная обработка видео, транскрибация, карусели и автопубликация.", "**Next:** user authentication, database, authorized Instagram/TikTok integrations, full video analysis, transcription, carousels and publishing."))

st.divider()
st.caption("Viral Studio AI · Independent concept prototype · Unaffiliated with Virales.io or ChatPlace Virale · Data via official YouTube API only when connected")
