"""Pub/Sub helper tools for triggering pipeline runs."""

from __future__ import annotations

import json
import os
from typing import Any

from google.adk.tools import tool
from google.cloud import pubsub_v1


def _get_project_id() -> str:
    project_id = os.environ.get("GCP_PROJECT_ID") or os.environ.get(
        "GOOGLE_CLOUD_PROJECT"
    )
    if not project_id:
        raise ValueError("GCP project ID is not configured.")
    return project_id


def _default_payload(keywords: list[str] | None, urls: list[str] | None) -> dict[str, Any]:
    return {
        "keywords": keywords
        or ["fenerbahce", "galatasaray", "mourinho", "transfer", "derbi"],
        "urls": urls
        or [
            "https://www.fanatik.com.tr",
            "https://www.ntvspor.net",
            "https://www.trtspor.com.tr/haber/futbol",
        ],
        "scrape_depth": 1,
        "persist": False,
        "log_level": "INFO",
    }


@tool
def trigger_scraper_pipeline(
    topic_name: str | None = None,
    keywords: list[str] | None = None,
    urls: list[str] | None = None,
    scrape_depth: int = 1,
    persist: bool = False,
) -> str:
    """Publish a scraping request identical to trigger_test_tr.py."""

    project_id = _get_project_id()
    topic = topic_name or os.environ.get("SCRAPING_REQUESTS_TOPIC", "scraping-requests")
    publisher = pubsub_v1.PublisherClient()
    topic_path = publisher.topic_path(project_id, topic)

    payload = _default_payload(keywords, urls)
    payload["scrape_depth"] = scrape_depth
    payload["persist"] = persist

    future = publisher.publish(topic_path, json.dumps(payload).encode("utf-8"))
    message_id = future.result()
    return message_id
