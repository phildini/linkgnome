"""Link scoring and normalization."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urljoin, urlparse, urlunparse

from linkgnome.fetchers.base import Post, ScoredLink
from linkgnome.link_meta import LinkMetadataCache, fetch_all_titles



def _is_noise_url(url: str) -> bool:
    """Check if URL is a noise/internal link that shouldn't be scored."""
    url_lower = url.lower()

    if "/tags/" in url_lower:
        return True

    if "/@" in url_lower:
        return True

    noise_indicators = [
        "cdn.masto.host",
        "sfo2.cdn.digitaloceanspaces.com",
        "media.mastodon.scot",
        "/web/20",
        "instructure-uploads-ap",
        "mastodon.archive.org",
        "mastodon.social/collec",
        "mastodon.social/@",
        "app.wafrn.net/dashboar",
        "friends.chasmcity.net",
    ]

    for indicator in noise_indicators:
        if indicator in url_lower:
            return True

    if url_lower.startswith("https://www") or url_lower.startswith("http://www"):
        domain_part = url_lower.split("://", 1)[1].split("/", 1)[0].split("?", 1)[0]
        if domain_part in ("www",):
            return True

    parsed = urlparse(url)
    if parsed.netloc in ("www", "www.", "http://www", "https://www"):
        return True

    if url_lower.rstrip("/").removeprefix("https://") in ("www", "www.") or url_lower.rstrip("/") == "https://www.":
        return True

    return False


async def score_links(
    posts: list[Post],
    period_hours: int = 24,
    metadata_cache: "LinkMetadataCache | None" = None,
) -> list[ScoredLink]:
    """Score links from posts based on engagement."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=period_hours)

    filtered_posts = [post for post in posts if post.created_at >= cutoff]

    link_groups: dict[str, list[Post]] = {}

    for post in filtered_posts:
        for url in post.urls:
            if _is_noise_url(url):
                continue
            canonical = normalize_url(url)
            if canonical is None:
                continue
            if canonical not in link_groups:
                link_groups[canonical] = []
            link_groups[canonical].append(post)

    unique_urls = list(link_groups.keys())

    titles: dict[str, str | None] = {}
    if metadata_cache and unique_urls:
        titles = await fetch_all_titles(unique_urls, metadata_cache)

    scored_links = []
    for canonical_url, posts_group in link_groups.items():
        if titles.get(canonical_url) is None and metadata_cache is not None:
            cached = metadata_cache.get(canonical_url)
            if cached and cached["status_code"] >= 400:
                continue

        original_count = sum(1 for p in posts_group if not p.is_boost)
        boost_count = sum(1 for p in posts_group if p.is_boost)
        like_count = sum(p.like_count for p in posts_group)

        score = original_count * 1.0 + boost_count * 0.5 + like_count * 0.25

        if score > 0:
            source_urls = set()
            source_platforms = set()
            for post in posts_group:
                source_urls.add(post.id)
                source_platforms.add(post.platform)

            title = titles.get(canonical_url) or canonical_url

            scored_link = ScoredLink(
                url=canonical_url,
                canonical_url=canonical_url,
                score=round(score, 2),
                post_count=original_count,
                boost_count=boost_count,
                like_count=like_count,
                posts=posts_group,
                source_platforms=source_platforms,
                title=title,
            )
            scored_links.append(scored_link)

    scored_links.sort(key=lambda x: x.score, reverse=True)
    return scored_links


TAG_PATH_PREFIXES = {"/tags/", "/@", "/users/"}

MEDIA_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".gif", ".webp", ".mp4", ".mov", ".mp3",
    ".wav", ".ogg", ".webm", ".avi", ".mkv", ".pdf",
}

MEDIA_HOST_INDICATORS = {
    "cdn.", "cloudfront", "media.", "attachments.", "files.",
    "mastodoncdn.com", "mastocdn.com",
}


def _is_tag_url(url: str) -> bool:
    """Check if URL is a hashtag or profile link."""
    for prefix in ["/tags/", "^#"]:
        if f"{prefix}" in url:
            return True
    return any(
        url.lower().split("://", 1)[-1].startswith(prefix.lstrip("/"))
        for prefix in TAG_PATH_PREFIXES
    )


def _is_media_url(url: str) -> bool:
    """Check if URL is media/CDN content."""
    url_lower = url.lower()
    parsed = urlparse(url_lower)
    host = parsed.netloc
    path = parsed.path

    if any(path.endswith(ext) for ext in MEDIA_EXTENSIONS):
        return True

    if any(ind in host or ind in path for ind in MEDIA_HOST_INDICATORS):
        return True

    return False


def normalize_url(url: str) -> str | None:
    """Normalize a URL for deduplication.
    
    Returns None if the URL should be filtered out (hashtags, media, etc).
    """
    try:
        parsed = urlparse(url)
        if not parsed.scheme or parsed.scheme == "":
            url = f"https://{url}"
            parsed = urlparse(url)

        if _is_tag_url(url) or _is_media_url(url):
            return None

        query_params = parse_qs(parsed.query, keep_blank_values=True)
        tracking_params = {
            "utm_source",
            "utm_medium",
            "utm_campaign",
            "utm_term",
            "utm_content",
            "fbclid",
            "gclid",
            "referrer",
            "ref",
            "source",
            "si",
        }
        query_params = {
            k: v for k, v in query_params.items() if k.lower() not in tracking_params
        }

        normalized = urlunparse(
            (
                parsed.scheme.lower(),
                parsed.netloc.lower().rstrip("."),
                parsed.path.rstrip("/") if parsed.path != "/" else parsed.path,
                parsed.params,
                "&".join(f"{k}={','.join(v)}" for k, v in sorted(query_params.items())),
                "",
            )
        )

        return normalized
    except Exception:
        return None


def follow_redirects(url: str, max_redirects: int = 4) -> str:
    """Follow HTTP redirects to get the canonical URL."""
    import httpx

    try:
        with httpx.Client(
            follow_redirects=False,
            timeout=10.0,
            http2=True,
        ) as client:
            current_url = url
            for _ in range(max_redirects):
                response = client.head(
                    current_url,
                    follow_redirects=False,
                )
                if response.status_code in (301, 302, 303, 307, 308):
                    location = response.headers.get("location")
                    if location:
                        current_url = urljoin(current_url, location)
                    else:
                        break
                else:
                    break
            return current_url
    except Exception:
        return url
