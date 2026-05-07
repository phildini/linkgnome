"""Tests for the link scoring algorithm."""

from datetime import datetime, timedelta, timezone
from linkgnome.fetchers.base import Platform, Post
from linkgnome.scorer import normalize_url, score_links


def _create_post(
    id: str = "test-1",
    urls: list[str] | None = None,
    is_boost: bool = False,
    like_count: int = 0,
    hours_ago: int = 0,
    platform: Platform = Platform.MASTODON,
) -> Post:
    """Helper to create a Post for testing."""
    created_at = datetime.now(timezone.utc) - timedelta(hours=hours_ago)
    return Post(
        id=id,
        platform=platform,
        author="testuser",
        author_display_name="Test User",
        content=f"Check out this link: {urls[0] if urls else 'none'}",
        urls=urls or [],
        created_at=created_at,
        is_boost=is_boost,
        like_count=like_count,
    )


class TestScoreLinks:
    """Tests for the score_links function."""

    def test_basic_scoring_original_post(self):
        """Test that an original post gets 1.0 points."""
        posts = [_create_post(id="post-1", urls=["https://example.com/article"])]
        scored = score_links(posts, period_hours=24)

        assert len(scored) == 1
        assert scored[0].url == "https://example.com/article"
        assert scored[0].score == 1.0
        assert scored[0].post_count == 1
        assert scored[0].boost_count == 0

    def test_boost_scoring(self):
        """Test that a boost gets 0.5 points."""
        posts = [
            _create_post(
                id="post-1", urls=["https://example.com/article"], is_boost=True
            )
        ]
        scored = score_links(posts, period_hours=24)

        assert len(scored) == 1
        assert scored[0].score == 0.5
        assert scored[0].boost_count == 1

    def test_like_scoring(self):
        """Test that likes get 0.25 points each."""
        posts = [
            _create_post(
                id="post-1", urls=["https://example.com/article"], like_count=4
            )
        ]
        scored = score_links(posts, period_hours=24)

        assert len(scored) == 1
        assert scored[0].score == 2.0  # 1.0 (post) + 4 × 0.25 (likes) = 2.0
        assert scored[0].like_count == 4

    def test_combined_scoring(self):
        """Test combined scoring from posts, boosts, and likes."""
        posts = [
            _create_post(id="post-1", urls=["https://example.com/article"]),
            _create_post(
                id="post-2", urls=["https://example.com/article"], is_boost=True
            ),
            _create_post(
                id="post-3", urls=["https://example.com/article"], like_count=4
            ),
        ]
        scored = score_links(posts, period_hours=24)

        assert len(scored) == 1
        assert scored[0].score == 3.5  # 1.0 + (1.0 + 0.5) + (1.0 + 4*0.25)
        assert scored[0].post_count == 2
        assert scored[0].boost_count == 1
        assert scored[0].like_count == 4

    def test_url_deduplication(self):
        """Test that duplicate URLs are grouped together."""
        posts = [
            _create_post(id="post-1", urls=["https://example.com/article"]),
            _create_post(id="post-2", urls=["https://example.com/article"]),
        ]
        scored = score_links(posts, period_hours=24)

        assert len(scored) == 1
        assert scored[0].post_count == 2

    def test_time_filtering(self):
        """Test that posts outside the time window are excluded."""
        old_time = 48
        posts = [
            _create_post(
                id="post-1", urls=["https://example.com/article"], hours_ago=1
            ),
            _create_post(
                id="post-2", urls=["https://example.com/article"], hours_ago=old_time
            ),
        ]
        scored = score_links(posts, period_hours=24)

        assert len(scored) == 1
        assert scored[0].score == 1.0
        assert scored[0].post_count == 1

    def test_sorting_by_score(self):
        """Test that results are sorted by score descending."""
        posts = [
            _create_post(id="post-1", urls=["https://example.com/low"]),
            _create_post(id="post-2", urls=["https://example.com/high"]),
            _create_post(id="post-3", urls=["https://example.com/high"], is_boost=True),
        ]
        scored = score_links(posts, period_hours=24)

        assert len(scored) == 2
        assert scored[0].url == "https://example.com/high"
        assert scored[0].score > scored[1].score

    def test_empty_posts(self):
        """Test that empty post list returns empty scored links."""
        scored = score_links([], period_hours=24)
        assert len(scored) == 0

    def test_no_urls(self):
        """Test that posts without URLs are ignored."""
        posts = [
            _create_post(id="post-1", urls=[]),
        ]
        scored = score_links(posts, period_hours=24)
        assert len(scored) == 0

    def test_multiple_unique_urls(self):
        """Test scoring with multiple unique URLs."""
        posts = [
            _create_post(id="post-1", urls=["https://example.com/a"]),
            _create_post(id="post-2", urls=["https://example.com/b"]),
        ]
        scored = score_links(posts, period_hours=24)

        assert len(scored) == 2
        urls = {s.url for s in scored}
        assert "https://example.com/a" in urls
        assert "https://example.com/b" in urls

    def test_source_platforms_tracking(self):
        """Test that source platforms are correctly tracked."""
        mast_post = _create_post(
            id="post-1",
            urls=["https://example.com/article"],
            platform=Platform.MASTODON,
        )
        bsky_post = _create_post(
            id="post-2",
            urls=["https://example.com/article"],
            platform=Platform.BLUESKY,
        )
        scored = score_links([mast_post, bsky_post], period_hours=24)

        assert len(scored) == 1
        assert scored[0].source_platforms == {Platform.MASTODON, Platform.BLUESKY}


class TestNormalizeUrl:
    """Tests for the normalize_url function."""

    def test_basic_normalization(self):
        """Test basic URL normalization."""
        url = "https://example.com/article/"
        normalized = normalize_url(url)
        assert normalized == "https://example.com/article"

    def test_case_normalization(self):
        """Test that scheme and host are lowercased."""
        url = "HTTPS://Example.COM/Article"
        normalized = normalize_url(url)
        assert normalized == "https://example.com/Article"

    def test_tracking_params_removed(self):
        """Test that tracking parameters are stripped."""
        url = "https://example.com/article?utm_source=twitter&ref=abc&id=123"
        normalized = normalize_url(url)
        assert "utm_source" not in normalized
        assert "ref" not in normalized
        assert "id=123" in normalized

    def test_all_tracking_params_removed(self):
        """Test removal of various tracking parameters."""
        url = "https://example.com/article?utm_medium=email&fbclid=abc123&si=xyz"
        normalized = normalize_url(url)
        assert "utm_medium" not in normalized
        assert "fbclid" not in normalized
        assert "si" not in normalized

    def test_no_scheme_adds_https(self):
        """Test that URLs without scheme get https:// prepended."""
        url = "example.com/article"
        normalized = normalize_url(url)
        assert normalized.startswith("https://")

    def test_fragment_removed(self):
        """Test that URL fragments are removed."""
        url = "https://example.com/article#section"
        normalized = normalize_url(url)
        assert "#" not in normalized

    def test_same_url_normalized_identically(self):
        """Test that equivalent URLs normalize to the same string."""
        url1 = "https://example.com/article?utm_source=twitter"
        url2 = "https://example.com/article/"
        assert normalize_url(url1) == normalize_url(url2)
