#!/usr/bin/env python3
"""Step 1b: classify pyramation packages into Constructive vs other (Hyperweb/Cosmology etc.) and fetch last-week downloads."""
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from _common import use_data_dir as _use_data_dir, GITHUB_ORG, NPM_MAINTAINERS, OWN_ORGS, clone_dir
_use_data_dir('npm')
import json, re, csv, time, urllib.request, urllib.parse, sys
from concurrent.futures import ThreadPoolExecutor
pk=json.load(open("raw_pyramation_pkgs.json"))
CONSTR_ORGS={"constructive-io","launchql"}
KW=re.compile(r"(pg|sql|graphile|postgraph|launchql|pgpm|constructive|supabase|postgres|libpg|plpgsql)",re.I)
def family(v):
    m=re.search(r'github\.com/([^/]+)/([^/#]+)',v['repo'] or '')
    owner,repo=(m.group(1).lower(),m.group(2)) if m else ("","")
    if owner in CONSTR_ORGS: return "constructive"
    if v["name"].startswith(("@constructive-io/","@launchql/","@pgsql/","@pgpmjs/","@libpg-query/","@pgpm/")): return "constructive"
    if owner in {o.lower() for o in NPM_MAINTAINERS} and KW.search(repo+" "+v["name"]): return "constructive"
    if not owner and KW.search(v["name"]): return "constructive"
    return "other"
def get(url):
    for i in range(6):
        try:
            with urllib.request.urlopen(urllib.request.Request(url,headers={"User-Agent":"customer-finder"}),timeout=60) as r: return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code==404: return None
            time.sleep(3*(i+1))
        except Exception: time.sleep(3*(i+1))
    return None
cache={}
try: cache=json.load(open("cache_downloads.json"))
except: pass
def dl(name):
    if name in cache: return name,cache[name]
    d=get("https://api.npmjs.org/downloads/point/last-week/"+urllib.parse.quote(name,safe="@"))
    return name,(d or {}).get("downloads")
def fetch_many(names):
    unscoped=[n for n in names if not n.startswith("@") and n not in cache]
    for i in range(0,len(unscoped),100):
        chunk=unscoped[i:i+100]
        d=get("https://api.npmjs.org/downloads/point/last-week/"+",".join(chunk))
        if d:
            for k,v in d.items(): cache[k]=(v or {}).get("downloads") if isinstance(v,dict) else None
        time.sleep(0.5)
    with ThreadPoolExecutor(6) as ex:
        for n,v in ex.map(dl,[n for n in names if n not in cache]): cache[n]=v
    json.dump(cache,open("cache_downloads.json","w"))
if __name__=="__main__":
    names=list(pk)
    fetch_many(names)
    rows=[]
    for n,v in pk.items():
        rows.append({"package":n,"family":family(v),"weekly_downloads":cache.get(n),"version":v["version"],"repo":v["repo"],"maintainers":v["maintainers"],"last_publish":v["date"][:10],"npm_url":"https://www.npmjs.com/package/"+n,"description":v["description"]})
    rows.sort(key=lambda r:-(r["weekly_downloads"] or 0))
    with open("constructive_packages.csv","w",newline="") as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0])); w.writeheader(); [w.writerow(r) for r in rows if r["family"]=="constructive"]
    with open("other_pyramation_packages.csv","w",newline="") as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0])); w.writeheader(); [w.writerow(r) for r in rows if r["family"]!="constructive"]
    c=[r for r in rows if r["family"]=="constructive"]
    print(len(c),"constructive;",len(rows)-len(c),"other; total weekly constructive",sum(r["weekly_downloads"] or 0 for r in c))
    for r in c[:45]: print(r["weekly_downloads"],r["package"],r["repo"])
