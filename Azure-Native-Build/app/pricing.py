"""Azure Retail Prices API client for dedicated host hourly rates.

The Retail Prices API (https://prices.azure.com/api/retail/prices) is
public — no authentication required. It serves pricing for both
commercial and government cloud SKUs.

If the API is unreachable (e.g., air-gapped environments), the module
falls back to a hardcoded pricing table in FALLBACK_PRICES.

Note: This endpoint is on commercial Azure infrastructure. The Cloud
Proxy must be able to reach prices.azure.com over HTTPS.
"""

import logging
from typing import Optional

import requests

logger = logging.getLogger(__name__)

RETAIL_PRICES_URL = "https://prices.azure.com/api/retail/prices"

# ---------------------------------------------------------------------------
# Fallback pricing table — Azure Gov dedicated host hourly rates (USD)
# Source: https://azure.microsoft.com/en-us/pricing/details/virtual-machines/dedicated-host/
# Last updated: 2026-04-10
#
# Update these when SKUs or pricing change. The API will be used
# preferentially when reachable; these are the air-gapped fallback.
# ---------------------------------------------------------------------------
FALLBACK_PRICES = {
    # DCadsv6_Type1 family
    "DCadsv6_Type1": 5.8610,

    # DCasv6_Type1 family
    "DCasv6_Type1": 4.6410,

    # DCsv2 Type 1 family
    "DCsv2 Type 1": 0.8450,

    # Dadsv5_Type1 family
    "Dadsv5_Type1": 4.1330,

    # Dasv4_Type1 family
    "Dasv4_Type1": 1.0670,

    # Dasv4_Type2 family
    "Dasv4_Type2": 5.0690,

    # Dasv5_Type1 family
    "Dasv5_Type1": 3.4220,

    # Dasv6_Type1 family
    "Dasv6_Type1": 4.6430,

    # Ddsv4_Type 1 family
    "Ddsv4_Type 1": 0.9180,

    # Ddsv4_Type2 family
    "Ddsv4_Type2": 4.7230,

    # Dsv3_Type1 family
    "Dsv3_Type1": 3.3800,

    # Dsv3_Type2 family
    "Dsv3_Type2": 3.8020,

    # Dsv3_Type3 family
    "Dsv3_Type3": 4.2250,

    # Dsv3_Type4 family
    "Dsv3_Type4": 5.2810,

    # Dsv4_Type1 family
    "Dsv4_Type1": 1.0560,

    # Dsv4_Type2 family
    "Dsv4_Type2": 5.0690,

    # Dsv6_Type1 family
    "Dsv6_Type1": 10.6450,

    # ECadsv6_Type1 family
    "ECadsv6_Type1": 7.4290,

    # ECasv6_Type1 family
    "ECasv6_Type1": 6.0980,

    # Easv4_Type1 family
    "Easv4_Type1": 1.3730,

    # Easv4_Type2 family
    "Easv4_Type2": 6.6530,

    # Easv6_Type1 family
    "Easv6_Type1": 6.0980,

    # Ebdsv5 family
    "Ebdsv5-Type1": 5.8780,

    # Ebsv5 family
    "Ebsv5-Type1": 5.2450,

    # Edsv4_Type 1 family
    "Edsv4_Type 1": 1.2250,

    # Edsv4_Type2 family
    "Edsv4_Type2": 6.0190,

    # Esv3_Type1 family
    "Esv3_Type1": 4.6500,

    # Esv3_Type2 family
    "Esv3_Type2": 5.1480,

    # Esv3_Type3 family
    "Esv3_Type3": 4.2970,

    # Esv3_Type4 family
    "Esv3_Type4": 5.8220,

    # Esv4_Type1 family
    "Esv4_Type1": 1.0630,

    # Esv4_Type2 family
    "Esv4_Type2": 5.8210,

    # FXmds Type1 family
    "FXmds Type1": 0.9820,

    # Fsv2 Type3 family
    "Fsv2 Type3": 3.5280,

    # Fsv2_Type2 family
    "Fsv2_Type2": 3.1752,

    # Fsv2_Type4 family
    "Fsv2_Type4": 4.4680,

    # Lsv2_Type1 family
    "Lsv2_Type1": 6.8640,

    # Lsv3_Type1 family
    "Lsv3_Type1": 7.6560,

    # Mdmsv2MedMem _Type1 family
    "Mdmsv2MedMem _Type1": 29.3590,

    # Mdsv2MedMem_Type1 family
    "Mdsv2MedMem_Type1": 14.6740,

    # Mmsv2MedMem family
    "Mmsv2MedMem-Type1": 8.3800,

    # Ms_Type1 family
    "Ms_Type1": 14.6690,

    # Msm_Type1 family
    "Msm_Type1": 29.3630,

    # Msmv2_Type1 family
    "Msmv2_Type1": 109.0600,

    # Msv2MedMem Type1 family
    "Msv2MedMem Type1": 4.1210,

    # Msv2_Type1 family
    "Msv2_Type1": 54.5380,

    # NDamsrA100v4_Type1 family
    "NDamsrA100v4_Type1": 36.0470,

    # NDasrA100v4_Type1 family
    "NDasrA100v4_Type1": 29.9170,

    # NVasv4_Type1 family
    "NVasv4_Type1": 7.1760,

    # NVsv3_Type1 family
    "NVsv3_Type1": 5.0160,
}


