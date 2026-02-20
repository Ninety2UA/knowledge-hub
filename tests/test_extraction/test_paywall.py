"""Tests for paywalled domain detection."""

from knowledge_hub.extraction.paywall import is_paywalled_domain, load_paywalled_domains


def test_is_paywalled_known_domain():
    assert is_paywalled_domain("https://nytimes.com/article") is True
    assert is_paywalled_domain("https://wsj.com/news/story") is True


def test_is_paywalled_with_www():
    """Subdomain www. should still match the base domain."""
    assert is_paywalled_domain("https://www.nytimes.com/2026/01/article") is True


def test_is_paywalled_unknown_domain():
    assert is_paywalled_domain("https://example.com/page") is False


def test_load_paywalled_domains():
    """YAML config loads and returns a frozenset."""
    domains = load_paywalled_domains()
    assert isinstance(domains, frozenset)
    assert "nytimes.com" in domains


def test_paywalled_domains_not_empty():
    """Config file has at least 5 domains."""
    domains = load_paywalled_domains()
    assert len(domains) >= 5
