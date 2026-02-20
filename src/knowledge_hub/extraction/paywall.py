"""Paywalled domain checking with configurable domain list."""

import functools
from pathlib import Path
from urllib.parse import urlparse

import yaml


_CONFIG_PATH = Path(__file__).resolve().parent / "paywalled_domains.yaml"


@functools.lru_cache
def load_paywalled_domains() -> frozenset[str]:
    """Load paywalled domains from YAML config file. Result is cached."""
    with open(_CONFIG_PATH) as f:
        data = yaml.safe_load(f)
    return frozenset(data.get("domains", []))


def is_paywalled_domain(url: str) -> bool:
    """Check if a URL belongs to a known paywalled domain.

    Handles subdomains: www.nytimes.com matches nytimes.com.
    """
    hostname = urlparse(url).hostname
    if not hostname:
        return False

    domains = load_paywalled_domains()

    # Check exact match and parent domain (strip subdomains one level at a time)
    parts = hostname.split(".")
    for i in range(len(parts)):
        candidate = ".".join(parts[i:])
        if candidate in domains:
            return True
    return False