def get_dedicated_host_prices(region: str) -> dict:
    """Fetch hourly rates for all Dedicated Host SKUs in a given region.

    Tries the Azure Retail Prices API first. If unreachable or returns
    no results, falls back to the hardcoded FALLBACK_PRICES table.

    Args:
        region: Azure region name (e.g., "usgov virginia", "usgovvirginia").

    Returns:
        Dict mapping SKU name (e.g., "DSv3-Type1") to hourly USD rate.
    """
    # Try the live API first
    prices = _fetch_from_api(region)

    if prices:
        logger.info("Fetched %d dedicated host SKU prices from API for '%s'",
                     len(prices), region)
        return prices

    # Fall back to hardcoded table — expand with alternate name formats
    # so lookups work regardless of whether ARM returns "DSv3-Type1",
    # "Dsv3_Type1", or "Dsv3-Type1"
    fallback = {}
    for sku, rate in FALLBACK_PRICES.items():
        fallback[sku] = rate
        fallback[sku.replace("_", "-")] = rate
        fallback[sku.replace("-", "_")] = rate

    logger.info("Using fallback pricing table (%d SKUs) — API unavailable "
                "or returned no results for '%s'", len(FALLBACK_PRICES), region)
    return fallback


def _fetch_from_api(region: str) -> dict:
    """Attempt to fetch pricing from the Azure Retail Prices API.

    Returns:
        Dict of {sku_name: hourly_rate}, or empty dict on failure.
    """
    prices = {}

    # OData filter for Dedicated Host consumption prices in the region
    # Dedicated hosts are under serviceName 'Virtual Machines' with
    # productName containing 'Dedicated Host'
    odata_filter = (
        f"serviceName eq 'Virtual Machines' "
        f"and contains(productName, 'Dedicated Host') "
        f"and armRegionName eq '{region}' "
        f"and priceType eq 'Consumption'"
    )

    url = RETAIL_PRICES_URL
    params = {"$filter": odata_filter}

    try:
        while url:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            for item in data.get("Items", []):
                sku_name = item.get("armSkuName", "")
                unit_price = item.get("unitPrice", 0.0)
                unit_of_measure = item.get("unitOfMeasure", "")

                # Only take hourly rates, skip reserved/spot
                if sku_name and unit_of_measure == "1 Hour":
                    # Normalize SKU: API returns "Dsv3_Type2",
                    # ARM returns "DSv3-Type2". Store both forms.
                    hyphen_name = sku_name.replace("_", "-")

                    # Prefer the lowest non-zero price (base pay-as-you-go)
                    for name in (sku_name, hyphen_name):
                        if name not in prices or (
                            unit_price > 0 and unit_price < prices[name]
                        ):
                            prices[name] = unit_price

            # Follow pagination
            next_link = data.get("NextPageLink")
            if next_link:
                url = next_link
                params = {}  # NextPageLink includes query params
            else:
                url = None

    except Exception as e:
        logger.warning("Retail Prices API unreachable: %s", e)

    return prices


