# Diagnose APPLY_ADAPTER Install Failure via xmllint

When an Aria Ops pak install fails at step 16/20 (`APPLY_ADAPTER`) with `taskState: ERROR after 0.0 seconds` and an empty `errorMessages` array, it means Suite-API rejected `describe.xml` synchronously. The actual error lives in a backend log we usually can't find, but **`xmllint` can validate the same XML locally** against the SDK schema and tell us exactly what Aria Ops is rejecting.

Run these on the **MP Builder server** (Photon OS), in order. Copy-paste friendly.

---

## Step 1 — Confirm a .pak was built

```bash
ls -la /opt/aria/Aria-MP-Builder/Azure/build/*.pak
```

Expected: one or more `MicrosoftAzureAdapter_*.pak` or `MicrosoftAzureAdapterTest_*.pak` files. Note the path of the most recent one; use it in Step 3.

If there's no pak, build first:

```bash
cd /opt/aria/Aria-MP-Builder
bash scripts/build-pak.sh
```

---

## Step 2 — Make sure xmllint is installed

```bash
which xmllint || sudo tdnf install -y libxml2
xmllint --version 2>&1 | head -2
```

On Photon, `libxml2` package provides `xmllint`. On Ubuntu/Debian the package is `libxml2-utils`. On RHEL/Rocky/CentOS it's `libxml2`.

---

## Step 3 — Extract the pak into a scratch directory

```bash
PAK=$(ls -t /opt/aria/Aria-MP-Builder/Azure/build/*.pak | head -1)
echo "Using pak: $PAK"

rm -rf /tmp/pak-inspect
mkdir -p /tmp/pak-inspect
cd /tmp/pak-inspect

unzip -q "$PAK"
unzip -q adapter.zip

ls -1
```

You should see `adapter.zip`, `manifest.txt`, `eula.txt`, `icon.png`, and an adapter-kind subdirectory (e.g. `MicrosoftAzureAdapter/` or `MicrosoftAzureAdapterTest/`).

---

## Step 4 — Find describe.xml and the schema inside the extracted adapter

```bash
# These paths work for any adapter kind name
DESCRIBE=$(find /tmp/pak-inspect -name describe.xml -not -path '*/conf/describeSchema*' | head -1)
SCHEMA=$(find /tmp/pak-inspect -name describeSchema.xsd | head -1)
echo "describe.xml : $DESCRIBE"
echo "describeSchema.xsd: $SCHEMA"
```

Both should resolve to a real path under `/tmp/pak-inspect`. If either is empty, the pak is malformed — stop and report back.

---

## Step 5 — Run xmllint schema validation

```bash
xmllint --noout --schema "$SCHEMA" "$DESCRIBE" 2>&1 | head -80
```

### Reading the output

- **Success** — you see exactly:

  ```
  /tmp/pak-inspect/.../describe.xml validates
  ```

  If this is the case, describe.xml is structurally correct and the APPLY_ADAPTER failure is NOT a schema issue. Jump to Step 7 (structural compare).

- **Failure** — you see lines like:

  ```
  describe.xml:42: element ResourceKind: Schemas validity error : Element 'ResourceKind', attribute 'type': '9' is not a valid value of the atomic type.
  describe.xml fails to validate
  ```

  Each error points at a line/element and the specific problem. Save the output:

  ```bash
  xmllint --noout --schema "$SCHEMA" "$DESCRIBE" 2>&1 > /tmp/pak-inspect/xmllint.out
  wc -l /tmp/pak-inspect/xmllint.out
  head -100 /tmp/pak-inspect/xmllint.out
  ```

  Common classes of error and where to fix them:

  | Error pattern | Fix location |
  | ------------- | ------------ |
  | `attribute 'type': 'X' is not valid` on `<ResourceKind>` | `scripts/patch-describe-xml.py` — adjust the `type=` value we inject |
  | `attribute 'subType'` invalid | Same patch script |
  | `<PowerState>` content invalid | Patch script — order of `<PowerStateValue>` children |
  | `Missing child element` on `<ResourceKind>` | `Azure-Native-Build/app/adapter.py` `get_adapter_definition()` — the stub loop or a specific ResourceKind is missing a required child |
  | `Element 'X' is not allowed` | SDK emitted something the schema doesn't recognize — likely an SDK version mismatch; worth checking the SDK wheel in `Azure-Native-Build/app/wheels/` |
  | Duplicate key exceptions | `Azure-Native-Build/app/constants.py` `ALL_NATIVE_STUB_KINDS` vs first-class types in `adapter.py` |

