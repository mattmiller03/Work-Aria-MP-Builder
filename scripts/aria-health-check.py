#!/usr/bin/env python3
"""Azure Gov MP — post-collection health check (Suite API).

Run on an Aria Ops data/UI node (the one with analytics-*.log). Verifies,
per ResourceKind: object count, collection-status breakdown, and how many
sampled objects actually have parent/child relationships bound (the thing
the 2026-07-20 uniqueness fix was about).

Usage:
    python3 aria-health-check.py                 # prompts for admin password
    ARIA_HOST=https://localhost python3 aria-health-check.py
"""
import os, sys, json, getpass, urllib.request, urllib.error, ssl, collections

HOST   = os.environ.get("ARIA_HOST", "https://localhost").rstrip("/")
ADAPTER = "MicrosoftAzureAdapter"
SAMPLE = 8            # objects per kind to probe for relationships
CTX = ssl.create_default_context(); CTX.check_hostname=False; CTX.verify_mode=ssl.CERT_NONE

# (label, resourceKind, expect_children, expect_parent)
KINDS = [
    ("Resource Group",      "AZURE_RESOURCE_GROUP",  True,  True),
    ("Virtual Machine",     "AZURE_VIRTUAL_MACHINE", True,  True),
    ("Managed Disk",        "AZURE_STORAGE_DISK",    False, True),
    ("Network Interface",   "AZURE_NW_INTERFACE",    False, True),
    ("Virtual Network",     "AZURE_VIRTUAL_NETWORK", True,  True),
    ("Load Balancer",       "AZURE_LB",              False, True),
    ("Storage Account",     "AZURE_STORAGE_ACCOUNT", False, True),
    ("Key Vault",           "AZURE_KEY_VAULTS",      False, True),
    ("SQL Server",          "AZURE_SQL_SERVER",      True,  True),
    ("SQL Database",        "AZURE_SQL_DATABASE",    False, True),
    ("Cosmos DB",           "AZURE_DB_ACCOUNT",      False, True),
    ("Public IP",           "AZURE_PUBLIC_IPADDRESSES", False, True),
    ("Host Group",          "AZURE_COMPUTE_HOSTGROUPS", True, True),
    ("Dedicated Host",      "AZURE_DEDICATE_HOST",   True,  True),
    ("Region-Per-Sub",      "AZURE_REGION_PER_SUB",  True,  True),
    ("Adapter Instance",    "MicrosoftAzureAdapter Instance", True, True),
]

def req(path, method="GET", body=None, token=None):
    url = HOST + path
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(url, data=data, method=method)
    r.add_header("Accept", "application/json")
    if body is not None: r.add_header("Content-Type", "application/json")
    if token: r.add_header("Authorization", "OpsToken " + token)
    try:
        with urllib.request.urlopen(r, context=CTX, timeout=60) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as e:
        raise SystemExit(f"HTTP {e.code} on {path}: {e.read()[:200]}")

def get_token():
    pw = os.environ.get("ARIA_PW") or getpass.getpass("Aria admin password: ")
    d = req("/suite-api/api/auth/token/acquire", "POST",
            {"username": "admin", "password": pw})
    return d["token"]

def resources(kind, token, page_size=500, pages=6):
    out=[]
    for p in range(pages):
        d = req(f"/suite-api/api/resources?adapterKind={ADAPTER}"
                f"&resourceKind={kind.replace(' ','%20')}&pageSize={page_size}&page={p}", token=token)
        rl = d.get("resourceList", [])
        out += rl
        total = (d.get("pageInfo") or {}).get("totalCount", len(out))
        if len(out) >= total or not rl: break
    return out, total

def rel_count(rid, kind, token):
    d = req(f"/suite-api/api/resources/{rid}/relationships?relationshipType={kind}", token=token)
    return len(d.get("resourceList", []))

def status_of(r):
    return (r.get("resourceStatusStates") or [{}])[0].get("resourceStatus","?")

def main():
    token = get_token()
    print(f"\n{'KIND':20} {'count':>6} {'DATA_RECV':>9} {'NONE':>5} {'other':>6}  {'rel-cover(sampled)':<22} flags")
    print("-"*100)
    problems=[]
    for label, kind, exp_child, exp_parent in KINDS:
        try:
            rl, total = resources(kind, token)
        except SystemExit as e:
            print(f"{label:20} ERROR: {e}"); continue
        cnt = collections.Counter(status_of(r) for r in rl)
        dr = cnt.get("DATA_RECEIVING",0); none=cnt.get("NONE",0)
        other = len(rl)-dr-none
        # sample healthy objects and probe relationships
        healthy=[r for r in rl if status_of(r)=="DATA_RECEIVING"] or rl
        sample=healthy[:SAMPLE]
        childs=parents=probed=0
        for r in sample:
            rid=r["identifier"]; probed+=1
            if exp_child  and rel_count(rid,"CHILD",token)>0:  childs+=1
            if exp_parent and rel_count(rid,"PARENT",token)>0: parents+=1
        cov=[]
        if exp_child:  cov.append(f"child {childs}/{probed}")
        if exp_parent: cov.append(f"parent {parents}/{probed}")
        cover=", ".join(cov)
        flags=[]
        if total==0: flags.append("NO OBJECTS")
        if exp_child and probed and childs==0: flags.append("NO CHILD RELS")
        if exp_parent and probed and parents==0: flags.append("NO PARENT RELS")
        if total and none/ max(total,1) > 0.25: flags.append(f"{none} NONE")
        fl=" ; ".join(flags)
        if fl: problems.append(f"{label}: {fl}")
        print(f"{label:20} {total:>6} {dr:>9} {none:>5} {other:>6}  {cover:<22} {fl}")
    print("\n" + ("ALL GREEN — every kind has objects and sampled relationships bound."
                  if not problems else "REVIEW:\n  - " + "\n  - ".join(problems)))

if __name__ == "__main__":
    main()
