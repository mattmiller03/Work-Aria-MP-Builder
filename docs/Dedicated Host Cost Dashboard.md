# Dedicated Host Cost — view DONE, visual dashboard IN PROGRESS (paused 2026-07-23)

## DONE: cost list view (ships in pak)
Built in Aria GUI by Matt, exported, swapped into the pak (commit b88d4c6).
ViewDef `f17928a6-0e6f-49e0-9001-12cfd508699b` "Azure Dedicated Host Costs View"
in `Azure-Native-Build/content/reports/views/content.xml`. Lists every
AZURE_DEDICATE_HOST with cost columns. Installs on next build-pak.sh + reinstall.
Lesson: build Aria views/dashboards in the GUI + Export; don't hand-author the
export envelope (my localizationKey/resources guesses failed; GUI export = single
content.xml, no resources folder, plain inline <Title>).

## IN PROGRESS: visual cost-breakdown dashboard for Matt's boss ("see it visually")
Decided: **native Aria dashboard** (live in Aria), not HTML. Build guide at
`deliverables/dedicated-host-cost-view/dedicated-host-cost-breakdown-dashboard-guide.md`
(commit 3510629): Heatmap cost map + Top-N priciest + Scoreboard + View table.

### Blocker found (where we paused)
Cost values are numeric **PROPERTIES** (hourly_rate, monthly_rate_estimate,
cost_month_to_date, cost_last_30_days — declared in adapter.py ~597-617). Aria
**Heatmap/Top-N chart off METRICS**, so:
- Default heatmap Size/Color pickers show only metrics + badges — cost props absent.
- Switching heatmap to "instance" mode DOES let you pick an attribute/property,
  BUT the result rendered **all-orange, value 0** — the property didn't chart.

### DECIDED NEXT STEP (tomorrow)
1. **First, 10-sec sanity check:** open the cost VIEW — are hourly_rate /
   monthly_rate_estimate actually nonzero? If they're 0, the problem is pricing
   collection (air-gapped Retail Prices fallback), not the widget. `app/pricing.py`
   fallback table + `dedicated_hosts.py` region_prices.
2. **If costs are real but heatmap still 0 → add cost METRICS to the pack** (the
   real fix, was mid-implementation):
   - `adapter.py` get_adapter_definition, `dh` object: add `dh.define_metric(...)`
     for cost (FLAT keys, NO pipe — pipe-grouped custom groups get erased by
     patch-describe-xml.py's native substitution; `_extract_custom_flat_attrs`
     only preserves FLAT self-closing ResourceAttributes, isProperty-agnostic).
     e.g. define_metric("cost_monthly_usd","Monthly Cost (USD)"), cost_hourly_usd,
     cost_mtd_usd, cost_30day_usd. KEEP the existing properties (table view uses them).
   - `collectors/dedicated_hosts.py`: alongside the `safe_property` cost calls
     (lines 631-633 hourly/monthly, 649-654 MTD/30d), add `host_obj.with_metric(
     "cost_monthly_usd", round(hourly_rate*730,2))` etc. (with_metric exists;
     regions.py step 6 uses inst_obj.with_metric).
   - Rebuild+reinstall -> cost metrics appear in Heatmap/Top-N pickers (metric
     mode) + enable cost trend-over-time (bonus for leadership).
3. Then build the dashboard in GUI (heatmap size/color by cost_monthly_usd, Top-N
   by it), Export, and package into the pak like the view.
4. Optional bigger add: fleet + per-subscription cost TOTALS (headline $/month).
   Per-instance isolation means per-sub totals are clean (each collect sums its
   own hosts onto its subscription/instance obj); a global World total has the
   same cross-instance limits as the browsable-World work.

## Overall pack status
Known-good baseline, 6 subs healthy, DLA-DADE fixed, Logs tab working (integration),
cost view shipping. Browsable-World = documented native-only gap.