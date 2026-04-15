"""Fetch dedicated host pricing from Azure Retail Prices API.

Run this from any internet-connected PC to generate an updated
FALLBACK_PRICES table for pricing.py.

Usage:
    python fetch_pricing.py                                          # fetch all Gov regions, print to screen
    python fetch_pricing.py --regions "usgovvirginia,usgovarizona"   # specific regions only
    python fetch_pricing.py --all-regions                            # all Azure regions (Gov + commercial)
    python fetch_pricing.py --no-verify                              # skip SSL cert verification
    python fetch_pricing.py -o fallback_prices.txt                   # save to a text file
    python fetch_pricing.py --update app/pricing.py                  # replace FALLBACK_PRICES in pricing.py directly
    python fetch_pricing.py --no-verify --update app/pricing.py      # typical air-gapped workflow
"""

import argparse
import json
import requests
import sys
import urllib3

RETAIL_PRICES_URL = "https://prices.azure.com/api/retail/prices"

# Set by --no-verify flag to skip SSL certificate verification
VERIFY_SSL = True

# Azure Gov regions where dedicated hosts are commonly deployed
GOV_REGIONS = [
    "usgovvirginia",
    "usgovarizona",
    "usgovtexas",
    "usdodcentral",
    "usdodeast",
]


def fetch_prices(region=None):
    """Fetch dedicated host pricing from the Retail Prices API.

    Args:
        region: Optional region filter. If None, fetches all regions.

    Returns:
        List of pricing items from the API.
    """
    items = []

    filter_parts = [
        "serviceName eq 'Virtual Machines'",
        "contains(productName, 'Dedicated Host')",
        "priceType eq 'Consumption'",
    ]
    if region:
        filter_parts.append(f"armRegionName eq '{region}'")

    odata_filter = " and ".join(filter_parts)
    url = RETAIL_PRICES_URL
    params = {"$filter": odata_filter}

    page = 1
    while url:
        print(f"  Fetching page {page}...", end=" ", flush=True)
        response = requests.get(url, params=params, timeout=30, verify=VERIFY_SSL)
        response.raise_for_status()
        data = response.json()

        page_items = data.get("Items", [])
        items.extend(page_items)
        print(f"{len(page_items)} items")

        next_link = data.get("NextPageLink")
        if next_link:
            url = next_link
            params = {}
            page += 1
        else:
            url = None

    return items


def build_price_table(items):
    """Build a {sku_name: hourly_rate} dict from API items.

    Only includes hourly pay-as-you-go rates (not reserved/spot).
    Groups by region for display.
    """
    # Group by region -> sku -> price
    by_region = {}
    skus_global = {}

    for item in items:
        sku = item.get("armSkuName", "")
        price = item.get("unitPrice", 0.0)
        unit = item.get("unitOfMeasure", "")
        region = item.get("armRegionName", "unknown")
        meter = item.get("meterName", "")
        sku_desc = item.get("skuName", "")

        if not sku or unit != "1 Hour" or price <= 0:
            continue

        if region not in by_region:
            by_region[region] = {}

        # Keep lowest non-zero price per SKU (base pay-as-you-go)
        if sku not in by_region[region] or price < by_region[region][sku]:
            by_region[region][sku] = price

        if sku not in skus_global or price < skus_global[sku]["price"]:
            skus_global[sku] = {
                "price": price,
                "region": region,
                "meter": meter,
                "desc": sku_desc,
            }

    return by_region, skus_global


