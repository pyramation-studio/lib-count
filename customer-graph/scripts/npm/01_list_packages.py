#!/usr/bin/env python3
"""Step 1: list all npm packages maintained by pyramation via registry search API, then fetch weekly downloads."""
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from _common import use_data_dir as _use_data_dir, GITHUB_ORG, NPM_MAINTAINERS, OWN_ORGS, clone_dir
_use_data_dir('npm')
import json, urllib.request, urllib.parse, time, csv, sys
def get(url, retries=4):
    for i in range(retries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent":"customer-finder"}), timeout=60) as r:
                return json.load(r)
        except Exception as e:
            if i==retries-1: print("ERR",url,e,file=sys.stderr); return None
            time.sleep(2*(i+1))
pkgs={}
for maint in NPM_MAINTAINERS:
    frm=0
    while True:
        d=get(f"https://registry.npmjs.org/-/v1/search?text=maintainer:{maint}&size=250&from={frm}")
        if not d or not d["objects"]: break
        for o in d["objects"]:
            p=o["package"]; pkgs[p["name"]]={"name":p["name"],"version":p.get("version"),"description":(p.get("description") or "")[:150],
              "repo":(p.get("links") or {}).get("repository",""),"maintainers":";".join(m.get("username","") for m in p.get("maintainers",[])),
              "publisher":(p.get("publisher") or {}).get("username",""),"date":p.get("date","")}
        frm+=250
        if frm>=d["total"]: break
json.dump(pkgs,open("raw_pyramation_pkgs.json","w"),indent=1)
print(len(pkgs))
