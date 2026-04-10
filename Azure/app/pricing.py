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
    # Dsv3 family
    "DSv3-Type1": 4.4108,
    "DSv3-Type2": 4.4108,
    "DSv3-Type3": 3.5948,
    "DSv3-Type4": 3.5948,
    # Dsv4 family
    "DSv4-Type1": 4.4108,
    "DSv4-Type2": 4.4108,
    # Dsv5 family
    "DSv5-Type1": 4.4108,
    # Esv3 family
    "ESv3-Type1": 4.7872,
    "ESv3-Type2": 4.7872,
    "ESv3-Type3": 3.8468,
    "ESv3-Type4": 3.8468,
    # Esv4 family
    "ESv4-Type1": 4.8764,
    "ESv4-Type2": 4.8764,
    # Esv5 family
    "ESv5-Type1": 4.8764,
    # Fsv2 family
    "FSv2-Type2": 3.0454,
    "FSv2-Type3": 3.0454,
    "FSv2-Type4": 2.5304,
    # Msv2 family
    "MSv2-Type1": 28.4518,
    # Lsv2 family
    "LSv2-Type1": 5.4538,
    # Dasv5 family
    "DASv5-Type1": 3.9704,
    # Easv5 family
    "EASv5-Type1": 4.3596,
    # Lsv3 family
    "LSv3-Type1": 5.7028,
    # Ddsv5 family
    "DDSv5-Type1": 4.5432,
    # Edsv5 family
    "EDSv5-Type1": 5.0824,
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

    # Fall back to hardcoded table
    logger.info("Using fallback pricing table (%d SKUs) — API unavailable "
                "or returned no results for '%s'", len(FALLBACK_PRICES), region)
    return dict(FALLBACK_PRICES)


def _fetch_from_api(region: str) -> dict:
    """Attempt to fetch pricing from the Azure Retail Prices API.

    Returns:
        Dict of {sku_name: hourly_rate}, or empty dict on failure.
    """
    prices = {}

    # OData filter for Dedicated Host consumption prices in the region
    odata_filter = (
        f"serviceName eq 'Virtual Machines Dedicated Host' "
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
                    # Prefer the lowest non-zero price (base pay-as-you-go)
                    if sku_name not in prices or (
                        unit_price > 0 and unit_price < prices[sku_name]
                    ):
                        prices[sku_name] = unit_price

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
