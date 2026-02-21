"""Slack ingress: webhook handling, signature verification, URL extraction, and notifications."""

from knowledge_hub.slack.client import get_slack_client, reset_client
from knowledge_hub.slack.notifier import (
    add_reaction,
    notify_duplicate,
    notify_error,
    notify_success,
)
from knowledge_hub.slack.router import router

__all__ = [
    "add_reaction",
    "get_slack_client",
    "notify_duplicate",
    "notify_error",
    "notify_success",
    "reset_client",
    "router",
]