---

## Step 6 — (if validation failed) Sanity-check sizes and counts

Useful context while comparing against the native pak:

```bash
grep -c "<ResourceKind "       "$DESCRIBE"     # how many kinds we emit
grep -c "<ResourceIdentifier " "$DESCRIBE"     # total identifiers
grep -c "<ResourceAttribute "  "$DESCRIBE"     # total attributes/properties
head -30 "$DESCRIBE"                            # root AdapterKind attributes
```

Note the `<AdapterKind>` root attributes — `key`, `nameKey`, `version`, `xsi:schemaLocation`. The native pak uses `version="17"` (a small integer). If ours emits `version="8.19.0"` (a dotted version string), that's potentially the issue.

---

## Step 7 — (if validation passed) Compare against the native pak

If xmllint says "validates" but the install still fails, the error is semantic (not structural). Diff against the native reference to spot what we're doing differently:

```bash
NATIVE_DESCRIBE="/opt/aria/Aria-MP-Builder/Azure-Native/MicrosoftAzureAdapter-818024067771/AzureAdapter/MicrosoftAzureAdapter/conf/describe.xml"
ls -la "$NATIVE_DESCRIBE"

# Top-of-file attributes — are root elements structured the same?
head -30 "$DESCRIBE"
echo "---"
head -30 "$NATIVE_DESCRIBE"

# Side-by-side ResourceKind counts
echo "ours:   $(grep -c '<ResourceKind ' "$DESCRIBE")"
echo "native: $(grep -c '<ResourceKind ' "$NATIVE_DESCRIBE")"

# Adapter Instance ResourceKind — where lots of registration logic happens
grep -A 5 'MicrosoftAzureAdapter Instance' "$DESCRIBE"       | head -20
echo "---"
grep -A 5 'MicrosoftAzureAdapter Instance' "$NATIVE_DESCRIBE" | head -20
```

The key fields to eyeball on `<ResourceKind key="MicrosoftAzureAdapter Instance">`:

- `type` — native has `type="7"`
- `credentialKind` — native has `credentialKind="AZURE_CLIENT_CREDENTIALS"`
- `monitoringInterval` — native has `monitoringInterval="10"`

If any of these are missing or different, the SDK we're using emits a looser shape that Aria Ops won't register as an adapter. The fix lives in `Azure-Native-Build/app/adapter.py` — we may need to patch the generated XML via `scripts/patch-describe-xml.py` to add them.

---

## Step 8 — Share what you found

If you hit validation errors, paste the first 30–50 lines of xmllint output. If validation passed, paste the three `head -30` / `grep` outputs from Step 7. Either way we can pick the fix from there.

---

## Appendix: One-shot command

If you just want the whole run in a single copy-paste:

```bash
cd /opt/aria/Aria-MP-Builder && \
PAK=$(ls -t Azure/build/*.pak 2>/dev/null | head -1) && \
[ -z "$PAK" ] && { echo "No pak built yet. Run: bash scripts/build-pak.sh"; exit 1; } ; \
which xmllint >/dev/null 2>&1 || sudo tdnf install -y libxml2 ; \
rm -rf /tmp/pak-inspect && mkdir -p /tmp/pak-inspect && cd /tmp/pak-inspect && \
unzip -q "$PAK" && unzip -q adapter.zip && \
DESCRIBE=$(find . -name describe.xml -not -path '*/conf/describeSchema*' | head -1) && \
SCHEMA=$(find . -name describeSchema.xsd | head -1) && \
echo "--- describe.xml: $DESCRIBE" && \
echo "--- schema:       $SCHEMA" && \
echo "--- validation:" && \
xmllint --noout --schema "$SCHEMA" "$DESCRIBE" 2>&1 | head -40 && \
echo "--- structure:" && \
echo "ResourceKinds: $(grep -c '<ResourceKind ' "$DESCRIBE")" && \
head -3 "$DESCRIBE"
```
