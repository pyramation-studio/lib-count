#!/usr/bin/env python3
"""Add a 'flags' column to dependents.csv: own-ecosystem forks, republished forks of third-party repos (stars inherited from upstream)."""
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from _common import use_data_dir as _use_data_dir, GITHUB_ORG, NPM_MAINTAINERS, OWN_ORGS, clone_dir
_use_data_dir('npm')
import csv,re
rows=list(csv.DictReader(open("dependents.csv")))
OWN=re.compile(r"github\.com/("+"|".join(map(re.escape,OWN_ORGS))+r")/",re.I)
# Optional, manually curated {npm-name-prefix: reason} for known unofficial republishes of third-party projects.
# Read from $CG_DATA_DIR/npm/known_republish.json (never committed).
import json, os
KNOWN_REPUBLISH=json.load(open("known_republish.json")) if os.path.exists("known_republish.json") else {}
for r in rows:
    f=[]
    if OWN.search(r["repo"]): f.append("own-ecosystem repo (fork/republish or affiliated tooling)")
    owner=(re.search(r"github\.com/([^/]+)/",r["repo"]) or [None,""])[1].lower()
    if r["dependent_pkg"].startswith("@") :
        scope=r["dependent_pkg"][1:].split("/")[0].lower()
        if owner and scope not in owner and owner not in scope and r["org/company"] and not OWN.search(r["repo"]): f.append(f"scope @{scope} != repo owner {owner}: maybe personal fork; stars belong to upstream")
    for prefix,why in KNOWN_REPUBLISH.items():
        if r["dependent_pkg"].startswith(prefix): f.append("known republish: "+why)
    if not r["repo"]: f.append("no public repo in npm metadata")
    r["flags"]="; ".join(f)
with open("dependents.csv","w",newline="") as fh:
    w=csv.DictWriter(fh,fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
print(sum(1 for r in rows if r["flags"]))
