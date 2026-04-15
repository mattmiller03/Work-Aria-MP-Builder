"""Reusable Azure Monitor metrics collection for all resource types.

Fetches time-series metrics from the Azure Monitor API and attaches
them to Aria Ops objects using obj.with_metric().
"""

import logging

from azure_client import AzureClient
from constants import MONITOR_METRICS

logger = logging.getLogger(__name__)


def collect_metrics_for_objects(client: AzureClient, objects_by_resource_id: dict,
                                resource_type_key: str):
    """Fetch Azure Monitor metrics for a batch of objects.

    Args:
        client: Azure REST client.
        objects_by_resource_id: Dict mapping Azure resource ID to the
            Aria Ops object (from result.object()).
        resource_type_key: Key into MONITOR_METRICS (e.g., "virtual_machines").
    """
    metric_defs = MONITOR_METRICS.get(resource_type_key, [])
    if not metric_defs:
        return

    # Group metrics by aggregation type to batch API calls
    by_aggregation = {}
    for azure_name, aria_key, aggregation in metric_defs:
        if aggregation not in by_aggregation:
            by_aggregation[aggregation] = []
        by_aggregation[aggregation].append((azure_name, aria_key))

    total = len(objects_by_resource_id)
    success = 0
    errors = 0

    for resource_id, obj in objects_by_resource_id.items():
        for aggregation, metrics in by_aggregation.items():
            azure_names = [m[0] for m in metrics]
            aria_keys = {m[0]: m[1] for m in metrics}

            try:
                values = client.get_metrics(
                    resource_id=resource_id,
                    metric_names=azure_names,
                    aggregation=aggregation,
                )

                for azure_name, value in values.items():
                    aria_key = aria_keys.get(azure_name)
                    if aria_key and value is not None:
                        obj.with_metric(aria_key, value)

                if values:
                    success += 1

            except Exception as e:
                errors += 1
                if errors <= 3:
                    logger.warning("Metrics error for %s: %s",
                                   resource_id.split("/")[-1], e)

    logger.info("Metrics for %s: %d/%d resources, %d errors",
                resource_type_key, success, total, errors)
