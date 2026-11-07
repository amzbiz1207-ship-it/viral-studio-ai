"""Optional, official external API calls. All credentials are supplied at runtime."""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
import requests
from core import days_since, iso_duration

BASE = "https://www.googleapis.com/youtube/v3"


class ApiError(Exception):
    pass


def yt_request(path: str, key: str, **params) -> dict:
    if not key:
        raise ApiError("A YouTube Data API key is required.")
    try:
        response = requests.get(f"{BASE}/{path}", params={"key": key, **params}, timeout=15)
        data = response.json()
        if not response.ok:
            desc = data.get("error", {}).get("message", f"HTTP {response.status_code}")
            raise ApiError(str(desc))
        return data
    except requests.exceptions.RequestException as exc:
        raise ApiError(f"Connection error: {exc}") from exc
    except ValueError as exc:
        raise ApiError("The video service returned invalid JSON.") from exc


def _enrich(items: list[dict], key: str) -> list[dict]:
    if not items:
        return []
    ids = [x.get("id", {}).get("videoId") if isinstance(x.get("id"), dict) else x.get("id") for x in items]
    ids = list(dict.fromkeys(x for x in ids if x))
    if not ids:
        return []
    data = yt_request("videos", key, part="snippet,contentDetails,statistics", id=",".join(ids[:50]))
    video_items = data.get("items", [])
    channel_ids = list(dict.fromkeys(x.get("snippet", {}).get("channelId", "") for x in video_items if x.get("snippet", {}).get("channelId")))
    channels = {}
    if channel_ids:
        channel_data = yt_request("channels", key, part="statistics", id=",".join(channel_ids[:50]))
        channels = {x["id"]: x.get("statistics", {}) for x in channel_data.get("items", [])}
    output = []
    for v in video_items:
        sn, stats = v.get("snippet", {}), v.get("statistics", {})
        views = int(stats.get("viewCount", 0))
        likes = int(stats.get("likeCount", 0)) if "likeCount" in stats else None
        channel = channels.get(sn.get("channelId", ""), {})
        subscribers = int(channel.get("subscriberCount", 0)) if not channel.get("hiddenSubscriberCount", False) else None
        age = days_since(sn.get("publishedAt"))
        output.append({
            "id": v["id"], "url": f"https://www.youtube.com/watch?v={v['id']}",
            "title": sn.get("title", ""), "description": sn.get("description", ""),
            "channel": sn.get("channelTitle", ""), "published": sn.get("publishedAt", ""),
            "thumbnail": sn.get("thumbnails", {}).get("medium", {}).get("url", ""),
            "views": views, "likes": likes, "comments": stats.get("commentCount"),
            "subscribers": subscribers,
            "views_per_day": round(views / age),
            "view_to_subscriber": round(views / subscribers, 2) if subscribers and subscribers > 0 else None,
            "duration_s": iso_duration(v.get("contentDetails", {}).get("duration")),
        })
    return output


def search_youtube(query: str, key: str, days: int = 7, limit: int = 18, language: str = "en") -> list[dict]:
    published = datetime.now(timezone.utc) - timedelta(days=days)
    data = yt_request("search", key, part="snippet", q=query, type="video", maxResults=min(limit, 50),
                      order="viewCount", publishedAfter=published.strftime("%Y-%m-%dT%H:%M:%SZ"),
                      relevanceLanguage=language, safeSearch="moderate")
    return _enrich(data.get("items", []), key)


def get_youtube_video(video_id: str, key: str) -> dict | None:
    data = _enrich([{"id": video_id}], key)
    return data[0] if data else None


def gemini_generate(api_key: str, model: str, instruction: str, user_prompt: str) -> str:
    if not api_key:
        raise ApiError("A Gemini API key is required.")
    try:
        from google import genai
        from google.genai import types
    except ImportError as exc:
        raise ApiError("The google-genai package is not installed. Install requirements.txt.") from exc
    try:
        with genai.Client(api_key=api_key) as client:
            response = client.models.generate_content(
                model=model,
                contents=user_prompt,
                config=types.GenerateContentConfig(system_instruction=instruction, temperature=0.75),
            )
        if not response.text:
            raise ApiError("The model returned no text. Please try again.")
        return response.text.strip()
    except ApiError:
        raise
    except Exception as exc:
        raise ApiError(f"Gemini API error: {str(exc)[:400]}") from exc
