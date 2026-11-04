"""Public Bluesky posts about each team: what fans are saying, with attribution and a link.

Runs in the worker with the owner's app password, so the API and browser never reach Bluesky. Search
results are noisy, so a post has to name the team, stand on its own, come from someone who allows
logged-out viewing, and earn some engagement. Definitions: docs/data-synchronization.md#fan-posts.
"""

import re
from collections.abc import Callable, Iterable, Mapping
from datetime import datetime, timedelta
from typing import Any
from urllib.parse import quote

import requests

from app.config import get_settings

ENTRYWAY = "https://bsky.social"
SOURCE = "bluesky_search"
WINDOW = timedelta(days=7)
SEARCH_LIMIT = 50
KEEP_PER_TEAM = 8
MIN_LIKES = 3
MIN_LENGTH = 25
HALF_LIFE_DAYS = 3.0
MAX_DIGIT_SHARE = 0.15

# These nicknames are everyday words or belong to other leagues too; only the full name counts.
FULL_NAME_ONLY = frozenset({
    "Bucks", "Bulls", "Hawks", "Heat", "Hornets", "Jazz", "Kings", "Magic", "Nets", "Pacers",
    "Rockets", "Spurs", "Suns", "Thunder", "Warriors", "Wizards",
})  # fmt: skip

_AUTOMATED = re.compile(r"^\W*(final|halftime|q[1-4]|box score)\b", re.IGNORECASE)
# A public portfolio page shows these posts without review, so anything likely to need one is left
# out: profanity, betting tips, and politics that merely mention a team.
_LEFT_OUT = re.compile(
    r"\b(fuck\w*|shit\w*|bitch\w*|asshole\w*|cunt\w*|dick\w*|nazi\w*|rape\w*|"
    r"parlay\w*|sportsbook\w*|betting|odds|"
    r"trump\w*|maga|biden|harris|democrat\w*|republican\w*|gop|election\w*|vote\w*|ice raids?)\b",
    re.IGNORECASE,
)
_RKEY = re.compile(r"^[A-Za-z0-9._:~-]{1,512}$")
_HANDLE = re.compile(r"^[A-Za-z0-9.-]{1,253}$")

Search = Callable[[str, datetime], list[dict[str, Any]]]


def configured() -> bool:
    settings = get_settings()
    return bool(settings.bluesky_handle and settings.bluesky_app_password)


def client() -> Search:
    """A logged-in search function for one sync run."""
    settings = get_settings()
    timeout = settings.stats_timeout_seconds
    login = requests.post(
        f"{ENTRYWAY}/xrpc/com.atproto.server.createSession",
        json={
            "identifier": settings.bluesky_handle,
            "password": settings.bluesky_app_password.get_secret_value(),
        },
        timeout=timeout,
    )
    login.raise_for_status()
    session = login.json()
    services = (session.get("didDoc") or {}).get("service") or [{}]
    host = services[0].get("serviceEndpoint") or ENTRYWAY
    headers = {"Authorization": f"Bearer {session['accessJwt']}"}

    def search(query: str, since: datetime) -> list[dict[str, Any]]:
        response = requests.get(
            f"{host}/xrpc/app.bsky.feed.searchPosts",
            params={
                "q": query,
                "sort": "top",
                "lang": "en",
                "limit": SEARCH_LIMIT,
                "since": since.isoformat().replace("+00:00", "Z"),
            },  # fmt: skip
            headers=headers,
            timeout=timeout,
        )
        response.raise_for_status()
        return response.json().get("posts") or []

    return search


def team_terms(city: str, name: str) -> list[str]:
    """What a post must contain to be about this team; each term is searched as a phrase."""
    full = f"{city} {name}"
    return [full] if name in FULL_NAME_ONLY else [name, full]


def _names_team(text: str, terms: Iterable[str]) -> bool:
    return any(re.search(rf"\b{re.escape(t)}\b", text, re.IGNORECASE) for t in terms)


def _standalone(post: Mapping[str, Any], text: str) -> bool:
    record = post.get("record") or {}
    if record.get("reply") or len(text) < MIN_LENGTH:
        return False
    embed = str((post.get("embed") or {}).get("$type") or "")
    if "record" in embed:
        return False
    digits = sum(c.isdigit() for c in text)
    return digits / len(text) <= MAX_DIGIT_SHARE and not _AUTOMATED.search(text)


def _labeled(post: Mapping[str, Any]) -> bool:
    """Authors can ask not to be shown to logged-out viewers, and moderation labels posts."""
    author = post.get("author") or {}
    return bool(
        author.get("labels") or post.get("labels") or (post.get("record") or {}).get("labels")
    )


def _url(post: Mapping[str, Any]) -> str | None:
    handle = (post.get("author") or {}).get("handle") or ""
    rkey = str(post.get("uri") or "").rsplit("/", 1)[-1]
    if not _HANDLE.match(handle) or not _RKEY.match(rkey):
        return None
    return f"https://bsky.app/profile/{quote(handle)}/post/{quote(rkey)}"


def score(likes: int, reposts: int, replies: int, age_days: float) -> float:
    """Engagement, with a repost worth two likes, halving every few days."""
    return (likes + 2 * reposts + replies) * 0.5 ** (max(age_days, 0.0) / HALF_LIFE_DAYS)


def transform_posts(
    team_id: int, terms: list[str], posts: Iterable[Mapping[str, Any]], now: datetime
) -> list[dict[str, Any]]:
    """The team's most relevant posts, at most one per author, best first."""
    best: dict[str, dict[str, Any]] = {}
    for post in posts:
        record = post.get("record") or {}
        text = str(record.get("text") or "").strip()
        likes = int(post.get("likeCount") or 0)
        url = _url(post)
        if (
            url is None
            or likes < MIN_LIKES
            or _labeled(post)
            or not _names_team(text, terms)
            or not _standalone(post, text)
            or _LEFT_OUT.search(text)
        ):
            continue
        try:
            posted = datetime.fromisoformat(str(record["createdAt"]).replace("Z", "+00:00"))
        except (KeyError, ValueError):
            continue
        if posted.tzinfo is None or posted < now - WINDOW or posted > now + timedelta(hours=1):
            continue
        author = post["author"]
        reposts = int(post.get("repostCount") or 0)
        replies = int(post.get("replyCount") or 0)
        row = {
            "team_id": team_id,
            "uri": post["uri"],
            "url": url,
            "author_handle": author["handle"],
            "author_name": (author.get("displayName") or "").strip() or None,
            "text": text,
            "posted_at": posted,
            "likes": likes,
            "reposts": reposts,
            "replies": replies,
            "score": score(likes, reposts, replies, (now - posted).total_seconds() / 86400),
        }
        held = best.get(author["handle"])
        if held is None or row["score"] > held["score"]:
            best[author["handle"]] = row
    return sorted(best.values(), key=lambda r: (-r["score"], r["uri"]))[:KEEP_PER_TEAM]
