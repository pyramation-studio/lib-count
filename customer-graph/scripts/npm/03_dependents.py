#!/usr/bin/env python3
"""Step 2: direct dependents of each Constructive package.
Primary source: npmjs.com website JSON (header x-spiferack:1) -> /package/<p> (dependentsCount) and /browse/depended/<p>?offset=N (36/page).
Secondary: ecosyste.ms dependent_packages (union, marks source)."""
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from _common import use_data_dir as _use_data_dir, GITHUB_ORG, NPM_MAINTAINERS, OWN_ORGS, clone_dir
_use_data_dir('npm')
import json, csv, time, urllib.request, urllib.parse, sys
from concurrent.futures import ThreadPoolExecutor
H={"x-spiferack":"1","User-Agent":"Mozilla/5.0 customer-finder"}
def get(url,headers=H):
    for i in range(6):
        try:
            with urllib.request.urlopen(urllib.request.Request(url,headers=headers),timeout=60) as r: return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code==404: return None
            time.sleep(4*(i+1))
        except Exception: time.sleep(4*(i+1))
    print("FAIL",url,file=sys.stderr); return None
q=lambda n: urllib.parse.quote(n,safe="@")
pk=list(csv.DictReader(open("constructive_packages.csv")))
names=[r["package"] for r in pk]
try: out=json.load(open("raw_dependents.json"))
except: out={}
def count(n):
    d=get("https://www.npmjs.com/package/"+q(n))
    try: return n,int(str(d["dependents"]["dependentsCount"]).replace(",",""))
    except: return n,None
def npm_deps(n):
    res=[];off=0
    while True:
        d=get(f"https://www.npmjs.com/browse/depended/{q(n)}?offset={off}")
        if not d: break
        for p in d.get("packages",[]): res.append({"name":p["name"],"maintainers":p.get("maintainers",[]),"description":(p.get("description") or "")[:200],"last_publish":(p.get("date") or {}).get("ts")})
        if not d.get("hasNext"): break
        off+=36; time.sleep(0.3)
    return res
def eco_deps(n):
    res=[];page=1
    while True:
        d=get(f"https://packages.ecosyste.ms/api/v1/registries/npmjs.org/packages/{q(n)}/dependent_packages?per_page=100&page={page}",{"User-Agent":"customer-finder"})
        if not d: break
        for p in d: res.append({"name":p["name"],"repo":p.get("repository_url"),"maintainers":[m.get("login") for m in p.get("maintainers") or []],"owner":((p.get("repo_metadata") or {}).get("owner_record") or {}).get("name"),"stars":(p.get("repo_metadata") or {}).get("stargazers_count")})
        if len(d)<100: break
        page+=1
    return res
def work(n):
    if n in out: return n,out[n]
    _,c=count(n)
    rec={"npm_count":c,"npm":npm_deps(n) if c else [],"eco":eco_deps(n)}
    return n,rec
with ThreadPoolExecutor(5) as ex:
    for i,(n,rec) in enumerate(ex.map(work,names)):
        out[n]=rec
        if i%50==0: json.dump(out,open("raw_dependents.json","w")); print(i,n,rec["npm_count"],len(rec["npm"]),len(rec["eco"]),flush=True)
json.dump(out,open("raw_dependents.json","w"))
print("done")
