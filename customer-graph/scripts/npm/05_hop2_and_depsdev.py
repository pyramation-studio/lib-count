#!/usr/bin/env python3
"""Step 4: (a) deps.dev direct/indirect dependent counts for top Constructive packages (latest version);
(b) one more hop: npm dependents of the top external dependents by downloads (bounded to TOP_N)."""
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from _common import use_data_dir as _use_data_dir, GITHUB_ORG, NPM_MAINTAINERS, OWN_ORGS, clone_dir
_use_data_dir('npm')
import json, csv, urllib.request, urllib.parse, time, sys, importlib
sys.path.insert(0,"."); d3=importlib.import_module("03_dependents") if False else None
H={"x-spiferack":"1","User-Agent":"Mozilla/5.0 customer-finder"}
def get(url,h=H):
    for i in range(5):
        try:
            with urllib.request.urlopen(urllib.request.Request(url,headers=h),timeout=60) as r: return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code==404: return None
            time.sleep(3*(i+1))
        except Exception: time.sleep(3*(i+1))
q=lambda n: urllib.parse.quote(n,safe="")
pk=list(csv.DictReader(open("constructive_packages.csv")))
depsdev=[]
for r in pk[:25]:
    n=r["package"]; v=r["version"]
    d=get(f"https://api.deps.dev/v3alpha/systems/npm/packages/{q(n)}/versions/{q(v)}:dependents",{"User-Agent":"cf"}) or {}
    depsdev.append({"package":n,"version":v,"weekly_downloads":r["weekly_downloads"],**d}); print(depsdev[-1])
with open("depsdev_counts.csv","w",newline="") as f:
    w=csv.DictWriter(f,fieldnames=["package","version","weekly_downloads","dependentCount","directDependentCount","indirectDependentCount"],extrasaction="ignore"); w.writeheader(); w.writerows(depsdev)
TOP_N=20
deps=list(csv.DictReader(open("dependents.csv")))[:TOP_N]
dl=json.load(open("cache_downloads.json"))
hop=[]
for r in deps:
    n=r["dependent_pkg"]; off=0
    while True:
        d=get(f"https://www.npmjs.com/browse/depended/{urllib.parse.quote(n,safe='@')}?offset={off}")
        if not d: break
        for p in d.get("packages",[]): hop.append({"hop2_pkg":p["name"],"depends_on":n,"via_constructive_pkg":r["depends_on"],"maintainers":";".join(p.get("maintainers",[])),"description":(p.get("description") or "")[:200].replace("\n"," "),"npm_url":"https://www.npmjs.com/package/"+p["name"]})
        if not d.get("hasNext") or off>360: break
        off+=36
    print(n, sum(1 for h in hop if h["depends_on"]==n))
importlib.import_module("02_downloads").fetch_many(list({h["hop2_pkg"] for h in hop}))
dl=json.load(open("cache_downloads.json"))
for h in hop: h["weekly_downloads"]=dl.get(h["hop2_pkg"])
hop.sort(key=lambda h:-(h["weekly_downloads"] or 0))
with open("dependents_hop2.csv","w",newline="") as f:
    w=csv.DictWriter(f,fieldnames=["hop2_pkg","depends_on","via_constructive_pkg","weekly_downloads","maintainers","npm_url","description"]); w.writeheader(); w.writerows(hop)
print(len(hop))
for h in hop[:30]: print(h["weekly_downloads"],h["hop2_pkg"],"->",h["depends_on"],h["maintainers"])
