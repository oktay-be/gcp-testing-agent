# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import datetime as dt
import json
import os
from typing import Any

import google.auth
from google.adk.agents import Agent
from google.adk.apps.app import App
from google.adk.tools import tool
from google.cloud import functions_v2
from google.cloud import logging_v2
from google.cloud import pubsub_v1
from google.cloud import storage

_, project_id = google.auth.default()
resolved_project = os.environ.setdefault("GCP_PROJECT_ID", project_id)
os.environ.setdefault("GOOGLE_CLOUD_PROJECT", resolved_project)
os.environ.setdefault("GOOGLE_CLOUD_LOCATION", os.environ.get("VERTEX_AI_LOCATION", "global"))
os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "True")


def _get_project_id() -> str:
  project_id = os.environ.get("GCP_PROJECT_ID") or os.environ.get("GOOGLE_CLOUD_PROJECT")
  if not project_id:
    raise ValueError("GCP project ID is not configured in the environment.")
  return project_id


def _get_default_region() -> str:
  return os.environ.get("REGION") or os.environ.get("VERTEX_AI_LOCATION", "us-central1")


def _normalize_bucket_and_blob(bucket_name: str, blob_path: str | None = None) -> tuple[str, str | None]:
  normalized_bucket = bucket_name[5:] if bucket_name.startswith("gs://") else bucket_name
  if blob_path and blob_path.startswith("gs://"):
    path_without_scheme = blob_path[5:]
    bucket_part, object_part = path_without_scheme.split("/", 1)
    return bucket_part, object_part
  return normalized_bucket, blob_path


def _get_storage_client() -> storage.Client:
  return storage.Client(project=_get_project_id())


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
def list_gcs_objects(bucket_name: str, prefix: str = "", limit: int = 20) -> list[dict[str, Any]]:
  """List recent objects under a prefix."""

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


@tool
def describe_cloud_function(
  function_name: str,
  location: str | None = None,
) -> dict[str, Any]:
  """Return human-friendly metadata for a Cloud Function."""

  client = functions_v2.FunctionServiceClient()
  project_id = _get_project_id()
  resolved_location = location or _get_default_region()
  name = client.function_path(project=project_id, location=resolved_location, function=function_name)

  cloud_function = client.get_function(name=name)
  service_config = cloud_function.service_config
  build_config = cloud_function.build_config

  return {
    "name": cloud_function.name,
    "state": cloud_function.state.name if cloud_function.state else "STATE_UNSPECIFIED",
    "update_time": cloud_function.update_time.isoformat() if cloud_function.update_time else None,
    "service_account_email": service_config.service_account_email if service_config else None,
    "available_memory": service_config.available_memory if service_config else None,
    "max_instance_count": service_config.max_instance_count if service_config else None,
    "min_instance_count": service_config.min_instance_count if service_config else None,
    "ingress_settings": service_config.ingress_settings.name if service_config and service_config.ingress_settings else None,
    "build_worker_pool": build_config.worker_pool if build_config else None,
    "runtime": build_config.runtime if build_config else None,
    "environment_variables": dict(service_config.environment_variables)
    if service_config and service_config.environment_variables
    else None,
    "labels": dict(cloud_function.labels) if cloud_function.labels else None,
  }

TESTING_AGENT_INSTRUCTION = """
You are the AISports Cloud Testing Agent. GitHub's Test Organizer calls you with a
natural-language test plan after every pull request. Your job is to autonomously
validate the end-to-end Google Cloud pipeline (scraper_function → batch_builder_function
→ result_merger_function → downstream post generation) and report a definitive PASS or
FAIL with evidence.

When you receive a request:
1. Restate the asked functionality and list the acceptance criteria you must verify.
2. Build a short checklist that references relevant components (topics, Cloud Functions,
   buckets, Cloud Deploy steps, etc.).
3. Execute the plan using the registered tools. Always prefer tools instead of
   assumptions.
   • Use trigger_scraper_pipeline to publish the canonical scraper test payload.
   • Use list_gcs_objects/read_gcs_* helpers to inspect intermediate artifacts in
     news_data/, batch_processing/, batch_results_raw/, batch_results_merged/, and any
     new folders mentioned in the brief.
   • Use query_function_logs to capture logs (errors + confirmations) for each Cloud
     Function that should have executed.
   • After triggering a function, poll query_function_logs for that specific
     function until you see fresh entries; if no logs appear, check the next
     candidate function (e.g., batch builder → merger) before declaring a blocker.
   • Use describe_cloud_function to ensure new deployments are live (check update
     timestamp, service account, and region).
4. When examining merged results and post-generation outputs, enforce the newsroom
   prioritization rules: fights/derbies/scandals/transfers/press conferences take
   precedence, and football content outranks basketball when choosing highlight posts.
5. Log any gaps, tool failures, or missing artifacts as blockers and stop the run rather
   than guessing.

Reporting cadence:
- Produce a Markdown response with the sections `Test Plan`, `Execution`, `Evidence`,
  `Issues`, and `Verdict`.
- Cite every claim with either a tool result summary or a file/log name + timestamp.
- End with `VERDICT: PASSED` or `VERDICT: FAILED` on its own line. Only mark PASSED if
  every acceptance criterion is satisfied and logs show no unhandled errors.
"""

root_agent = Agent(
    name="aisports_testing_agent",
    model=os.environ.get("VERTEX_AI_MODEL", "gemini-2.5-pro"),
    description="Autonomous integration tester for the AISports news pipeline.",
    instruction=TESTING_AGENT_INSTRUCTION,
    tools=[
        trigger_scraper_pipeline,
        list_gcs_objects,
        read_gcs_object,
        read_gcs_jsonl_preview,
        query_function_logs,
        describe_cloud_function,
    ],
)

app = App(root_agent=root_agent, name="app")
