# Icons

Three sources, tried in order:

1. **Bundled Microsoft catalog** — official Azure / Dynamics / Entra SVGs at
   `skills/_lib/ms_icons`, matched by `$sprite` or component id, and
   **base64-embedded** into the `.drawio` so they render through the draw.io CLI
   without depending on its own shape libraries.
2. **Project `icons.json`** — a sprite → draw.io shape path map, for anything not
   in the catalog.
3. **Type fallback** — a generic shape per C4 element type.

## Using a bundled icon

```
Container(sb, "Service Bus", "Azure Service Bus", "async backbone", $sprite="AzureServiceBus")
```

List the aliases:

```bash
grep -v '^#' ~/.agents/skills/_lib/ms_icons/catalog.tsv | awk '{print $1, $4}'
```

Covers ~38 products: API Management, Service Bus, Functions, Logic Apps, Key
Vault, Event Grid, Event Hubs, Data Factory, Synapse, Cosmos DB, SQL Database,
Storage, Data Lake, AKS, Container Apps/Instances/Registry, App Service,
Front Door, Firewall, WAF, Application Gateway, Load Balancer, VNet, VPN
Gateway, Private Link, Private Endpoint, DNS, Monitor, App Insights, App
Configuration, Redis, VMs, Dynamics 365 / Dataverse, D365 F&O, Entra ID.

**Not** included: Power Automate, Microsoft Fabric. Map those via `icons.json`.

## Project icon map

`diagrams/drawio/icons.json`, picked up automatically:

```json
{
  "PowerAutomate": "img/lib/azure2/analytics/Power_Platform.svg",
  "SendGrid": "img/lib/mscae/SendGrid_Accounts.svg",
  "LogicApps": "img/lib/mscae/Logic_Apps.svg"
}
```

Paths are draw.io's built-in shape library. To find one:

```bash
strings -a "/Applications/draw.io.app/Contents/Resources/app.asar" \
  | grep -oE "img/lib/[a-z0-9_]+/[A-Za-z0-9_/-]*\.svg" | sort -u | grep -i <product>
```

## Adding to the shared catalog

Prefer this when the icon is an official Microsoft product asset:

1. Drop the SVG in `skills/_lib/ms_icons/{azure,dynamics,entra}/` with a stable
   `snake_case` name.
2. Add a row to `catalog.tsv`: `KEY<TAB>FILE<TAB>PACK<TAB>ALIASES`.
3. Reference it as `$sprite=<Alias>`.

Keep the Microsoft Terms of Use in `LICENSES/` alongside the icons.

## Troubleshooting

**Every node looks the same** — no `$sprite`, and the type fallback is being
used. Check the alias resolves:

```python
from puml_drawio import icons
icons.load_catalog()
print(icons.sprite_file("AzureServiceBus"))   # None means no match
```

**Icon missing after rendering** — an `icons.json` path pointing at a draw.io
shape that does not exist. Catalog icons are embedded and cannot fail this way,
which is why they are preferred.
