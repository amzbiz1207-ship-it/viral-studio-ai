"""Viral Studio AI — independent Streamlit prototype, RU/EN."""
from __future__ import annotations
import json
import copy
import hashlib
import re
import os
import hmac
import base64
import io
import requests
import subprocess
import tempfile
import shutil
from PIL import Image
from html import escape as safe_html
from datetime import datetime
from pathlib import Path
import streamlit as st
from core import DAYS_RU, DAYS_EN, sample_hooks, demo_script, demo_week, format_num, youtube_id, data_export
from services import ApiError, get_youtube_video, search_youtube, gemini_generate, deepseek_generate
from studio_tools import RECIPES, CATALOG, GROUPS, title as recipe_title, route_request, fallback_draft, ai_prompts
from storage import StateStore, StorageError, validate_restore
from exports import filename, docx_bytes, pdf_bytes

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

def secret(name: str) -> str:
    try:
        return str(st.secrets.get(name, os.environ.get(name, "")))
    except (FileNotFoundError, AttributeError, OSError):
        return os.environ.get(name, "")

DEFAULT_PROFILE = {"niche":"", "audience":"", "tone":"", "platform":"Instagram Reels",
                   "goal":"", "language":"EN", "output_language":"EN", "prompt_language":"EN",
                   "duration":30, "handle":"", "week":[], "members":[]}
DEFAULT_STATE = {"projects":{"My channel":{**DEFAULT_PROFILE, "niche":"How things work / Как это устроено",
                        "audience":"Curious viewers aged 12+", "tone":"Clear, lively, scientifically accurate",
                        "platform":"YouTube Shorts", "goal":"More organic views"}},
                 "current":"My channel", "library":[], "videos":[], "saved_outputs":[],
                 "language_output":"EN", "prompt_language":"EN"}
DATA_KEYS = list(DEFAULT_STATE)

def persistent_state():
    return {k: copy.deepcopy(S.get(k, DEFAULT_STATE[k])) for k in DATA_KEYS}

try:
    store=StateStore(secret("SUPABASE_URL"),secret("SUPABASE_SERVICE_ROLE_KEY"))
    storage_problem = ""
except StorageError as e:
    store = None
    storage_problem = str(e)

if "_data_loaded" not in S:
    try:
        data=store.load() if store else None
        if data:
            data=validate_restore({"schema":2,**data})
        for k,v in (data or DEFAULT_STATE).items():
            if k in DATA_KEYS: S[k]=copy.deepcopy(v)
        # Widget state must reflect the cloud record, not a previous view's default.
        S._data_loaded=True
        S.project_picker=S.get("current", "My channel")
        S._cloud_loaded_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    except (StorageError, ValueError) as e:
        storage_problem=str(e)
        # Never silently replace stored data if storage is unavailable.
        st.error("Saved data unavailable / Не удалось загрузить данные: " + storage_problem)
        st.stop()
for k,v in DEFAULT_STATE.items():
    if k not in S: S[k]=copy.deepcopy(v)
if S.current not in S.projects: S.current=next(iter(S.projects))
for k, v in {"script":"", "script_title":"", "review":"", "selected_topic":"",
             "page":"studio", "studio_recipe":None, "studio_output":"",
             "studio_output_type":"", "studio_group":"All", "results":[],
             "_pending_nav":None, "_last_save_error":"", "_flash_message":"",
             "review_original":"", "review_adaptation":"", "review_evidence":"",
             "review_idea_choice":1, "review_source_url":"",
             "story_source":"", "story_ideas":"", "story_script":"",
             "story_style":"family", "story_draft_source":"", "story_style_for_ideas":"family"}.items():
    if k not in S: S[k]=v

def save_state():
    """Persist complete user state, and never claim success on a failed write."""
    if not store:
        raise StorageError(storage_problem or 'Storage not configured')
    store.save(persistent_state())
    S._last_save_error = ""

def reload_from_storage():
    """Explicit authoritative re-read; never overwrite cloud data with empty defaults."""
    if not store:
        raise StorageError(storage_problem or 'Storage not configured')
    raw=store.load()
    if raw is None:
        raise StorageError('No saved cloud record was found. Local changes were left intact.')
    loaded=validate_restore({'schema':2, **raw})
    for key in DATA_KEYS:
        S[key]=copy.deepcopy(loaded.get(key, DEFAULT_STATE[key]))
    if not S.projects:
        raise StorageError('Saved project list is empty.')
    if S.current not in S.projects:
        S.current=next(iter(S.projects))
    # The selectbox already exists during this run: defer its update until the next rerun.
    S._pending_project=S.current
    for key in list(S):
        # Clear per-project widgets: they must not replay older profile values
        # and overwrite the freshly restored cloud snapshot.
        if isinstance(key,str) and (key.startswith('profile_') or key.startswith('topic_') or key.startswith('status_')):
            del S[key]
    S._saved_digest=hashlib.sha256(json.dumps(persistent_state(),ensure_ascii=False,sort_keys=True).encode()).hexdigest()
    S._cloud_loaded_at=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    S._last_save_error=''

def profile_key(field):
    # Scope Streamlit widgets to the active project.
    return 'profile_'+hashlib.sha256(S.current.encode('utf-8')).hexdigest()[:12]+'_'+field

def navigate(destination):
    # Synchronise the sidebar widget on the NEXT run rather than overwriting its value.
    S.page=destination
    S._pending_nav=destination
    try:
        save_state()
    except StorageError as e:
        S._last_save_error=str(e)
    st.rerun()

def exports_ui(content, kind, subject, key):
    st.caption(tr("Скачать материал", "Download material"))
    cols=st.columns(3)
    files=[('MD', content.encode('utf-8'),'md','text/markdown'),
           ('Word', None,'docx','application/vnd.openxmlformats-officedocument.wordprocessingml.document'),
           ('PDF', None,'pdf','application/pdf')]
    for c,(label,blob,ext,mime) in zip(cols,files):
        try:
            if ext=='docx': blob=docx_bytes(subject,content)
            if ext=='pdf': blob=pdf_bytes(subject,content)
            with c:
                st.download_button(label,blob,file_name=filename(kind,subject,ext),mime=mime,
                                   key=f"{key}_{ext}",width='stretch')
        except Exception as e:
            with c: st.warning(f"{label}: {e}")

def tr(ru: str, en: str) -> str:
    return ru if S.ui_lang == "RU" else en


def creative_director_rules() -> str:
    """Production brief used by every final short-video script path.

    This is prompt guidance, NOT a claim that retention analytics or source
    footage can be inferred from public YouTube metadata.
    """
    return (
        "CREATIVE DIRECTOR / HOOK & STORY OPTIMIZER — REQUIRED FOR EVERY FINAL SHORT: "
        "First identify the core audience emotion, curiosity gap, comic mechanism, "
        "and most compelling observable action or reaction. The first 0–3 seconds "
        "must be a SPECIFIC visual event, not an introduction, title card, background "
        "explanation, generic question or slow establishing shot. Design THREE genuinely "
        "different opening options: (A) show a consequence or something visibly wrong, "
        "(B) interrupt an ordinary action with a plausible surprise, (C) tease the "
        "reaction/payoff without revealing its cause. Specify an exact visual, action, "
        "sound and viewer curiosity for each; recommend ONE and explain why for THIS "
        "story (do not claim guaranteed virality). Build a tight cause-and-effect beat "
        "sequence: hook, escalation, reveal/payoff, brief natural reaction, clean ending. "
        "Consider a reverse-order cold open or a callback ONLY if it makes the short "
        "clearer. Remove filler, repeated shots, excessive narration, artificial calls "
        "to action and implausible acting. Prefer humor that is visually understandable "
        "even with sound off and feels candid, warm and surprising to adults. "
        "Deliver production-ready timed scenes with one feasible physical action per "
        "clip, clear continuity and consistent appearance/location. Add ready-to-copy "
        "standalone image/video generation prompts (each clip no longer than 8 seconds), "
        "sound/edit notes and a compact realism/safety self-check. If this script is "
        "inspired by a reference analysis, reuse ONLY general narrative principles, "
        "not distinctive source footage, jokes, dialogue, characters or sequence. "
        "Evidence rules: without actual video frames/transcript, NEVER assert which "
        "specific source frame made the video popular, its retention curve, or an "
        "observed hook. Label such claims as hypotheses. "
    )