# ---------------------------------------------------------------------------
# Fallback memory table — Dedicated Host SKU memory capacity (GiB)
# Source: Azure Compute SKU API + Microsoft Learn dedicated host SKU docs
#         https://learn.microsoft.com/azure/virtual-machines/dedicated-host
#
# Used when Azure Gov's Microsoft.Compute/skus API doesn't surface the
# `MemoryGB` capability for dedicated hosts (observed 2026-05-01 — the
# capability is present in commercial Azure but missing from Gov even
# when the SKU itself is returned). dedicated_hosts.py falls back to
# this table to compute memory_utilization_pct.
#
# **Best-effort values** — verify against your tenant's actual SKU API
# response when possible. Unknown SKUs log a WARNING from
# get_dedicated_host_memory_fallback so operators can extend this table
# as new host families are deployed. Both underscore and hyphen forms
# are accepted by the lookup function.
#
# Last reviewed: 2026-05-01
# ---------------------------------------------------------------------------
FALLBACK_DEDICATED_HOST_MEMORY_GIB = {
    # Dsv3 — General-purpose, Intel Xeon E5-2673 v4 (Broadwell)
    "Dsv3_Type1": 256.0,
    "Dsv3_Type2": 448.0,
    "Dsv3_Type3": 576.0,
    "Dsv3_Type4": 768.0,

    # Dsv4 / Dasv4 / Ddsv4 — Intel Cascade Lake / AMD EPYC Rome
    "Dsv4_Type1": 384.0,
    "Dsv4_Type2": 768.0,
    "Dasv4_Type1": 384.0,
    "Dasv4_Type2": 768.0,
    "Ddsv4_Type 1": 384.0,
    "Ddsv4_Type2": 768.0,

    # Dsv5 / Dadsv5 / Dasv5 — Intel Ice Lake / AMD EPYC Milan
    "Dadsv5_Type1": 384.0,
    "Dasv5_Type1": 384.0,

    # Esv3 — Memory-optimized
    "Esv3_Type1": 432.0,
    "Esv3_Type2": 504.0,
    "Esv3_Type3": 768.0,
    "Esv3_Type4": 1008.0,

    # Esv4 / Easv4 / Edsv4 — Memory-optimized newer gen
    "Esv4_Type1": 504.0,
    "Esv4_Type2": 1024.0,
    "Easv4_Type1": 504.0,
    "Easv4_Type2": 1024.0,
    "Edsv4_Type 1": 504.0,
    "Edsv4_Type2": 1024.0,

    # Lsv2 — Storage-optimized
    "Lsv2_Type1": 768.0,

    # Fsv2 — Compute-optimized
    "Fsv2_Type2": 288.0,
    "Fsv2_Type3": 384.0,
    "Fsv2_Type4": 504.0,

    # Ms / Msv2 / Msmv2 — High-memory
    "Ms_Type1": 3892.0,
    "Msv2_Type1": 5700.0,
    "Msmv2_Type1": 11400.0,

    # DCsv2 — Confidential compute
    "DCsv2 Type 1": 192.0,
}


def get_dedicated_host_memory_fallback(sku_name: str) -> float:
    """Look up dedicated host memory capacity from the hardcoded table.

    Used when the Azure SKU API doesn't return MemoryGB for dedicated
    hosts (Azure Gov data quirk as of 2026-05-01). Tries both underscore
    and hyphen forms of the SKU name to match whatever ARM returned.

    Args:
        sku_name: Dedicated host SKU name (e.g., "Dsv3-Type1" or "Dsv3_Type1").

    Returns:
        Memory capacity in GiB, or 0.0 if the SKU isn't in the fallback
        table. Logs a WARNING on miss so operators see which SKUs need
        to be added.
    """
    if not sku_name:
        return 0.0

    # Try direct match, then both name-format variants
    for candidate in (sku_name, sku_name.replace("-", "_"), sku_name.replace("_", "-")):
        if candidate in FALLBACK_DEDICATED_HOST_MEMORY_GIB:
            return FALLBACK_DEDICATED_HOST_MEMORY_GIB[candidate]

    logger.warning(
        "No memory fallback for dedicated host SKU %r — extend "
        "FALLBACK_DEDICATED_HOST_MEMORY_GIB in pricing.py to populate "
        "memory_utilization_pct for hosts of this type",
        sku_name,
    )
    return 0.0


def get_all_dedicated_host_prices(regions: list) -> dict:
    """Fetch dedicated host prices across multiple regions.

    Args:
        regions: List of Azure region names.

    Returns:
        Dict mapping (region, sku_name) to hourly USD rate.
    """
    all_prices = {}
    seen_regions = set()

    for region in regions:
        region_lower = region.lower()
        if region_lower in seen_regions:
            continue
        seen_regions.add(region_lower)

        region_prices = get_dedicated_host_prices(region_lower)
        for sku_name, rate in region_prices.items():
            all_prices[(region_lower, sku_name)] = rate

    return all_prices
