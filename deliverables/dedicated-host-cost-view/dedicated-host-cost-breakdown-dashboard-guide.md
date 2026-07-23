# Dedicated Host Cost Breakdown — Visual Dashboard Build Guide

**Goal:** a leadership-friendly dashboard your boss can pull up in Aria Operations
showing dedicated-host cost visually (a cost "map," the priciest hosts, totals,
and the detail table).

**Cost attribute keys the pack collects on `AZURE_DEDICATE_HOST`:**
`monthly_rate_estimate`, `hourly_rate` (retail estimates), `cost_month_to_date`,
`cost_last_30_days` (actuals from Cost Management), `cost_currency`,
`vm_size_summary`, `allocatable_vm_summary`. These are numeric **properties**
(cost) and string properties (currency, summaries).

---

## STEP 0 — 60-second check that decides the whole approach

The visual widgets below (Heatmap, Top-N) chart best off **metrics**, but our cost
values are **properties**. Confirm which works before building everything:

1. Visualize > Dashboards > Create.
2. Drag a **Heatmap** widget on. Open its config.
3. Under **Size by** / **Color by**, try to select **Azure Dedicated Host** ->
   `monthly_rate_estimate`.
   - If `monthly_rate_estimate` appears and the tiles render -> **properties work**,
     continue with this guide as-is.
   - If the cost fields DON'T appear in the Size/Color picker -> tell me. I'll add
     the cost values as **metrics** in the pack (small collector change + rebuild),
     which makes them chartable AND trendable over time. Then this guide works
     verbatim.

---

## Widget 1 — Cost Map (Heatmap)   [the visual centerpiece]

Every dedicated host as a tile; bigger/redder = more expensive. Boss sees the
whole fleet's cost at a glance.

- Widget: **Heatmap**
- Input: adapter **MicrosoftAzureAdapter**, object type **Azure Dedicated Host**,
  select all.
- **Group by:** (optional) Resource Group or leave flat.
- **Size by:** `monthly_rate_estimate`
- **Color by:** `cost_month_to_date`  (green->red, low->high)
- Title: `Dedicated Host Cost Map`

## Widget 2 — Most Expensive Hosts (Top-N)

Ranked bar of the priciest hosts.

- Widget: **Top-N** (or **Pareto Analysis** for a bar+cumulative view)
- Object type: **Azure Dedicated Host**
- **Metric/Property:** `monthly_rate_estimate`, sort descending, show top 10
- Title: `Top 10 Hosts by Monthly Cost`

## Widget 3 — Cost Summary (Scoreboard)

Big-number tiles. Scoreboards DO read properties (your existing dedicated-host
dashboard proves it).

- Widget: **Scoreboard**
- Object type: **Azure Dedicated Host**, Self Provider **On**
- Tiles (add each as a property): `hourly_rate`, `monthly_rate_estimate`,
  `cost_month_to_date`, `cost_last_30_days`
- Title: `Cost Summary (per host)`
- Note: a single **fleet total** (sum across all hosts) needs a rollup we don't
  compute yet — say the word and I'll add per-subscription and fleet cost totals
  to the pack so you get one headline number.

## Widget 4 — Cost Detail (View)

The sortable table you already built.

- Widget: **View**
- Select the **Azure Dedicated Host Costs View** (already installed).
- Title: `Cost Detail`

---

## Layout

```
+--------------------------------------------------+
|  Widget 1: Dedicated Host Cost Map (Heatmap)     |  <- full width, tall
+---------------------------+----------------------+
|  Widget 2: Top 10 by Cost |  Widget 3: Summary   |
+---------------------------+----------------------+
|  Widget 4: Cost Detail (table, full width)       |
+--------------------------------------------------+
```

## When done

Save, then **Dashboards > Manage > Export** the dashboard and send me the export.
I'll swap it into the pack so it ships to prod alongside the cost view.

## Optional pack enhancements (I do these — just ask)
- **Cost as metrics** -> heatmap/Top-N/trend charts + cost-over-time history.
- **Fleet + per-subscription cost totals** -> one headline "$/month" number and a
  cost-by-subscription breakdown (great for leadership).
