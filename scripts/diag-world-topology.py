#!/usr/bin/env python3
"""Diagnose Azure World subscription count + NIC->VM binding (Suite API).

Answers two things the aggregate health check can't:

  1. Why does "Azure World" show 1 subscription when 9 adapter instances
     exist? total_number_subscriptions on AZURE_WORLD is a native
     ComputedMetric = count(MicrosoftAzureAdapter Instance, depth=10). So the
     real question is topology, not the (now-removed) pushed value:
       - Is there ONE shared AZURE_WORLD object, or one per adapter instance?
       - How many adapter-instance objects is each World actually a parent of?
       - Do all 9 instances point at the SAME World id, or 9 different ones?

  2. Are NICs actually children of their VM, or only of their Resource Group?
     The health check's "parent 8/8" only proves a NIC has *some* parent (RG
     counts). This lists parent kinds so we can see the VM edge specifically.

Output is SCRUBBED by default: every real object name / id is replaced with a
stable token (same object -> same token *within a run*, so the topology stays
fully readable), but no real names leave the environment. Tokens are re-salted
each run so they can't be correlated across runs; set SCRUB_SALT=... for a
fixed salt if you need run-to-run stability.
ResourceKind keys (AZURE_VIRTUAL_MACHINE, ...) and metric values are schema /
counts, not sensitive, so they are shown as-is. Set SCRUB=0 to see real names.

Run on the Aria Ops data/UI node (the one with Suite API / analytics logs).
Usage:
    python3 diag-world-topology.py
    ARIA_HOST=https://localhost ARIA_PW=secret python3 diag-world-topology.py
    SCRUB=0 python3 diag-world-topology.py        # show real names (local only)
"""
import os, json, getpass, hashlib, urllib.request, urllib.error, ssl, collections

HOST = os.environ.get("ARIA_HOST", "https://localhost").rstrip("/")
ADAPTER = "MicrosoftAzureAdapter"
SCRUB = os.environ.get("SCRUB", "1") != "0"
CTX = ssl.create_default_context(); CTX.check_hostname = False; CTX.verify_mode = ssl.CERT_NONE


# --- Scrubbing --------------------------------------------------------------
# Deterministic pseudonymisation: a real string always maps to the same token,
# so relationships/uniqueness in the output are preserved (you can still tell
# "same World" from "different World") while the real name is never shown. The
# token is a short salted hash — stable within a run, and NOT reversible back
# to the original without the salt (which is random per run and never printed).
_SALT = os.environ.get("SCRUB_SALT", "") or os.urandom(8).hex()
_seen = {}


def scrub(value, prefix="obj"):
    """Return a stable token for `value`. Pass-through when SCRUB is off."""
    if not SCRUB or value in (None, "", "?"):
        return value
    s = str(value)
    if s not in _seen:
        h = hashlib.blake2s((_SALT + s).encode(), digest_size=3).hexdigest()
        _seen[s] = f"{prefix}-{h}"
    return _seen[s]


# Short, human-friendly prefix per ResourceKind so scrubbed tokens still hint
# at what they are (vm-ab12, nic-cd34) without revealing the name.
_PREFIX = {
    "AZURE_VIRTUAL_MACHINE": "vm",
    "AZURE_NW_INTERFACE": "nic",
    "AZURE_STORAGE_ACCOUNT": "sa",
    "AZURE_RESOURCE_GROUP": "rg",
    "AZURE_STORAGE_DISK": "disk",
    "AZURE_REGION_PER_SUB": "rps",
    "AZURE_REGION": "region",
    "AZURE_WORLD": "world",
    "MicrosoftAzureAdapter Instance": "inst",
}


def sn(r):
    """Scrub the display name of a resource dict, prefixed by its kind."""
    return scrub(name_of(r), _PREFIX.get(kind_of(r), "obj"))


def si(rid, prefix="id"):
    """Scrub an internal resource identifier (Aria UUID)."""
    return scrub(rid, prefix)


# --- Suite API --------------------------------------------------------------
def req(path, method="GET", body=None, token=None):
    url = HOST + path
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(url, data=data, method=method)
    r.add_header("Accept", "application/json")
    if body is not None:
        r.add_header("Content-Type", "application/json")
    if token:
        r.add_header("Authorization", "OpsToken " + token)
    with urllib.request.urlopen(r, context=CTX, timeout=60) as resp:
        return json.load(resp)


def get_token():
    pw = os.environ.get("ARIA_PW") or getpass.getpass("Aria admin password: ")
    return req("/suite-api/api/auth/token/acquire", "POST",
               {"username": "admin", "password": pw})["token"]


def list_kind(kind, token, page_size=1000, pages=20):
    out = []
    for p in range(pages):
        d = req(f"/suite-api/api/resources?adapterKind={ADAPTER}"
                f"&resourceKind={kind.replace(' ', '%20')}"
                f"&pageSize={page_size}&page={p}", token=token)
        rl = d.get("resourceList", [])
        out += rl
        total = (d.get("pageInfo") or {}).get("totalCount", len(out))
        if len(out) >= total or not rl:
            break
    return out


def rels(rid, rtype, token):
    d = req(f"/suite-api/api/resources/{rid}/relationships?relationshipType={rtype}",
            token=token)
    return d.get("resourceList", [])


