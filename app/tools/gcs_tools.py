"""GCS helper tools for the AISports testing agent."""

from __future__ import annotations

import json
import os
from typing import Any

from google.adk.tools import tool
from google.cloud import storage


def _normalize_bucket_and_blob(bucket_name: str, blob_path: str | None = None) -> tuple[str, str | None]:
    normalized_bucket = bucket_name[5:] if bucket_name.startswith("gs://") else bucket_name
    if blob_path and blob_path.startswith("gs://"):
        path_without_scheme = blob_path[5:]
        bucket_part, object_part = path_without_scheme.split("/", 1)
        return bucket_part, object_part
    return normalized_bucket, blob_path


def _get_storage_client() -> storage.Client:
    project_id = os.environ.get("GCP_PROJECT_ID") or os.environ.get("GOOGLE_CLOUD_PROJECT")
    return storage.Client(project=project_id)


@tool
def list_gcs_objects(bucket_name: str, prefix: str = "", limit: int = 20) -> list[dict[str, Any]]:
    """List recent objects under a prefix.

    Args:
        bucket_name: Target bucket (with or without gs:// prefix).
        prefix: Object prefix within the bucket.
        limit: Maximum number of entries to return.
    """

    client = _get_storage_client()
    normalized_bucket, _ = _normalize_bucket_and_blob(bucket_name)
    bucket = client.bucket(normalized_bucket)
    blobs = bucket.list_blobs(prefix=prefix)

    results: list[dict[str, Any]] = []
    for blob in blobs:
        results.append(
            {
                "name": blob.name,
                "size": blob.size,
                "updated": blob.updated.isoformat() if blob.updated else None,
                "content_type": blob.content_type,
            }
        )
        if len(results) >= limit:
            break
    return results


@tool
def read_gcs_object(bucket_name: str, object_path: str) -> str:
    """Return the raw text content of a GCS object."""

    client = _get_storage_client()
    bucket, blob_path = _normalize_bucket_and_blob(bucket_name, object_path)
    if not blob_path:
        raise ValueError("object_path must include the blob name")
    blob = client.bucket(bucket).blob(blob_path)
    return blob.download_as_text()


@tool
def read_gcs_jsonl_preview(bucket_name: str, object_path: str, max_lines: int = 10) -> list[dict[str, Any]]:
    """Return the first N JSONL rows to keep responses small."""

    raw_content = read_gcs_object(bucket_name, object_path)
    preview: list[dict[str, Any]] = []
    for index, line in enumerate(raw_content.splitlines()):
        if not line.strip():
            continue
        try:
            preview.append(json.loads(line))
        except json.JSONDecodeError:
            preview.append({"line": line})
        if index + 1 >= max_lines:
            break
    return preview
