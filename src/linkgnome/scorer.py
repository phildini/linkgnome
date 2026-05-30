"""Link scoring and normalization."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlparse, urlunparse

from linkgnome.fetchers.base import Post, ScoredLink
from linkgnome.db import LinkgnomeDB
from linkgnome.link_meta import fetch_all_titles



def _platform_normalize_scores(scored_links: list[ScoredLink]) -> list[ScoredLink]:
    """Normalize scores across platforms so no single platform dominates.

    Computes the median score for each platform, then lifts lower-median
    platforms so all platforms share the same median score.
    """
    platform_scores: dict[Platform, list[float]] = {}
    for link in scored_links:
        for p in link.source_platforms or []:
            platform_scores.setdefault(p, []).append(link.score)

    if len(platform_scores) < 2:
        return scored_links

    medians: dict[Platform, float] = {}
    for p, scores in platform_scores.items():
        sorted_scores = sorted(scores)
        mid = len(sorted_scores) // 2
        if len(sorted_scores) % 2 == 0:
            medians[p] = (sorted_scores[mid - 1] + sorted_scores[mid]) / 2
        else:
            medians[p] = sorted_scores[mid]

    max_median = max(medians.values())
    lift_factors: dict[Platform, float] = {}
    for p, median in medians.items():
        lift_factors[p] = max_median / median if median > 0 else 1.0

    for link in scored_links:
        if link.source_platforms:
            factors = [lift_factors.get(p, 1.0) for p in link.source_platforms]
            link.score = round(link.score * sum(factors) / len(factors), 2)

    scored_links.sort(key=lambda x: x.score, reverse=True)
    return scored_links


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
    db: "LinkgnomeDB | None" = None,
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
    if db and unique_urls:
        titles = await fetch_all_titles(unique_urls, db)

    scored_links = []
    for canonical_url, posts_group in link_groups.items():
        if titles.get(canonical_url) is None and db is not None:
            cached = db.get_url_metadata(canonical_url)
            if cached and cached["status_code"] >= 400:
                continue

        original_count = sum(1 for p in posts_group if not p.is_boost)
        boost_count = sum(1 for p in posts_group if p.is_boost)
        like_count = sum(p.like_count for p in posts_group)

        newest_post = max(posts_group, key=lambda p: p.created_at)
        age_hours = max(0, (datetime.now(timezone.utc) - newest_post.created_at).total_seconds() / 3600)
        decay = 1 - 0.5 * (age_hours / period_hours)

        score = (original_count * 1.0 + boost_count * 0.5 + like_count * 0.25) * decay

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
    scored_links = _platform_normalize_scores(scored_links)

    if db:
        scored_links = _merge_redirect_duplicates(scored_links, db)

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
            "amp",
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


def _merge_redirect_duplicates(
    scored_links: list[ScoredLink], db: LinkgnomeDB
) -> list[ScoredLink]:
    """Merge scored links that redirect to the same final URL.

    After title fetching, check each link's final_url from the DB cache.
    If two links resolve to the same canoncial URL, merge their engagement.
    """
    redirect_map: dict[str, str] = {}
    for link in scored_links:
        meta = db.get_url_metadata(link.url)
        if meta and meta.get("final_url"):
            final_canonical = normalize_url(meta["final_url"])
            if final_canonical and final_canonical != link.url:
                redirect_map[link.url] = final_canonical

    if not redirect_map:
        return scored_links

    merged: dict[str, ScoredLink] = {}
    for link in scored_links:
        target = redirect_map.get(link.url, link.url)
        existing = merged.get(target)
        if existing:
            existing.score = round(existing.score + link.score, 2)
            existing.post_count += link.post_count
            existing.boost_count += link.boost_count
            existing.like_count += link.like_count
        else:
            if target != link.url:
                existing = ScoredLink(
                    url=target,
                    canonical_url=target,
                    score=link.score,
                    post_count=link.post_count,
                    boost_count=link.boost_count,
                    like_count=link.like_count,
                    posts=link.posts,
                    source_platforms=link.source_platforms,
                    title=link.title,
                )
                merged[target] = existing
            else:
                merged[target] = link

    result = list(merged.values())
    result.sort(key=lambda x: x.score, reverse=True)
    return result