def kind_of(r):
    return (r.get("resourceKey") or {}).get("resourceKindKey", "?")


def name_of(r):
    return (r.get("resourceKey") or {}).get("name", "?")


def status_of(r):
    return (r.get("resourceStatusStates") or [{}])[0].get("resourceStatus", "?")


def prop_of(rid, key, token):
    """Read one property value off a resource (or None)."""
    try:
        d = req(f"/suite-api/api/resources/{rid}/properties", token=token)
        for p in d.get("property", []):
            if p.get("name") == key:
                return p.get("value")
    except Exception:
        return None
    return None


def latest_stat(rid, key, token):
    try:
        d = req(f"/suite-api/api/resources/{rid}/stats/latest", token=token)
        for v in d.get("values", []):
            for s in (v.get("stat-list") or {}).get("stat", []):
                if (s.get("statKey") or {}).get("key") == key:
                    data = s.get("data") or []
                    return data[-1] if data else None
    except Exception as e:
        return f"(err {e})"
    return None


def main():
    token = get_token()
    print(f"[names are {'SCRUBBED — identical tokens mean the same object' if SCRUB else 'REAL (SCRUB=0)'}]")

    print("=" * 72)
    print("PART 1 — Azure World object(s) and their instance children")
    print("=" * 72)
    worlds = list_kind("AZURE_WORLD", token)
    print(f"AZURE_WORLD objects: {len(worlds)}   "
          f"(expect 1 shared; >1 means one World per instance = the bug)")
    for w in worlds:
        rid = w["identifier"]
        kids = rels(rid, "CHILD", token)
        inst_kids = [k for k in kids if kind_of(k) == "MicrosoftAzureAdapter Instance"]
        subs = latest_stat(rid, "summary|total_number_subscriptions", token)
        print(f"\n  World '{sn(w)}'  id={si(rid, 'world')}")
        print(f"    computed total_number_subscriptions = {subs}")
        print(f"    direct children: {len(kids)}  |  adapter-instance children: {len(inst_kids)}")
        for k, c in collections.Counter(kind_of(k) for k in kids).most_common():
            print(f"        {c:>4}  {k}")
        for ik in inst_kids:
            print(f"          instance child: {sn(ik)}")

    print("\n" + "=" * 72)
    print("PART 2 — Adapter Instances: does each point at the SAME World?")
    print("=" * 72)
    insts = list_kind("MicrosoftAzureAdapter Instance", token)
    print(f"Adapter Instance objects: {len(insts)}")
    world_parents = collections.Counter()
    for i in insts:
        ps = rels(i["identifier"], "PARENT", token)
        wps = [p for p in ps if kind_of(p) == "AZURE_WORLD"]
        for wp in wps:
            world_parents[wp["identifier"]] += 1
        tag = "World OK" if wps else "*** NO WORLD PARENT ***"
        print(f"  {sn(i):20} parent-kinds={sorted(set(kind_of(p) for p in ps))}  [{tag}]")
    print(f"\n  Distinct AZURE_WORLD ids across all instances: {len(world_parents)}")
    print("  1 distinct id  -> shared World (good); the count bug is elsewhere.")
    print("  N distinct ids -> each instance made its own World (the bug).")
    for wid, n in world_parents.items():
        print(f"      {n} instance(s) -> World {si(wid, 'world')}")

    print("\n" + "=" * 72)
    print("PART 3 — NIC parents: sample ATTACHED, DATA_RECEIVING NICs only")
    print("=" * 72)
    print("  (attached_vm resolved = the NIC's Azure API DID report a VM;")
    print("   so if parents lack AZURE_VIRTUAL_MACHINE, the edge is dropped, not absent)")
    all_nics = list_kind("AZURE_NW_INTERFACE", token)
    healthy_nics = [n for n in all_nics if status_of(n) == "DATA_RECEIVING"]
    print(f"  NICs total={len(all_nics)}  DATA_RECEIVING={len(healthy_nics)}")
    shown = 0
    for n in healthy_nics:
        rid = n["identifier"]
        attached = prop_of(rid, "attached_vm_id", token)
        if not attached:
            continue  # only look at NICs the API says are attached to a VM
        ps = rels(rid, "PARENT", token)
        kinds = sorted(set(kind_of(p) for p in ps))
        print(f"  NIC {sn(n):18} attached_vm=YES  parents={kinds}  "
              f"{'VM-OK' if 'AZURE_VIRTUAL_MACHINE' in kinds else '*** VM EDGE DROPPED ***'}")
        shown += 1
        if shown >= 10:
            break
    if shown == 0:
        print("  (no attached DATA_RECEIVING NIC found in the pages scanned — "
              "attached_vm_id property empty on all; the API ref may be missing)")

    print("\n" + "=" * 72)
    print("PART 4 — VM child kinds: sample DATA_RECEIVING VMs")
    print("=" * 72)
    vms = [v for v in list_kind("AZURE_VIRTUAL_MACHINE", token)
           if status_of(v) == "DATA_RECEIVING"][:10]
    for v in vms:
        ks = collections.Counter(kind_of(k) for k in rels(v["identifier"], "CHILD", token))
        print(f"  VM {sn(v):18} children={dict(ks)}")


if __name__ == "__main__":
    main()