def make_prompt(kind: str, subject: str, extra: str = "") -> tuple[str,str]:
    p = S.projects[S.current]
    base = (f"Creator profile: niche={p['niche']}; target audience={p['audience']}; "
            f"tone={p['tone']}; platform={p['platform']}; goal={p['goal']}; "
            f"output_language={'Russian' if S.language_output == 'RU' else 'English'}. "
            "Avoid factual claims without evidence, guarantees of virality, and copied wording from competitor videos. "
            "Create original, executable material. For factual content, highlight what must be verified. "
            "Produce all headings and explanations in the output language. "
            f"Production prompts must be written in {'Russian' if S.prompt_language == 'RU' else 'English'}. "
            "Never claim features or metrics not shown as available in the supplied facts.")
    if kind == "script":
        system = "You are a meticulous short-video producer and storyboard writer. " + base + creative_director_rules()
        prompt = (f"Create a {p['duration']}-second script for this topic: {subject}. "
                  "Output: three contrasting concrete 0–3-second visual hook options, identify the strongest, "
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
    st.caption("Independent creator workspace · Personal 1.0")
    S.ui_lang = st.segmented_control("Language / Язык", ["RU", "EN"], default="RU", key="language_ui")
    names = list(S.projects)
    idx = names.index(S.current) if S.current in names else 0
    if S.get('project_picker') not in names:
        S.project_picker=S.current
    if S.get("_pending_project"):
        S.project_picker=S._pending_project
        S._pending_project=None
    chosen = st.selectbox(tr("Проект", "Project"), names, key="project_picker")
    if chosen != S.current:
        # Save any edits to the outgoing project before switching views.
        try:
            save_state()
        except StorageError as exc:
            S._last_save_error=str(exc)
            st.error('Project change not saved / Не удалось сохранить проект: '+str(exc))
            st.stop()
        S.current = chosen
        S.language_output=S.projects[chosen].get("output_language","EN")
        S.prompt_language=S.projects[chosen].get("prompt_language","EN")
        # Clear transient creative work so content from another project cannot appear here.
        for transient in ("results", "script", "script_title", "review", "selected_topic",
                          "studio_output", "studio_output_type", "last_video", "review_url",
                          "review_url_input", "studio_idea", "transcript", "review_original",
                          "review_adaptation", "review_adaptation_idea", "review_evidence", "review_source_url",
                          "story_source", "story_ideas", "story_script", "story_draft_source",
                          "story_source_input", "story_guidance", "story_script_custom", "story_script_idea",
                          "story_style_picker", "story_idea_choice", "story_style_for_ideas",
                          "story_reference_picker", "story_reference_marker"):
            S.pop(transient, None)
        S.results = []
        S.script = ""
        S.studio_output = ""
        navigate(S.page)
    menu = [
        ("studio",tr("✨ AI-студия и шаблоны", "✨ AI studio & templates")),
        ("dashboard",tr("🏠 Обзор", "🏠 Overview")),
        ("profile",tr("🎯 Анкета и проекты", "🎯 Profile & projects")),
        ("trends",tr("🔥 Поиск видео", "🔥 Video discovery")),
        ("scripts",tr("✍️ Сценарии и хуки", "✍️ Scripts & hooks")),
        ("week",tr("🗓️ План на неделю", "🗓️ Weekly plan")),
        ("review",tr("🔍 Разбор по ссылке", "🔍 Analyze a link")),
        ("story",tr("📖 История → готовый ролик", "📖 Story → ready-to-film video")),
        ("library",tr("📚 Библиотека", "📚 Library")),
        ("metrics",tr("📈 Мои результаты", "📈 My results")),
        ("team",tr("👥 Команда", "👥 Team")),
        ("settings",tr("⚙️ Настройки", "⚙️ Settings")),
    ]
    label_to_id = {label:key for key,label in menu}
    if S.get("_pending_nav") or S.get("_nav_language") != S.ui_lang:
        page_for_menu=S.get("_pending_nav") or S.page
        S.nav_selection=next((label for key,label in menu if key==page_for_menu),menu[0][1])
        S._pending_nav=None
        S._nav_language=S.ui_lang
    def _on_navigation():
        S.page=label_to_id[S.nav_selection]
    selected = st.radio(tr("Разделы", "Sections"), [label for key,label in menu],
                        index=next((i for i,(key,_) in enumerate(menu) if key==S.page),0),
                        key="nav_selection", on_change=_on_navigation)
    if S.page != label_to_id[selected]: S.page=label_to_id[selected]
    st.divider()
    with st.expander(tr("🔑 Подключения API", "🔑 API connections")):
        S.gemini_key = st.text_input("Gemini API key", type="password", value=S.get("gemini_key", "") or secret("GEMINI_API_KEY"), help="Private session input; not included in exports")
        S.youtube_key = st.text_input("YouTube Data API key", type="password", value=S.get("youtube_key", "") or secret("YOUTUBE_API_KEY"))
        S.gemini_model = st.text_input("Gemini model", value=secret("GEMINI_MODEL") or S.get("gemini_model", "") or "gemini-3.8-flash")
        S.ai_provider = st.selectbox(tr("Нейросеть", "AI provider"),
                                     ["Auto (Gemini → DeepSeek)", "Gemini", "DeepSeek"],
                                     index=0, key="ai_provider_picker")
        S.deepseek_key = st.text_input("DeepSeek API key",type="password",
                                       value=secret("DEEPSEEK_API_KEY") or S.get("deepseek_key", ""))
        st.caption(tr("Ключи не включаются в экспорт. Для постоянного подключения настрой Secrets.",
                      "Keys are excluded from exports. Configure Secrets for persistent API access."))
    if store and not store.remote:
        st.warning(tr("Локальное сохранение: на Streamlit Community Cloud данные могут исчезнуть после перезапуска сервера. Для надёжного хранения подключи Supabase.",
                      "Local storage: Streamlit Cloud can discard this data on redeploy/restart. Connect Supabase for durability."))
    if S._last_save_error: st.error(tr("Сохранение не удалось: ", "Save failed: ")+S._last_save_error)
    if S.get('_flash_message'):
        st.success(S.pop('_flash_message'))
    st.caption(tr("Демонстрационный кабинет · без регистрации и оплаты", "Prototype workspace · no sign-up or payments"))

p = S.projects[S.current]

nav_a,nav_b,nav_c=st.columns([1,1,4])
with nav_a:
    if st.button(tr("← Назад", "← Back"), key="nav_back_button"):
        navigate(S.get("previous_page","studio") if S.get("previous_page")!=S.page else "studio")
with nav_b:
    if st.button(tr("⌂ Инструменты", "⌂ Tools"), key="nav_home_button"):
        navigate("studio")
if S.get("_last_page") != S.page:
    if S.get("_last_page") and S.get("_last_page")!=S.page:
        S.previous_page=S._last_page
    S._last_page=S.page


def header(kicker: str, title: str, caption: str):
    st.markdown(f'<div class="v-hero"><div class="v-kicker">{kicker}</div><h1>{title}</h1><p>{caption}</p></div>', unsafe_allow_html=True)


def add_library(kind: str, title: str, body: str, url: str = ""):
    item={"type":kind, "title":title, "content":body, "url":url,
          "project":S.current, "added":datetime.now().strftime("%Y-%m-%d %H:%M"),
          "creative_style":(S.get("story_style_picker","family") if kind=="story_ideas" else S.get("review_style","animals") if kind in ("analysis","original_script") else "")}
    if any(x.get("project")==S.current and x.get("type")==kind and
           ((kind=='youtube' and bool(url) and x.get('url')==url) or x.get("content")==body)
           for x in S.library):
        st.info(tr("Материал уже сохранён — дубликат не создан.", "Already saved; no duplicate created."))
        return
    if kind == "story_ideas":
        item["source_story"] = S.get("story_draft_source", "")
        item["reference_marker"] = S.get("story_reference_marker", "")
    S.library.append(item)
    try:
        save_state()
        st.success(tr("Сохранено в библиотеку", "Saved to library"))
    except StorageError as exc:
        st.error(tr("Не удалось сохранить: ", "Save failed: ")+str(exc))


def run_ai(kind: str, subject: str, extra: str = "") -> str:
    system, prompt = make_prompt(kind, subject, extra)
    return generate_ai(system,prompt)


def generate_ai(system, prompt):
    provider=S.get("ai_provider","Auto (Gemini → DeepSeek)")
    errors=[]
    if provider != "DeepSeek" and S.gemini_key:
        try: return gemini_generate(S.gemini_key,S.gemini_model,system,prompt)
        except ApiError as e:
            errors.append(str(e))
            if provider == "Gemini" or (not any(k in str(e).upper() for k in ('503', '504', 'UNAVAILABLE', 'DEADLINE_EXCEEDED', 'TIMEOUT', 'TIMED OUT'))):
                raise
    if provider != "Gemini" and S.get("deepseek_key"):
        try: return _deepseek_flash(system,prompt,effort='none')
        except ApiError as e: errors.append(str(e))
    raise ApiError('; '.join(errors) or tr("Подключи API-ключ выбранной нейросети.", "Connect an API key for the selected provider."))



def _vision_images(uploaded_files) -> list[dict]:
    """Convert selected screenshots to capped JPEGs; never persist originals or credentials."""
    images=[]
    for file in list(uploaded_files or [])[:8]:
        try:
            with Image.open(io.BytesIO(file.getvalue())) as source:
                frame=source.convert('RGB')
                frame.thumbnail((1280,1280))
                output=io.BytesIO()
                frame.save(output,format='JPEG',quality=78,optimize=True)
            data=base64.b64encode(output.getvalue()).decode('ascii')
            images.append({'type':'image_url','image_url':{'url':'data:image/jpeg;base64,'+data, 'detail':'auto'}})
        except (OSError, ValueError) as exc:
            raise ApiError('Не удалось прочитать один из кадров / Cannot read one uploaded frame.') from exc
    return images


class _PreparedFrame:
    """Small in-memory frame with the uploader's getvalue() protocol."""
    def __init__(self, raw: bytes):
        self._raw=raw
    def getvalue(self):
        return self._raw


def _frames_from_uploaded_video(video_file):
    """Extract a small, evenly spaced visual sample if ffmpeg is available.

    This is NOT full video/transcript understanding. Uploaded video bytes
    are handled in a temporary directory and not written to Supabase.
    """
    if video_file is None:
        return []
    if not shutil.which('ffmpeg'):
        raise ApiError('Автоизвлечение кадров недоступно на сервере (нет ffmpeg). '
                       'Добавь 4–8 скриншотов ролика вручную.')
    data=video_file.getvalue()
    if not data or len(data)>60*1024*1024:
        raise ApiError('Загрузи MP4/MOV до 60 МБ или используй скриншоты.')
    with tempfile.TemporaryDirectory(prefix='viral_video_') as folder:
        suffix='.mov' if video_file.name.lower().endswith('.mov') else '.mp4'
        source=Path(folder)/('source'+suffix)
        source.write_bytes(data)
        # FPS=1/8 produces up to 8 frames spanning the first 64 seconds.
        target=str(Path(folder)/'frame_%02d.jpg')
        try:
            result=subprocess.run(['ffmpeg','-hide_banner','-loglevel','error',
              '-i',str(source),'-vf','fps=1/8,scale=960:-2','-frames:v','8',
              '-q:v','4','-y',target], capture_output=True,text=True,timeout=35,check=False)
        except (OSError,subprocess.TimeoutExpired) as exc:
            raise ApiError('Не удалось извлечь кадры из видео; используй скриншоты.') from exc
        if result.returncode != 0:
            raise ApiError('Видео не распознано или формат не поддерживается; используй скриншоты.')
        shots=sorted(Path(folder).glob('frame_*.jpg'))
        if not shots:
            raise ApiError('Не удалось найти кадры в видео; используй скриншоты.')
        return [_PreparedFrame(x.read_bytes()) for x in shots]


def analyze_with_frames(system: str, prompt: str, uploaded_files) -> str:
    """DeepSeek Flash vision API, actual uploaded frames only. A YouTube URL is not video footage."""
    if not S.get('deepseek_key'):
        raise ApiError('Для анализа кадров нужен DeepSeek API key / DeepSeek key needed for frame analysis.')
    frames=_vision_images(uploaded_files)
    if not frames:
        return generate_ai(system,prompt)
    message=[{'type':'text','text':prompt + '\nThese uploaded frames are evidence of the video. Their order is the upload order. Do not infer unseen motion, dialogue, edits or exact frame timestamps.'}] + frames
    try:
        response=requests.post('https://api.deepseek.com/chat/completions',
           headers={'Authorization':f"Bearer {S.deepseek_key}", 'Content-Type':'application/json'},
           json={'model':'deepseek-flash','messages':[{'role':'system','content':system},
                  {'role':'user','content':message}], 'temperature':0.55,'stream':False,'reasoning_effort':'low', 'max_tokens':3400}, timeout=(12,100))
        if not response.ok:
            error_text=(response.json().get('error') or {}).get('message','API error') if 'json' in response.headers.get('Content-Type','').lower() else f'HTTP {response.status_code}'
            raise ApiError(f'DeepSeek Vision HTTP {response.status_code}: {str(error_text)[:160]}')
        answer=response.json()['choices'][0]['message']['content']
        if not answer: raise ApiError('DeepSeek did not return an analysis.')
        return str(answer).strip()
    except (requests.RequestException, ValueError, KeyError, IndexError, TypeError) as exc:
        raise ApiError(f'DeepSeek Vision request failed: {str(exc)[:160]}') from exc


CONTENT_STYLES = {
    "animals": "Realistic Animal Comedy",
    "family": "Real-Life Family Comedy — entirely fictional children",
}

def _creative_rules(style: str) -> str:
    """Rules for ORIGINAL ideas, not a reason to distort analysis of source footage."""
    common = (
        "ORIGINAL CONCEPT SAFETY AND REALISM: Plausible everyday situations, natural lighting, "
        "candid smartphone/home-camera appearance, real-world physics, one simple location, "
        "one escalating surprise and one clear punchline. Broad adult appeal, also family-safe. "
        "No dangerous falls, intimidation, distress as entertainment, humiliating pranks, "
        "dangerous stunts, or injury. Never reuse competitor footage, unique dialogue or characters. "
        "For photorealistic AI scenes, remind the publisher to comply with synthetic-media disclosure rules. "
    )
    if style == "family":
        return common + (
            "STYLE: entirely fictional AI children with no resemblance to real or identifiable children. "
            "Kind, candid, age-appropriate household comedy involving natural reactions and everyday surprises. "
            "Small children are supervised and safe; no unsafe infant sleep setup, loose covers on sleeping "
            "infants, risky handling or frightening pranks. If spoken language is comedically advanced for "
            "the child's age, frame it as clearly staged fictional comedy rather than actual footage. "
            "No demeaning jokes, adult subject matter, or child impersonation. "
            "If the target audience is English-speaking, invent dialogue in natural contemporary "
            "English. Use only idioms or double meanings that genuinely exist in English and are "
            "naturally spoken in the scene; do not translate Russian sayings or wordplay literally. "
            "A misunderstanding must follow a believable child's interpretation, not a forced pun. "
            "No toilet jokes unless the creator explicitly requests them, and avoid childish slapstick."
        )
    return common + (
        "STYLE: photorealistic ordinary cats/dogs and natural pet behavior; accurate anatomy, weight, "
        "paw motion and reaction timing. No clothes, speech, human careers, cartoon behavior, magic "
        "or implausible intentional human-like plotting. Humor should come from harmless pet mishaps, "
        "misdirection, reaction and visual reversal. Never frighten or endanger the animals."
    )


def _deepseek_flash(system: str, prompt: str, *, effort: str = 'none', timeout: int = 80) -> str:
    """Bounded DeepSeek Flash call; no hidden unlimited auto-retries."""
    key=S.get('deepseek_key')
    if not key:
        raise ApiError('DeepSeek API key is missing.')
    payload={'model':'deepseek-flash',
        'messages':[{'role':'system','content':system}, {'role':'user','content':prompt}],
        'stream':False, 'reasoning_effort':effort,
        'temperature':0.6, 'max_tokens':3400}
    try:
        response=requests.post('https://api.deepseek.com/chat/completions',
            headers={'Authorization':f'Bearer {key}','Content-Type':'application/json'},
            json=payload, timeout=(12,timeout))
        if not response.ok:
            try: detail=(response.json().get('error') or {}).get('message','')
            except ValueError: detail=''
            raise ApiError(f'DeepSeek HTTP {response.status_code}: {str(detail)[:170]}')
        answer=response.json()['choices'][0]['message']['content']
        if not isinstance(answer,str) or not answer.strip():
            raise ApiError('DeepSeek returned no text. Try again with a shorter task.')
        return answer.strip()
    except requests.Timeout as exc:
        raise ApiError('DeepSeek did not respond in time. The request was stopped; try fewer frames or a shorter task.') from exc
    except requests.RequestException as exc:
        raise ApiError(f'DeepSeek connection error: {str(exc)[:130]}') from exc
    except (ValueError,KeyError,IndexError,TypeError) as exc:
        raise ApiError('DeepSeek response could not be read. Please try once more.') from exc


def analysis_prompts(metadata: str, transcript: str, frame_count: int, style: str = "animals") -> tuple[str,str]:
    lang='Russian' if S.language_output=='RU' else 'English'
    system=(f'You are a careful video editor and creator. Write analysis in {lang}, production prompts in English. '
      'Use only supplied YouTube metadata, user scene notes and actual uploaded still frames. '
      'Separate OBSERVED from INFERRED and UNKNOWN. Never claim to have viewed the entire original video '
      'from a YouTube URL. Do not invent a transcript, editing cuts, music or retention metrics. '
      'Never reproduce a competitor video or their dialogue. Provide practical original, production-ready ideas. '
      'For ORIGINAL ideas only, obey: '+_creative_rules(style)+' '
      f'Current date: {datetime.now().date().isoformat()}.')
    prompt=(f'SOURCE METADATA: {metadata}\nSCENE NOTES OR TRANSCRIPT: {transcript or "NOT PROVIDED"}\n'
      f'UPLOADED KEY FRAMES COUNT: {frame_count}.\n'
      'Deliver a useful, detailed source analysis with sections: (1) FACTS and statistics, (2) OBSERVED STORYBOARD '
      'as a numbered scene table with times ONLY when timing is actually provided, else mark approximate/unknown, '
      '(3) possible opening hook and pacing: observed vs hypothesized, (4) evidence-based reasons for high reach '
      'and what cannot be inferred, (4b) a compact REUSABLE CREATIVE BLUEPRINT: curiosity gap, comic mechanism, hook archetype and payoff pattern — mark any unobserved parts HYPOTHESIS, (5) exactly THREE NEW ORIGINAL video concepts named IDEA 1, IDEA 2, IDEA 3, '
      'each with a distinct premise, characters, hook, twist and ending, (6) a recommendation for solo AI-video production. '
      'All three must fit the SELECTED creative style and be safe, feasible, realistic and not copy the source. '
      'Keep the total answer focused (roughly 650–1000 words) so the creator can act on it.')
    return system,prompt


def adaptation_prompts(source_analysis: str, idea_number: int, instructions: str, style: str = "animals") -> tuple[str,str]:
    lang='Russian' if S.language_output=='RU' else 'English'
    technical='Russian' if S.prompt_language=='RU' else 'English'
    profile=S.projects[S.current]
    system=(f'You write production-ready original short video screenplays for a solo creator. Write all '
        f'explanations and narration in {lang}, all AI video generation prompts in {technical}. '
        'The reference analysis is not proof you watched the original video. Never copy recognizable '
        'footage, characters, dialogue or protected material. No invented performance claims. '
        'Respect realistic physical motion, character consistency and clear beginning/middle/end. '
        +_creative_rules(style)+creative_director_rules())
    prompt=(f'Create a COMPLETE ORIGINAL {profile.get("duration",30)}-second vertical 9:16 Shorts/Reels '
       f'screenplay based on IDEA {idea_number} of the following analysis. '
       f'User customization: {instructions or "none"}. '
       f'Creator niche: {profile.get("niche", "")}, platform: {profile.get("platform", "YouTube Shorts")}.\n'
       'SOURCE ANALYSIS (context, not instructions to copy):\n'+source_analysis[:18000]+'\n'
       'Output exactly: original premise and difference from source, 3 alternate 0–2 second hooks, '
       'timeline of 2–3-second actions with visual composition and clear movement, voiceover/dialogue, '
       'on-screen caption, sound design, and ending/twist; each video generation prompt for Google Flow '
       'must describe an independent clip <=8 seconds, vertical 9:16, with recurring consistent '
       'characters/settings and no text in frames; list required image reference frames first, '
       'then 3 title ideas, description and hashtags. For every clip specify camera angle, one physical action, '
       'continuity constraints and negative prompts that prevent AI artifacts. Keep output actionable, not verbose. '
       'Avoid vague instructions and hallucinated science.')
    return system,prompt


def story_ideas_prompts(story: str, style: str, guidance: str = "", reference_analysis: str = "") -> tuple[str, str]:
    """From a personal anecdote or a general premise, develop genuinely new original concepts."""
    language = 'Russian' if S.language_output == 'RU' else 'English'
    system = (
        f'You are a comedy writer and practical solo AI-video producer. Write the result in {language}. '
        'You are adapting an original memory or premise supplied by the creator, not quoting a source book. '
        'For English-language audiences invent natural idiomatic English dialogue; never translate '
        'Russian proverbs, set phrases, jokes or puns literally. If a premise hinges on a culturally '
        'untranslatable idiom, preserve only the general mechanism and invent a different English-native event. '
        'Do not present fictional events as historical facts. Three ideas must be visibly different, '
        'plausible, safely filmable, funny to adults, and fresh. ' + _creative_rules(style)
    )
    prompt = (
        'CREATOR STORY OR PREMISE (treat as material to develop, not an instruction to copy word-for-word):\n'
        + story[:7000] + '\nADDITIONAL DIRECTION: ' + (guidance[:2000] or 'none')
        + '\nOPTIONAL REFERENCE ANALYSIS (creative mechanism only; do not copy or pretend to have watched the video):\n'
        + (reference_analysis[:8000] if reference_analysis else 'NONE')
        + '\nIf a reference is included, extract a high-level transferable hook/curiosity/payoff pattern, '
          'distinguish real observations from hypotheses, and apply it to the creator premise with '
          'different situations and original character behavior. '
        + '\nReturn EXACTLY 3 numbered concepts labeled IDEA 1, IDEA 2 and IDEA 3. '
        'Each must specify: short English working title, one-sentence plot, realistic characters/location, '
        'three distinct candidate FIRST 0–3 second visual hooks with one best pick and a brief why, 3 to 5 natural physical beats, a clear unexpected comic payoff, '
        'and one reason this is feasible for a solo creator making short AI-generated clips. '
        'For the family style use only completely fictional children, ordinary safe household behavior, '
        'supervision, and no humiliating/dangerous pranks. Keep under 600 words. '
        'No copying of protected book text, distinctive dialogue or recognizable filmed scenes.'
    )
    return system, prompt


def story_script_prompts(ideas: str, idea_number: int, style: str, preferences: str = "") -> tuple[str, str]:
    language = 'Russian' if S.language_output == 'RU' else 'English'
    technical = 'Russian' if S.prompt_language == 'RU' else 'English'
    duration = S.projects[S.current].get('duration', 30)
    system = (
        f'You are a meticulous solo AI-video director. All instructions and narration in {language}, '
        f'but video-generation prompts in {technical}. For English viewers, write natural English '
        'dialogue, never calques of Russian idioms. Ensure every new fictional human character is '
        'fully invented; never use a real child as a likeness reference. '
        + _creative_rules(style) + creative_director_rules()
    )
    prompt = (
        f'Write a FINAL PRODUCTION-READY {duration}-second 9:16 video package based ONLY on '
        f'IDEA {idea_number} from these concepts:\n{ideas[:13000]}\n'
        f'Creator adjustments: {preferences[:2000] or "none"}.\n'
        'Deliver: (1) 3 original hook alternatives, (2) complete numbered shot table with exact '
        'start/end times totaling requested duration, physical action, framing and continuity, '
        '(3) brief dialogue or narration (if any), sound design and final comic payoff, '
        '(4) ready-to-copy English prompts for each independent <=8-second Google Flow/Kling clip: '
        'consistent character appearance, one action per clip, location/light/camera, natural physics, '
        'negative artifacts; no baked-in text, (5) optional on-screen captions, titles, description '
        'and tags, (6) a safety/plausibility checklist. Do NOT require extra story development '
        'by the creator and do NOT invent a source video or imagined observed footage.'
    )
    return system, prompt


if S.page == "studio":
    if S.ui_lang == "RU":
        st.markdown("""<div class="studio-hero"><div class="studio-kicker">VIRAL STUDIO AI / CREATOR WORKSPACE</div><h1>Создавай то, что хочется досмотреть</h1><p>Одна идея → сценарий, карусель, контент-план или визуальный промпт. Все инструменты в одном месте.</p></div>""", unsafe_allow_html=True)
    else:
        st.markdown("""<div class="studio-hero"><div class="studio-kicker">VIRAL STUDIO AI / CREATOR WORKSPACE</div><h1>Make content worth watching</h1><p>One idea → a script, carousel, content calendar or visual prompt. All in one workspace.</p></div>""", unsafe_allow_html=True)
    st.caption(tr("Личная версия: черновики без API, генерация через Gemini или DeepSeek, поиск через YouTube API.",
                  "Personal version: drafts without API, generation via Gemini or DeepSeek, discovery via YouTube API."))
    a_lang,b_lang,c_lang=st.columns(3)
    with a_lang:
        S.language_output=st.selectbox(tr("Язык материала", "Document language"),["EN","RU"],
             index=["EN","RU"].index(S.language_output), format_func=lambda x: "English" if x=="EN" else "Русский")
    with b_lang:
        S.prompt_language=st.selectbox(tr("Язык промптов", "Prompt language"),["EN","RU"],
             index=["EN","RU"].index(S.prompt_language), format_func=lambda x: "English" if x=="EN" else "Русский")
    p["output_language"]=S.language_output
    p["prompt_language"]=S.prompt_language
    st.caption(tr("Язык сайта, документа и технических промптов выбираются отдельно.",
                  "Interface, document and generation-prompt languages are independent."))
    idea_text = st.text_area(tr("Расскажи, что хочешь сделать", "Describe your idea"),
                            key="studio_idea",
                            placeholder=tr("Например: 30-секундный Shorts о том, как курица формирует яйцо. Реалистично, быстрые кадры, английская озвучка.",
                                           "For example: make a 30-second Short explaining how a hen forms an egg. Realistic, close-ups, English voiceover."),
                            height=110)
    a,b,c,d=st.columns([1.6,1.3,1.0,1.0])
    with a:
        if st.button(tr("✨ Создать с AI", "✨ Generate with AI"),type="primary",width='stretch',key="generate_top"):
            if not idea_text.strip():
                st.warning(tr("Напиши задание выше, затем нажми «Создать с AI».",
                              "Write a request above before generating."))
            else:
                S._generate_from_top=True
    with b:
        if st.button(tr("Подобрать инструмент", "Suggest a tool"), width='stretch'):
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
                navigate(S.page)
    with c:
        if st.button(tr("🔍 Найти видео", "🔍 Discover"), width='stretch'):
            navigate("trends")
    with d:
        if st.button(tr("📅 План недели", "📅 Weekly plan"), width='stretch'):
            navigate("week")

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
                if st.button(tr("Выбрать", "Select") if not active else tr("✓ Выбрано", "✓ Selected"),
                             key="recipe_"+r.slug, width='stretch'):
                    if r.kind=="navigate":
                        S.page=r.route
                    else:
                        S.studio_recipe=r.slug
                        S.studio_output=""
                    navigate(S.page)

    selected=CATALOG.get(S.studio_recipe)
    st.divider()
    if selected:
        st.subheader(tr("Мастерская: ", "Workshop: ") + recipe_title(selected.slug,S.ui_lang))
    if selected:
        st.caption(selected.ru_desc if S.ui_lang=="RU" else selected.en_desc)
    if not selected:
        st.info(tr("Сначала введи задачу и нажми «Выбрать» под нужным инструментом.",
                   "Write your request, then click Select on the tool you want."))
    if not idea_text.strip():
        st.info(tr("Напиши идею в поле вверху. Можно использовать тему канала, если конкретная идея ещё не готова.",
                   "Enter an idea above. Your channel niche can be used as a starting point."))
    gen_a,gen_b=st.columns(2)
    with gen_a:
        if st.button(tr("Создать бесплатный черновик", "Create free draft"), width='stretch', disabled=not bool(selected)):
            if not selected:
                st.warning(tr("Сначала выбери инструмент.", "Select a tool first."))
            else:
                S.studio_output=fallback_draft(selected.slug,idea_text or p["niche"],p,S.ui_lang)
                S.studio_output_type="draft"
    with gen_b:
        generated_from_bottom=False
        st.caption(tr("Для AI-генерации используй одну основную кнопку наверху.", "Use the single Generate with AI button above."))
        if generated_from_bottom or bool(S.pop("_generate_from_top",False)):
            if not selected:
                st.warning(tr("Сначала выбери инструмент под его карточкой.", "Select a tool card first."))
            elif not (S.gemini_key or S.get("deepseek_key")):
                st.warning(tr("Добавь Gemini или DeepSeek API key слева.", "Connect Gemini or DeepSeek API key in the sidebar."))
            else:
                sys_msg,prompt=ai_prompts(selected.slug,idea_text or p["niche"],p,S.language_output)
                sys_msg += (" Technical generator prompts must be in " + ("Russian" if S.prompt_language=="RU" else "English") + ". ")
                sys_msg += " Only deliver the selected tool's output, do not append unrelated formats or scripts. "
                if selected.slug in ("reels_script", "short_story", "reels_teardown"):
                    sys_msg += " " + creative_director_rules()
                try:
                    with st.spinner(tr("Готовим результат с AI…", "Creating with AI…")):
                        S.studio_output=generate_ai(sys_msg,prompt)
                        S.studio_output_type="ai"
                        add_library(selected.slug,(idea_text.strip() or p["niche"])[:90],S.studio_output)
                except ApiError as e:
                    st.error(str(e))
    if S.studio_output and selected:
        if S.studio_output_type=="draft":
            st.info(tr("Это шаблонный черновик без AI-генерации и без проверки трендов.", "This is a rule-based draft, not an AI generation or trend report."))
        else:
            st.caption(tr("Результат AI. Проверь факты, даты и пригодность сценария перед публикацией.",
                          "AI output. Verify claims, dates and production details before publishing."))
        with st.container(border=True):
            st.markdown(S.studio_output)
        exports_ui(S.studio_output,selected.slug,(idea_text.strip() or p["niche"])[:90],"studio_export")
        if st.button(tr("♡ Сохранить в библиотеку", "♡ Save to library"), key="save_studio", width='stretch'):
            add_library(selected.slug,(idea_text.strip() or p["niche"])[:90],S.studio_output)
        if st.button(tr("← Все инструменты", "← All tools"),key="studio_back"):
            navigate("studio")
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
            navigate("scripts")
    with right:
        st.markdown(f'<div class="v-card"><h3>{tr("Что действительно работает в этой версии", "What works in this version")}</h3><p>✓ {tr("Анкета, план, шаблоны и библиотека", "Profiles, plans, templates and library")}</p><p>✓ {tr("Настоящие данные YouTube при наличии API-ключа", "Real YouTube data when API is connected")}</p><p>✓ {tr("AI-сценарии через Gemini или DeepSeek", "AI scripts using Gemini or DeepSeek")}</p></div>', unsafe_allow_html=True)
        st.info(tr("Автопубликация, анализ Instagram/TikTok, многопользовательский доступ и генерация видео пока не подключены.", "Auto-posting, Instagram/TikTok analytics, multiuser access and video generation are not integrated yet."))

elif S.page == "profile":
    header("01 / CREATOR DNA",tr("Анкета автора", "Creator profile"),tr("Эти ответы определяют стиль будущих сценариев.", "Your answers shape the scripts and calendar."))
    new_name = st.text_input(tr("Название нового проекта", "New project name"), placeholder="Second channel")
    if st.button(tr("＋ Создать проект", "＋ Create project")):
        name = new_name.strip()
        if not name: st.warning(tr("Введите название.", "Enter a name."))
        elif name in S.projects: st.warning(tr("Такой проект существует.", "This project exists."))
        else:
            S.projects[name]=copy.deepcopy(DEFAULT_PROFILE)
            S.current=name
            S.language_output=S.projects[name]["output_language"]
            S.prompt_language=S.projects[name]["prompt_language"]
            S._pending_project=name
            S._flash_message=tr("Проект создан и выбран. Теперь заполни его отдельную анкету.",
                                "Project created and selected. Fill out its separate profile.")
            navigate("profile")
    a,b=st.columns(2)
    with a:
        p["niche"] = st.text_input(tr("Ниша", "Niche"), value=p["niche"],key=profile_key('niche'))
        p["audience"] = st.text_area(tr("Кто смотрит", "Target audience"), value=p["audience"], height=90,key=profile_key('audience'))
        p["tone"] = st.text_area(tr("Манера речи и стиль", "Tone of voice"), value=p["tone"], height=90,key=profile_key('tone'))
        p["handle"] = st.text_input(tr("Ссылка на канал (для справки)", "Channel URL (reference only)"),value=p.get("handle",""),key=profile_key('handle'))
    with b:
        p["platform"] = st.selectbox(tr("Главная платформа", "Main platform"),["YouTube Shorts","Instagram Reels","TikTok","Telegram","Pinterest"],index=["YouTube Shorts","Instagram Reels","TikTok","Telegram","Pinterest"].index(p["platform"]) if p["platform"] in ["YouTube Shorts","Instagram Reels","TikTok","Telegram","Pinterest"] else 0,key=profile_key('platform'))
        p["goal"] = st.text_input(tr("Цель", "Goal"),value=p["goal"],key=profile_key('goal'))
        p["duration"] = st.slider(tr("Длина видео (сек)", "Video duration (sec)"),min_value=12,max_value=60,value=int(p["duration"]),key=profile_key('duration'))
    st.caption(tr("Изменения автосохраняются в подключённом хранилище; надёжность зависит от выбранного способа хранения.",
                  "Changes auto-save to the configured store; durability depends on its backend."))

elif S.page == "trends":
    header("02 / DISCOVER", tr("Поиск популярных видео", "Discover high-performing videos"),
           tr("Данные YouTube, а не придуманные показатели. Приближённые сигналы, не гарантия вирусности.", "Real YouTube data, not invented metrics. Signals are not proof of virality."))
    if S.youtube_key:
        st.success(tr("YouTube API подключён. Ищем только видео, удовлетворяющие выбранным фильтрам.",
                      "YouTube API connected. Only videos passing your filters are shown."))
    else:
        st.warning(tr("Для поиска добавь YouTube Data API key слева.", "Connect YouTube Data API key in the sidebar."))
    c1,c2,c3=st.columns([2,1,1])
    with c1: query = st.text_input(tr("Ниша / поисковый запрос", "Niche / search query"),value=p["niche"])
    with c2: days = st.selectbox(tr("За период", "Published within"),[1,3,7,30],index=2,format_func=lambda n:tr(f"{n} дней",f"{n} days"))
    with c3: language = st.selectbox(tr("Язык поиска", "Search language"),["en","ru","es","de","fr"],index=0 if S.ui_lang=="EN" else 1)
    minviews_a,short_b=st.columns([2,1])
    with minviews_a:
        min_views=st.selectbox(tr("Минимум просмотров", "Minimum views"),[10000,100000,500000,1000000],index=1)
    with short_b:
        short_only=st.checkbox(tr("Короткие видео (до 3 минут)", "Short videos (up to 3 min)"),value=True)
    st.caption(tr("YouTube не гарантирует идентификацию Shorts через API. Поиск может расходовать до 300 единиц квоты за раз.",
                  "YouTube API cannot definitively identify Shorts; a search may cost up to 300 quota units."))
    if st.button(tr("Найти реальные видео", "Search real videos"),type="primary"):
        if not S.youtube_key: st.warning(tr("Сначала добавь YouTube API key.", "First add a YouTube API key."))
        else:
            try:
                with st.spinner(tr("Получаем данные YouTube...", "Fetching YouTube data...")):
                    S.results=search_youtube(query,S.youtube_key,days=days,language=language,
                                             min_views=min_views,short_only=short_only)
            except ApiError as e:
                st.error(tr('Поиск не выполнен: ', 'Search failed: ')+str(e))
                S._youtube_search_failed=True
            else:
                S._youtube_search_failed=False
    if S.results:
        st.caption(tr("Сортировка: средние просмотры в день (примерная оценка на основе даты публикации).", "Sorted by estimated views per day since publication."))
        results=sorted(S.results,key=lambda x:x["views_per_day"],reverse=True)
        for v in results:
            with st.container(border=True):
                a,b=st.columns([1,2.4])
                with a:
                    if v["thumbnail"]: st.image(v["thumbnail"],width='stretch')
                with b:
                    st.markdown(f"**{v['title']}**")
                    st.caption(f"{v['channel']} · {v['published'][:10]} · {v['duration_s']}s")
                    st.write(f"👁 {format_num(v['views'])} · {tr('в день','per day')} {format_num(v['views_per_day'])} · {tr('просмотры/подписчики','views/subscribers')}: {v['view_to_subscriber'] if v['view_to_subscriber'] is not None else '—'}")
                    st.link_button(tr("Открыть ролик", "Open video"),v["url"])
                    if st.button(tr("Анализировать →", "Analyze →"),key="analyze_"+v["id"]):
                        S.review_url=v["url"]
                        S.pop('review_url_input',None)
                        S.last_video=v
                        S.review=''; S.review_original=''; S.review_adaptation=''
                        S.review_source_url=''
                        navigate("review")
                    if st.button(tr("Сохранить в библиотеку", "Save to library"),key="save_"+v["id"]):
                        add_library("youtube",v["title"],f"Channel: {v['channel']}. Views: {v['views']}. Published: {v['published']}.",v["url"])
                        st.toast(tr("Добавлено", "Saved"))
    elif not S.get('_youtube_search_failed',False):
        st.info(tr("Подходящие видео пока не найдены. Уменьши порог просмотров, расширь период или уточни запрос.",
                   "No matching videos. Lower minimum views, widen dates, or refine the topic."))

elif S.page == "scripts":
    header("03 / SCRIPT LAB",tr("Сценарист и 5 хуков", "Script lab & 5 hooks"),tr("Короткие, точные кадры, таймкоды и промпты для видео.", "Compact scenes, timing and prompts for AI-video tools."))
    topic=st.text_input(tr("Тема ролика", "Video topic"),value=S.selected_topic or "How a chicken egg forms")
    extra=st.text_area(tr("Дополнительные пожелания", "Extra instructions"),placeholder=tr("Реалистично, научно точно, без повторов...", "Realistic, scientifically accurate, no repeated shots..."),height=90)
    st.subheader(tr("Пять черновых начал (без AI)", "Five draft hooks (without AI)"))
    st.caption(tr("Это шаблонные подсказки. Для содержательных хуков по фактам используй генерацию AI и проверь результат.",
                  "These are editable sketches. For subject-specific, factual hooks use AI generation and verify its claims."))
    hooks=sample_hooks(topic,p["niche"],S.ui_lang)
    for i,(kind,h) in enumerate(hooks):
        st.markdown(f'<div class="v-card" style="min-height:40px;padding:13px 18px;margin:7px 0"><span class="v-tag">{i+1:02} · {safe_html(kind)}</span> {safe_html(h)}</div>',unsafe_allow_html=True)
    a,b=st.columns(2)
    with a:
        if st.button(tr("Создать шаблон бесплатно", "Create free template"),width='stretch'):
            S.script=demo_script(topic,p["niche"],S.language_output,p["duration"])
            S.script_title=topic
            add_library("script",topic,S.script)
    with b:
        if st.button(tr("✨ Сгенерировать сценарий с AI", "✨ Generate with AI"),type="primary",width='stretch'):
            try:
                with st.spinner(tr("Создаём сценарий...", "Generating script...")):
                    S.script=run_ai("script",topic,extra)
                    S.script_title=topic
                    add_library("script",topic,S.script)
            except ApiError as e: st.error(str(e))
    if S.script:
        st.divider()
        st.markdown(S.script)
        exports_ui(S.script,"Script",S.script_title,"script_export")
        if st.button(tr("♡ Сохранить в библиотеку", "♡ Save in library")):
            add_library("script",S.script_title,S.script)
            st.toast(tr("Сценарий сохранён", "Script saved"))

elif S.page == "week":
    header("04 / EDITORIAL CALENDAR",tr("План на семь дней", "Seven-day calendar"),tr("Меняй темы, отмечай готовность и открывай сценарии одним нажатием.", "Edit topics, track progress and jump into script writing."))
    a,b=st.columns(2)
    with a:
        if st.button(tr("Создать шаблон недели", "Build week template"),width='stretch'):
            for i in range(7):
                S.pop(f"topic_{S.current}_{i}", None)
                S.pop(f"status_{S.current}_{i}", None)
            p["week"]=demo_week(p["niche"],S.ui_lang)
    with b:
        if st.button(tr("✨ План недели с AI", "✨ Create AI week plan"),type="primary",width='stretch'):
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
        status_options=["planned","filming","review","ready","published"]
        status_labels={"planned":tr("План", "Planned"),"filming":tr("Снимаем", "Filming"),"review":tr("Правки", "Review"),"ready":tr("Готово к публикации", "Ready to publish"),"published":tr("Опубликовано", "Published")}
        for i,item in enumerate(p["week"]):
            with st.container(border=True):
                top,stat,open_button=st.columns([3.6,1.4,1.2])
                with top:
                    st.caption(labels[i])
                    item["topic"]=st.text_input(tr("Тема", "Topic"),value=item["topic"],key=f"topic_{S.current}_{i}",label_visibility="collapsed")
                with stat:
                    item["status"]=st.selectbox(tr("Статус", "Status"),status_options,index=status_options.index(item.get("status","planned")) if item.get("status","planned") in status_options else 0,format_func=lambda x:status_labels[x],key=f"status_{S.current}_{i}")
                with open_button:
                    st.caption(" ")
                    if st.button(tr("Сценарий →", "Script →"),key=f"scriptday_{S.current}_{i}"):
                        S.selected_topic=item["topic"]
                        navigate("scripts")
        done=sum(x["status"]=="published" for x in p["week"])
        st.progress(done/7,text=tr(f"Опубликовано {done} из 7",f"Published {done} of 7"))

elif S.page == "review":
    header('05 / CREATIVE DECONSTRUCTION',
           tr('Анализ → 3 идеи → свой сценарий', 'Analyze → 3 ideas → original script'),
           tr('От реальных данных и кадров к готовой раскадровке и промптам.',
              'From real evidence and selected frames to your own complete storyboard.'))
    st.subheader(tr('Стиль будущего оригинального видео', 'Style of YOUR new video'))
    style_index=0 if S.get('review_style','animals')=='animals' else 1
    style_selected=st.selectbox(tr('Выбери направление', 'Choose direction'),
        list(CONTENT_STYLES), index=style_index,
        format_func=lambda k:CONTENT_STYLES[k], key='review_style_picker')
    if S.get('review_style','animals') != style_selected and S.get('review_original'):
        st.warning(tr('После смены направления перезапусти анализ, чтобы три идеи соответствовали новому стилю.',
                      'Rerun the analysis after changing style to regenerate matching ideas.'))
    S.review_style=style_selected
    st.caption(tr('Стиль влияет на новые идеи и сценарий, но не искажает анализ оригинального ролика.',
                  'Style guides original ideas and scripts, not factual analysis of the source.'))
    st.info(tr('YouTube API показывает статистику, но не передаёт само видео для просмотра. '
               'Для визуального анализа добавь ключевые кадры (скриншоты) или описание сцен. '
               'DeepSeek Flash сможет изучить загруженные кадры.',
               'YouTube API supplies metadata, not actual video footage. Upload key frames or scene notes '
               'for a visual analysis with DeepSeek Flash.'))
    url=st.text_input(tr('Ссылка на видео', 'Video link'),
        value=S.get('review_url',''), placeholder='https://www.youtube.com/shorts/...',key='review_url_input')
    vid=youtube_id(url) if url else None
    if S.get('review_url_input') != S.get('review_url'):
        S.review_url=S.review_url_input
        if S.get('review_source_url') != url:
            S.review=''; S.review_original=''; S.review_adaptation=''; S.review_evidence=''
        if S.get('last_video') and S.last_video.get('id')!=vid:
            S.last_video=None
    if url and not vid:
        st.caption(tr('Для других платформ можно использовать свои кадры и описание; статистика YouTube недоступна.',
                      'For other platforms, use your own frames and notes; YouTube metrics are unavailable.'))
    transcript=st.text_area(tr('Текст речи / описание сцен и их время (необязательно)',
                               'Transcript / scene descriptions and timing (optional)'),
        placeholder=tr('Например: 0–2 с: кот тянется к тарелке; 2–5 с: собака замечает...','e.g. 0–2s: cat reaches for plate; 2–5s: dog notices...'),
        height=120,key='review_transcript')
    frames=st.file_uploader(tr('Ключевые кадры видео (до 8 PNG/JPG/WebP)',
                               'Key video frames (up to 8 PNG/JPG/WebP)'),
                            type=['png','jpg','jpeg','webp'],accept_multiple_files=True,key='review_frames')
    video_upload=st.file_uploader(tr('Или загрузи видео MP4/MOV (до 60 МБ; при наличии ffmpeg)',
                                      'Or upload MP4/MOV (up to 60 MB, if ffmpeg is installed)'),
                                  type=['mp4','mov'],key='review_video_upload')
    if video_upload:
        st.caption(tr('Из видео будет взято до 8 кадров с интервалом примерно 8 секунд. '
                      'Аудио и промежуточные движения не анализируются; для точности добавь описание сцен.',
                      'Up to 8 still frames roughly 8 seconds apart. Audio and motion between frames '
                      'are not examined; add scene notes for detail.'))
    if frames and len(frames)>8:
        st.warning(tr('Будут рассмотрены первые 8 кадров.', 'Only the first 8 frames will be used.'))
    if frames:
        st.caption(tr(f'Добавлено кадров: {min(len(frames),8)}. Порядок загрузки = порядок сцен. Кадры не записываются в Supabase.',
                      f'{min(len(frames),8)} frames. Upload order is scene order. Images are not stored in Supabase.'))
    if st.button(tr('Получить статистику YouTube', 'Get YouTube facts'),key='review_facts'):
        if not vid: st.warning(tr('Укажи YouTube-ссылку.', 'Enter a YouTube link.'))
        elif not S.youtube_key: st.warning(tr('Добавь YouTube API key в Secrets.', 'Add YouTube API key in Secrets.'))
        else:
            try:
                S.last_video=get_youtube_video(vid,S.youtube_key)
                if not S.last_video: st.warning(tr('Видео не найдено.', 'Video not found.'))
            except ApiError as err: st.error(str(err))
    video=S.get('last_video') if vid and (S.get('last_video') or {}).get('id')==vid else None
    if video:
        st.markdown(f"**{video.get('title','')}** · {video.get('channel','')}")
        m1,m2,m3=st.columns(3)
        m1.metric(tr('Просмотры','Views'),format_num(video.get('views',0)))
        m2.metric(tr('Лайки','Likes'),format_num(video['likes']) if video.get('likes') is not None else '—')
        m3.metric(tr('В день (среднее)','Avg/day'),format_num(video.get('views_per_day',0)))
    metadata=(f'URL: {url}; title: {video.get("title", "")}; description: {video.get("description", "")}; '
              f'views: {video.get("views", "unknown")}; likes: {video.get("likes", "unknown")}; '
              f'published: {video.get("published", "unknown")}; duration_s: {video.get("duration_s", "unknown")}; '
              f'channel: {video.get("channel", "unknown")}' if video else f'URL: {url}; source metadata unavailable')
    st.subheader(tr('Шаг 1. Разобрать ролик и получить три новые идеи',
                    'Step 1. Analyze the source and get three new ideas'))
    if st.button(tr('✨ Анализировать и предложить 3 идеи', '✨ Analyze and suggest 3 ideas'),
                 type='primary',key='review_deep_analyze',width='stretch'):
        if not (url.strip() or transcript.strip() or frames or video_upload):
            st.warning(tr('Добавь ссылку, описание или кадры.', 'Provide a link, scene notes, or frames.'))
        else:
            try:
                # Re-fetch source only if needed; a failed metadata fetch never fabricates source facts.
                if vid and S.youtube_key and video is None:
                    try:
                        S.last_video=get_youtube_video(vid,S.youtube_key)
                        video=S.last_video
                        if video:
                            metadata=(f'URL: {url}; title: {video.get("title", "")}; description: {video.get("description", "")}; '
                                f'views: {video.get("views", "unknown")}; likes: {video.get("likes", "unknown")}; '
                                f'published: {video.get("published", "unknown")}; duration_s: {video.get("duration_s", "unknown")}; '
                                f'channel: {video.get("channel", "unknown")}')
                    except ApiError as fetch_err:
                        st.warning(tr('Статистика недоступна: ', 'Metadata unavailable: ')+str(fetch_err))
                input_frames=list(frames or [])[:8]
                if video_upload and not input_frames:
                    input_frames=_frames_from_uploaded_video(video_upload)
                system,prompt=analysis_prompts(metadata,transcript,len(input_frames),S.review_style)
                with st.spinner(tr('Анализируем факты, кадры и предлагаем идеи...',
                                   'Analyzing evidence and building original ideas...')):
                    generated=(analyze_with_frames(system,prompt,input_frames) if input_frames else
                        (_deepseek_flash(system,prompt,effort='low') if S.get('ai_provider')=='DeepSeek' else generate_ai(system,prompt)))
                S.review=generated; S.review_original=generated
                S.review_adaptation=''
                S.review_adaptation_idea=None
                S.pop('review_idea_choice',None)
                S.review_source_url=url
                S.review_evidence='frames' if input_frames else ('notes' if transcript.strip() else 'metadata')
                S.review_style_for_analysis=S.review_style
                add_library('analysis',((video or {}).get('title') or url or 'Video analysis')[:90],generated,url)
                st.rerun()
            except ApiError as err: st.error(str(err))
    if S.get('review_original') and S.get('review_source_url')==url:
        style_matches=(S.get('review_style_for_analysis', S.get('review_style','animals'))==S.get('review_style','animals'))
        st.success(tr('Анализ готов. Выбери идею и получи собственный сценарий.',
                      'Analysis ready. Choose an idea to create an original script.'))
        with st.expander(tr('Показать полный анализ и три идеи', 'Full analysis and three ideas'), expanded=True):
            st.markdown(S.review_original)
        exports_ui(S.review_original,'Analysis',((video or {}).get('title') or 'Video')[:70],'deep_review_export')
        st.subheader(tr('Шаг 2. Выбери оригинальную идею', 'Step 2. Pick an original concept'))
        idea=st.radio(tr('Идея из анализа', 'Concept from analysis'),[1,2,3],horizontal=True,
                      format_func=lambda x:tr(f'Идея {x}',f'Idea {x}'),key='review_idea_choice')
        custom=st.text_area(tr('Что изменить в будущем сценарии?', 'Customize your script'),
             placeholder=tr('Например: домашний юмор, бабушка и кот, неожиданный финал, 9:16, без фантастики.',
                            'E.g. realistic domestic humor, a grandmother and a cat, unexpected ending, 9:16.'),
             key='review_custom_idea',height=90)
        if st.button(tr('🎬 Создать МОЙ сценарий с раскадровкой',
                        '🎬 Create MY script and storyboard'),type='primary',
                        key='review_make_script',width='stretch',disabled=not style_matches):
            system,prompt=adaptation_prompts(S.review_original,idea,custom,S.get("review_style","animals"))
            try:
                with st.spinner(tr('Создаём оригинальную историю, тайминг и промпты...',
                                   'Creating your original storyline and shot prompts...')):
                    text=generate_ai(system,prompt)
                S.review_adaptation=text
                S.review_adaptation_idea=idea
                title=(f'Original idea {idea} · '+((video or {}).get('title') or 'Shorts'))[:90]
                add_library('original_script',title,text,url)
                st.rerun()
            except ApiError as err: st.error(str(err))
    if (S.get('review_adaptation') and S.get('review_source_url')==url
            and S.get('review_adaptation_idea')==S.get('review_idea_choice')):
        st.subheader(tr('Шаг 3. Твой готовый сценарий', 'Step 3. Your finished original script'))
        st.markdown(S.review_adaptation)
        exports_ui(S.review_adaptation,'Original_Script',f'Idea_{S.review_idea_choice}_Shorts','review_adapt_export')
        st.caption(tr('Сценарий сохранён в библиотеку этого проекта.',
                      'The original script is saved in this project library.'))

elif S.page == "story":
    header('STORY → VIDEO', tr('Своя история → три идеи → готовый сценарий',
                              'Your story → three ideas → production-ready script'),
           tr('Без YouTube-ссылок. Для реальных воспоминаний и новых оригинальных сюжетов.',
              'No YouTube link needed. Adapt your own memories or original premises.'))
    st.info(tr('Семейные видео: только полностью вымышленные AI-персонажи. '
               'Для английской аудитории — естественный английский юмор, без буквального перевода русских поговорок.',
               'Family videos: fully fictional AI characters only. English-native humor, not literal translations of Russian idioms.'))
    if S.get('story_style_picker') not in CONTENT_STYLES:
        S.story_style_picker='family'
    story_style=st.selectbox(tr('Направление ролика', 'Video genre'), list(CONTENT_STYLES),
        format_func=lambda x: CONTENT_STYLES[x], key='story_style_picker')
    story_text=st.text_area(tr('Опиши случай или придуманный сюжет', 'Describe your experience or original idea'),
        key='story_source_input', height=175, placeholder=tr(
            'Например: мама попросила старшую сестру присмотреть за младенцем. Малыш плакал, сестра пыталась его утешить...',
            'For example: a little girl tries to console her baby brother; when she cries too, he stops and stares.'))
    guidance=st.text_input(tr('Дополнительное пожелание (необязательно)', 'Extra direction (optional)'),
        key='story_guidance', placeholder=tr('Больше визуального юмора, минимум диалогов',
                                            'More visual comedy, minimal dialogue'))
    # Let a personal story borrow a narrative *principle* from a saved YouTube analysis.
    # The reference is optional: the Story → Video workflow works without YouTube.
    available_analyses=[x for x in S.library if x.get('project','My channel')==S.current
                        and x.get('type')=='analysis' and x.get('content')]
    reference_options=['']+[str(i) for i in range(len(available_analyses))]
    story_reference=st.selectbox(
        tr('Использовать приём из анализа YouTube (необязательно)',
           'Borrow storytelling techniques from a saved analysis (optional)'),
        reference_options,
        format_func=lambda x: (tr('Без референса — только моя история', 'No reference — my own story')
                               if x=='' else available_analyses[int(x)].get('title','Analysis')[:85]),
        key='story_reference_picker',
        help=tr('Используются принципы интриги и юмора, не чужие кадры или реплики.',
                'Only general hook and comic principles, never source footage or dialogue.'))
    reference_content=(available_analyses[int(story_reference)].get('content','')
                       if story_reference else '')
    reference_marker=(hashlib.sha256(reference_content.encode()).hexdigest()[:16]
                      if reference_content else '')
    if st.button(tr('✨ Предложить 3 оригинальные идеи', '✨ Generate 3 original concepts'),
                 key='story_generate_ideas', type='primary', width='stretch'):
        if len(story_text.strip()) < 20:
            st.warning(tr('Опиши ситуацию хотя бы двумя предложениями.',
                          'Describe the situation in at least two sentences.'))
        else:
            try:
                sys_msg, user_prompt=story_ideas_prompts(story_text,story_style,guidance,reference_content)
                with st.spinner(tr('Составляем три идеи...', 'Generating three original concepts...')):
                    ideas=generate_ai(sys_msg,user_prompt)
                S.story_ideas=ideas
                S.story_script=''
                S.story_script_idea=None
                S.story_draft_source=story_text.strip()
                S.story_style_for_ideas=story_style
                S.story_reference_marker=reference_marker
                S.story_source=story_text.strip()
                add_library('story_ideas',story_text.strip()[:85],ideas)
                st.rerun()
            except ApiError as exc:
                st.error(str(exc))
    active=bool(S.get('story_ideas'))
    matches=(active and S.get('story_draft_source')==story_text.strip()
             and S.get('story_style_for_ideas')==story_style
             and S.get('story_reference_marker','')==reference_marker)
    if active:
        if not matches:
            st.warning(tr('Исходный текст или стиль изменился. Создай три идеи заново перед сценарием.',
                          'Source text or genre changed. Regenerate the three ideas before writing a script.'))
        st.subheader(tr('Три оригинальных идеи', 'Three original concepts'))
        st.markdown(S.story_ideas)
        exports_ui(S.story_ideas,'Story_Ideas',story_text[:65],'story_ideas_export')
        number=st.radio(tr('Выбери идею для сценария', 'Choose a concept for the script'),
                        [1,2,3],horizontal=True,key='story_idea_choice')
        adjustments=st.text_area(tr('Что изменить в сюжете?', 'Customize the story'),
            key='story_script_custom',height=80,
            placeholder=tr('Например: действие в британском доме; смешная пауза в конце',
                           'For example: set in a British home; a funny silent reaction at the end'))
        if st.button(tr('🎬 Создать готовый сценарий и промпты',
                        '🎬 Create full script and clip prompts'),
                     key='story_make_script',type='primary',width='stretch',disabled=not matches):
            try:
                sys_msg,user_prompt=story_script_prompts(S.story_ideas,number,story_style,adjustments)
                with st.spinner(tr('Создаём раскадровку и промпты...',
                                   'Generating storyboard and clip prompts...')):
                    script=generate_ai(sys_msg,user_prompt)
                S.story_script=script
                S.story_script_idea=number
                add_library('story_script',f'Story idea {number} · {story_text[:60]}',script)
                st.rerun()
            except ApiError as exc:
                st.error(str(exc))
    if matches and S.get('story_script') and S.get('story_script_idea')==S.get('story_idea_choice'):
        st.subheader(tr('Готовый производственный сценарий', 'Production-ready video package'))
        st.markdown(S.story_script)
        exports_ui(S.story_script,'Story_Script',f'Idea_{S.get("story_idea_choice",1)}','story_script_export')

elif S.page == "library":
    header("06 / CREATIVE VAULT",tr("Библиотека идей", "Saved content library"),tr("Сценарии и интересные ролики не теряются в переписке.", "Keep scripts, links and ideas together."))
    if not any(x.get("project","My channel")==S.current for x in S.library):
        st.info(tr("В этом проекте пока нет сохранённых материалов.", "No saved material in this project yet."))
    for i,item in reversed(list(enumerate(S.library))):
        if item.get("project","My channel") != S.current: continue
        with st.expander(f"{item['type'].upper()} · {item['title']} · {item['added']}"):
            if item.get("url"): st.link_button(tr("Открыть источник", "Open source"),item["url"])
            st.markdown(item["content"])
            if item.get('type')=='story_ideas':
                if st.button(tr('📖 Продолжить: создать сценарий',
                                '📖 Continue: make a script'),key=f'continue_story_{i}'):
                    S.story_ideas=item.get('content','')
                    S.story_script=''
                    S.story_script_idea=None
                    S.story_source=item.get('source_story') or item.get('title','')
                    S.story_draft_source=S.story_source
                    S.story_source_input=S.story_source
                    S.story_style_for_ideas=item.get('creative_style','family') or 'family'
                    S.story_style_picker=S.story_style_for_ideas
                    stored_ref=item.get('reference_marker','')
                    matching_refs=[str(j) for j, a in enumerate([
                        x for x in S.library if x.get('project','My channel')==S.current
                        and x.get('type')=='analysis' and x.get('content')])
                        if hashlib.sha256(a.get('content','').encode()).hexdigest()[:16]==stored_ref]
                    S.story_reference_picker=matching_refs[0] if stored_ref and matching_refs else ''
                    S.story_reference_marker=stored_ref if matching_refs else ''
                    navigate('story')
            if item.get('type')=='analysis':
                if st.button(tr('🎬 Продолжить: выбрать идею и создать сценарий',
                                '🎬 Continue: select an idea and generate script'),key=f'continue_{i}'):
                    S.review_url=item.get('url','')
                    S.pop('review_url_input',None)
                    S.review_original=item.get('content','')
                    S.review=item.get('content','')
                    S.review_source_url=item.get('url','')
                    S.review_adaptation=''
                    S.review_idea_choice=1
                    S.review_style=item.get('creative_style','animals')
                    S.review_style_for_analysis=S.review_style
                    S.pop('review_style_picker',None)
                    navigate('review')
            exports_ui(item["content"],item["type"],item["title"],f"library_{i}")
            if st.button(tr("Удалить", "Delete"),key=f"delete_{i}"):
                S.library.pop(i); navigate("library")

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
                existing=next((v for v in S.videos if v.get("project")==S.current and
                               ((video_url.strip() and v.get("url")==video_url.strip()) or
                                (not video_url.strip() and v.get("title")==title.strip()))),None)
                record={"title":title.strip(),"url":video_url.strip(),"views":int(views),"likes":int(likes),
                        "comments":int(comments),"saves":int(saves),"project":S.current,
                        "updated":datetime.now().isoformat(timespec="seconds")}
                if existing: existing.update(record); st.info(tr("Существующая запись обновлена (без дубликата).", "Existing record updated (no duplicate)."))
                else: S.videos.append(record); st.success(tr("Результат добавлен. Он появится в таблице ниже.", "Result added. See the table below."))
            else: st.warning(tr("Укажи название.", "Enter a title."))
    own=[v for v in S.videos if v["project"]==S.current]
    if own:
        rows=[]
        for v in own:
            engagement=round(100*(v["likes"]+v["comments"]+v["saves"])/v["views"],2) if v["views"] else 0
            rows.append({tr("Ролик", "Video"):v["title"],tr("Просмотры", "Views"):v["views"],tr("Лайки", "Likes"):v["likes"],tr("Комментарии", "Comments"):v["comments"],"Interactions / views %":engagement})
        st.dataframe(rows,width='stretch',hide_index=True)
        st.caption(tr("Показатель interactions/views — простое отношение введённых взаимодействий к просмотрам, не официальный ER платформы.", "Interactions/views is a basic ratio of entered interactions to views, not a platform's official engagement rate."))
        st.subheader(tr("Управление записями", "Manage records"))
        for i,v in enumerate(S.videos):
            if v.get("project")!=S.current: continue
            with st.expander(f"{v.get('title','')} · {v.get('views',0)} views", expanded=False):
                with st.form(f'metric_edit_{i}'):
                    new_title=st.text_input(tr('Название', 'Title'),value=v.get('title',''),key=f'metric_title_{i}')
                    new_link=st.text_input(tr('Ссылка', 'Link'),value=v.get('url',''),key=f'metric_link_{i}')
                    cols=st.columns(4)
                    numbers={}
                    for col,key_name,label_ru,label_en in zip(cols,('views','likes','comments','saves'),
                          ('Просмотры','Лайки','Комментарии','Сохранения'),('Views','Likes','Comments','Saves')):
                        with col:
                            numbers[key_name]=st.number_input(tr(label_ru,label_en),min_value=0,
                                        value=int(v.get(key_name,0)),key=f'metric_{key_name}_{i}')
                    if st.form_submit_button(tr('Сохранить изменения', 'Save changes')):
                        if not new_title.strip():
                            st.error(tr('Название обязательно.', 'Title is required.'))
                        else:
                            v.update({'title':new_title.strip(),'url':new_link.strip(),
                                      **{k:int(x) for k,x in numbers.items()},
                                      'updated':datetime.now().isoformat(timespec='seconds')})
                            try:
                                save_state()
                                S._flash_message=tr('Изменения сохранены.', 'Changes saved.')
                                navigate('metrics')
                            except StorageError as e:
                                st.error(tr('Ошибка сохранения: ', 'Save error: ')+str(e))
                if st.button(tr('Удалить запись', 'Delete record'),key=f'metric_del_{i}'):
                    S.videos.pop(i)
                    try:
                        save_state()
                        S._flash_message=tr('Запись удалена.', 'Record deleted.')
                        navigate('metrics')
                    except StorageError as e:
                        st.error(tr('Ошибка сохранения: ', 'Save error: ')+str(e))

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
    if store and store.remote:
        st.success(tr("Supabase настроен. Проверить фактическое чтение можно ниже.",
                      "Supabase configured. Verify actual reads below."))
        if st.button(tr('Проверить облачные данные', 'Verify cloud data'),key='cloud_verify'):
            try:
                cloud=store.load()
                if cloud is None:
                    st.warning(tr('В облаке пока нет записи.', 'No cloud record yet.'))
                else:
                    cloud=validate_restore({'schema':2,**cloud})
                    st.success(tr('Прочитано из Supabase: ', 'Read from Supabase: ')+
                               ', '.join(cloud['projects']))
                    st.write(tr('Активный проект в базе: ', 'Active project in database: ')+str(cloud['current']))
            except (StorageError,ValueError,TypeError,KeyError) as e:
                st.error(tr('Ошибка чтения: ', 'Read error: ')+str(e))
        if st.button(tr('Загрузить сохранённые проекты из облака', 'Reload saved projects from cloud'),
                     key='cloud_reload'):
            try:
                reload_from_storage()
                S._flash_message=tr('Проекты загружены из Supabase.', 'Projects reloaded from Supabase.')
                st.rerun()
            except (StorageError,ValueError,TypeError,KeyError) as e:
                st.error(tr('Не удалось загрузить: ', 'Reload failed: ')+str(e))
    else:
        st.warning(tr("Работает локальная база SQLite. На Streamlit Cloud она может исчезнуть при перезапуске сервера или обновлении. Подключи Supabase по README для постоянного хранения.",
                      "Local SQLite mode: Streamlit Cloud can reset it on redeploy or server restart. Configure Supabase for durability."))
    payload={"schema":2,**persistent_state()}
    st.download_button(tr("↓ Скачать все данные JSON", "↓ Export all data as JSON"),data=json.dumps(payload,ensure_ascii=False,indent=2),file_name="viral_studio_backup.json",mime="application/json",type="primary")
    f=st.file_uploader(tr("Восстановить из JSON-файла", "Restore from JSON backup"),type="json")
    if f and st.button(tr("Восстановить данные", "Restore data")):
        try:
            content=json.load(f)
            assert content.get("schema") in (1,2) and isinstance(content.get("projects"),dict) and content["projects"]
            restored=validate_restore(content)
            # Apply the fully validated backup, then invalidate stale form widgets.
            # Without clearing them, old on-screen values can silently overwrite restored data.
            previous = persistent_state()
            try:
                for k,v in restored.items(): S[k]=copy.deepcopy(v)
                S.current=S.current if S.current in S.projects else next(iter(S.projects))
                save_state()
            except StorageError:
                for k,v in previous.items(): S[k]=v
                raise
            for k in list(S):
                if isinstance(k,str) and (k.startswith('profile_') or
                        k.startswith('topic_') or k.startswith('status_')):
                    del S[k]
            S._pending_project=S.current
            S.results=[]
            S.studio_output=""
            S.script=""
            S._flash_message=tr("Резервная копия восстановлена.", "Backup restored.")
            navigate("settings")
        except StorageError as e:
            st.error(tr("Не удалось сохранить восстановленные данные: ",
                        "Could not save restored data: ")+str(e))
        except (ValueError,AssertionError,TypeError,KeyError) as e:
            st.error(tr("Некорректный файл резервной копии.", "Invalid backup file."))
    st.subheader(tr("Что подключим дальше", "Future integrations"))
    st.markdown(tr("**Позже:** безопасные аккаунты, база данных, Instagram/TikTok с официальным доступом, полноценная обработка видео, транскрибация, карусели и автопубликация.", "**Next:** user authentication, database, authorized Instagram/TikTok integrations, full video analysis, transcription, carousels and publishing."))

st.divider()
st.caption("Viral Studio AI · Independent concept prototype · Unaffiliated with Virales.io or ChatPlace Virale · Data via official YouTube API only when connected")

# Persist edits at the end of successful Streamlit runs. Explicit navigation saves before rerun.
try:
    _payload = persistent_state()
    _digest = hashlib.sha256(json.dumps(_payload,ensure_ascii=False,sort_keys=True).encode()).hexdigest()
    if _digest != S.get("_saved_digest"):
        save_state()
        S._saved_digest=_digest
except StorageError as e:
    S._last_save_error=str(e)
    st.error(tr("Не удалось сохранить изменения. Скачай резервную копию JSON и проверь хранилище: ",
                "Changes were NOT saved. Download a JSON backup and check storage: ")+str(e))