def main():
    parser = argparse.ArgumentParser(
        description="Fetch Azure Dedicated Host pricing for FALLBACK_PRICES table"
    )
    parser.add_argument(
        "--regions",
        help="Comma-separated list of regions (default: all Gov regions)",
    )
    parser.add_argument(
        "--all-regions",
        action="store_true",
        help="Fetch pricing across ALL regions (not just Gov)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON instead of Python dict",
    )
    parser.add_argument(
        "--no-verify",
        action="store_true",
        help="Skip SSL certificate verification (for corporate proxies)",
    )
    parser.add_argument(
        "-o", "--output",
        help="Save FALLBACK_PRICES to a file (e.g., -o fallback_prices.txt)",
    )
    parser.add_argument(
        "--update",
        help="Path to pricing.py — replaces FALLBACK_PRICES in-place",
    )
    args = parser.parse_args()

    if args.no_verify:
        global VERIFY_SSL
        VERIFY_SSL = False
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        print("SSL verification disabled.\n")

    if args.all_regions:
        print("Fetching dedicated host pricing for ALL regions...")
        items = fetch_prices(region=None)
    elif args.regions:
        regions = [r.strip() for r in args.regions.split(",")]
        items = []
        for region in regions:
            print(f"Fetching pricing for {region}...")
            items.extend(fetch_prices(region=region))
    else:
        items = []
        for region in GOV_REGIONS:
            print(f"Fetching pricing for {region}...")
            items.extend(fetch_prices(region=region))

    if not items:
        print("\nNo pricing data returned. Check your network connection.")
        sys.exit(1)

    by_region, skus_global = build_price_table(items)

    # Print summary by region
    print(f"\n{'='*60}")
    print(f"RESULTS: {len(skus_global)} unique SKUs across {len(by_region)} regions")
    print(f"{'='*60}\n")

    for region in sorted(by_region):
        print(f"Region: {region}")
        for sku in sorted(by_region[region]):
            print(f"  {sku}: ${by_region[region][sku]:.4f}/hr")
        print()

    # Build the FALLBACK_PRICES block
    lines = []
    if args.json:
        lines.append(json.dumps(
            {k: v["price"] for k, v in skus_global.items()},
            indent=4,
        ))
    else:
        lines.append("FALLBACK_PRICES = {")
        # Group by family for readability
        families = {}
        for sku, info in sorted(skus_global.items()):
            # Extract family prefix (e.g., "DSv3" from "DSv3-Type1")
            family = sku.split("-")[0] if "-" in sku else sku
            if family not in families:
                families[family] = []
            families[family].append((sku, info["price"]))

        first_family = True
        for family in sorted(families):
            if not first_family:
                lines.append("")
            first_family = False
            lines.append(f"    # {family} family")
            for sku, price in sorted(families[family]):
                lines.append(f'    "{sku}": {price:.4f},')

        lines.append("}")

    pricing_block = "\n".join(lines)

    # Output: update pricing.py in-place, save to file, or print to screen
    if args.update:
        _update_pricing_file(args.update, pricing_block)
    elif args.output:
        with open(args.output, "w") as f:
            f.write(pricing_block + "\n")
        print(f"\nFALLBACK_PRICES saved to: {args.output}")
    else:
        print(f"{'='*60}")
        print("COPY THE BLOCK BELOW INTO pricing.py FALLBACK_PRICES:")
        print(f"{'='*60}\n")
        print(pricing_block)

    print(f"\nTotal SKUs: {len(skus_global)}")


def _update_pricing_file(filepath, pricing_block):
    """Replace the FALLBACK_PRICES dict in pricing.py in-place."""
    import re

    with open(filepath, "r") as f:
        content = f.read()

    # Match from "FALLBACK_PRICES = {" to the closing "}" at the same indent
    pattern = r"FALLBACK_PRICES = \{[^}]*(?:\{[^}]*\}[^}]*)*\}"
    match = re.search(pattern, content)

    if not match:
        print(f"ERROR: Could not find FALLBACK_PRICES block in {filepath}")
        sys.exit(1)

    old_block = match.group(0)
    new_content = content.replace(old_block, pricing_block)

    with open(filepath, "w") as f:
        f.write(new_content)

    print(f"\nUpdated FALLBACK_PRICES in: {filepath}")
    print(f"  Replaced {old_block.count(chr(10))+1} lines with {pricing_block.count(chr(10))+1} lines")


if __name__ == "__main__":
    main()
