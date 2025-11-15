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

import os

import google.auth
from google.adk.agents import Agent
from google.adk.apps.app import App

from app.tools import (
    describe_cloud_function,
    list_gcs_objects,
    query_function_logs,
    read_gcs_jsonl_preview,
    read_gcs_object,
    trigger_scraper_pipeline,
)

_, project_id = google.auth.default()
resolved_project = os.environ.setdefault("GCP_PROJECT_ID", project_id)
os.environ.setdefault("GOOGLE_CLOUD_PROJECT", resolved_project)
os.environ.setdefault("GOOGLE_CLOUD_LOCATION", os.environ.get("VERTEX_AI_LOCATION", "global"))
os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "True")

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
