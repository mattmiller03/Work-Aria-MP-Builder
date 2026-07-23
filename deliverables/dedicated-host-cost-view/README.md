# Azure Dedicated Host Costs — view + dashboard

The **view** now ships in the pak at
`Azure-Native-Build/content/reports/views/content.xml` (ViewDef id
`f17928a6-0e6f-49e0-9001-12cfd508699b`, built in the Aria GUI and exported by
Matt). A normal `build-pak.sh` + reinstall installs it to dev and prod as
"Azure Dedicated Host Costs View" under Visualize > Views — a list of every
AZURE_DEDICATE_HOST with cost columns (hourly_rate, monthly_rate_estimate,
cost_month_to_date, cost_last_30_days, cost_currency, vm_size_summary,
allocatable_vm_summary).

## For manual GUI import (no rebuild)
Use the exported zip from Aria (Views > Manage > Export) —
`../Azure Dedicated Host Costs View/content.xml` is that export (single file,
no resources folder, no localizationKey — the format the GUI importer accepts).

## Dashboard (optional)
`azure-dedicated-host-costs-dashboard.json` wraps the view in a View widget
(references the view id above). Import via Dashboards > Manage > Import AFTER the
view exists.
