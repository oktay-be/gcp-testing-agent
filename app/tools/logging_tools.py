"""Cloud Logging helper tools."""

from __future__ import annotations

import datetime as dt
from typing import Any

from google.adk.tools import tool
from google.cloud import logging_v2


@tool
def query_function_logs(
    function_name: str,
    minutes: int = 60,
    severity: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Fetch recent log entries for a Cloud Function."""

    client = logging_v2.Client()
    now = dt.datetime.utcnow()
    start = now - dt.timedelta(minutes=minutes)
    filters = [
        'resource.type="cloud_function"',
        f'resource.labels.function_name="{function_name}"',
        f'timestamp>="{start.isoformat()}Z"',
    ]
    if severity:
        filters.append(f'severity>={severity.upper()}')
    log_filter = " AND ".join(filters)

    entries = client.list_entries(filter_=log_filter, page_size=limit, order_by=logging_v2.DESCENDING)
    results: list[dict[str, Any]] = []
    for entry in entries:
        results.append(
            {
                "timestamp": entry.timestamp.isoformat() if entry.timestamp else None,
                "severity": entry.severity,
                "function": function_name,
                "text": entry.payload if isinstance(entry.payload, str) else getattr(entry.payload, "message", str(entry.payload)),
            }
        )
        if len(results) >= limit:
            break
    return results
