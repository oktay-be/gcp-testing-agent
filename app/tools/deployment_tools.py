"""Tools that expose Cloud Functions deployment metadata to the testing agent."""

from __future__ import annotations

import os
from typing import Any

from google.adk.tools import tool
from google.cloud import functions_v2


def _get_project_id() -> str:
    project_id = os.environ.get("GCP_PROJECT_ID") or os.environ.get(
        "GOOGLE_CLOUD_PROJECT"
    )
    if not project_id:
        raise ValueError("GCP project ID is not configured in the environment.")
    return project_id


def _get_default_region() -> str:
    return os.environ.get("REGION") or os.environ.get("VERTEX_AI_LOCATION", "us-central1")


@tool
def describe_cloud_function(
    function_name: str,
    location: str | None = None,
) -> dict[str, Any]:
    """Return human-friendly metadata for a Cloud Function.

    Args:
        function_name: Logical name of the function (e.g. "result-merger").
        location: Optional region override. Defaults to REGION or us-central1.
    """

    client = functions_v2.FunctionServiceClient()
    project_id = _get_project_id()
    resolved_location = location or _get_default_region()
    name = client.function_path(project=project_id, location=resolved_location, function=function_name)

    cloud_function = client.get_function(name=name)
    service_config = cloud_function.service_config
    build_config = cloud_function.build_config

    metadata: dict[str, Any] = {
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
        "environment_variables": dict(service_config.environment_variables) if service_config and service_config.environment_variables else None,
        "labels": dict(cloud_function.labels) if cloud_function.labels else None,
    }

    return metadata
