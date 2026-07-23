# Azure Dedicated Host Costs — importable view + dashboard

Lists every `AZURE_DEDICATE_HOST` with the pack's cost data as sortable columns:
monthly_rate_estimate, hourly_rate, cost_month_to_date, cost_last_30_days,
cost_currency, vm_size_summary, allocatable_vm_summary.

## Files
- `azure-dedicated-host-costs-view.zip` — **import this** via Aria Ops:
  **Visualize > Views > Manage > Import**, choose the **.zip** option.
  (Aria-export format: content.xml + resources/ properties.)
- `azure-dedicated-host-costs-view.xml` — raw ViewDef (reference only; the GUI
  importer needs the .zip, not raw XML).
- `azure-dedicated-host-costs-dashboard.json` — optional dashboard wrapping the
  view in a View widget. Import via **Dashboards > Manage > Import** AFTER the
  view exists (it references viewDefinitionId 843e2896-1561-4f5e-8334-23ca166734c6).

## Note
The same view is already committed to the pack at
`Azure-Native-Build/content/reports/views/content.xml`, so a normal
`build-pak.sh` + reinstall ships it to prod automatically — the .zip is just the
no-rebuild shortcut for testing in dev.

If a cost column imports empty, that field's `attributeKey` needs the exact
stored property key; build one column in the GUI, export, and match it.
