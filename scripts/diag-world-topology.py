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

Run on the Aria Ops data/UI node (the one with Suite API / analytics logs).
Usage:
    python3 diag-world-topology.py
    ARIA_HOST=https://localhost ARIA_PW=secret python3 diag-world-topology.py
"""
import os, json, getpass, urllib.request, urllib.error, ssl, collections

HOST = os.environ.get("ARIA_HOST", "https://localhost").rstrip("/")
ADAPTER = "MicrosoftAzureAdapter"
CTX = ssl.create_default_context(); CTX.check_hostname = False; CTX.verify_mode = ssl.CERT_NONE


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
        print(f"\n  World '{name_of(w)}'  id={rid}")
        print(f"    computed total_number_subscriptions = {subs}")
        print(f"    direct children: {len(kids)}  |  adapter-instance children: {len(inst_kids)}")
        for k, c in collections.Counter(kind_of(k) for k in kids).most_common():
            print(f"        {c:>4}  {k}")
        for ik in inst_kids:
            print(f"          instance child: {name_of(ik)}")

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
        print(f"  {name_of(i):32} parent-kinds={sorted(set(kind_of(p) for p in ps))}  [{tag}]")
    print(f"\n  Distinct AZURE_WORLD ids across all instances: {len(world_parents)}")
    print("  1 distinct id  -> shared World (good); the count bug is elsewhere.")
    print("  N distinct ids -> each instance made its own World (the bug).")
    for wid, n in world_parents.items():
        print(f"      {n} instance(s) -> World {wid}")

    print("\n" + "=" * 72)
    print("PART 3 — NIC parent kinds (sample 10): is the VM edge bound?")
    print("=" * 72)
    for n in list_kind("AZURE_NW_INTERFACE", token)[:10]:
        ps = rels(n["identifier"], "PARENT", token)
        kinds = sorted(set(kind_of(p) for p in ps))
        print(f"  NIC {name_of(n):30} parents={kinds}  "
              f"{'VM-OK' if 'AZURE_VIRTUAL_MACHINE' in kinds else '*** NO VM PARENT ***'}")

    print("\n" + "=" * 72)
    print("PART 4 — VM child kinds (sample 10): does the NIC show as a child?")
    print("=" * 72)
    for v in list_kind("AZURE_VIRTUAL_MACHINE", token)[:10]:
        ks = collections.Counter(kind_of(k) for k in rels(v["identifier"], "CHILD", token))
        print(f"  VM {name_of(v):30} children={dict(ks)}")


if __name__ == "__main__":
    main()
