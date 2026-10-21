#!/usr/bin/env python3
"""Step 3: build dependent edges (excluding Constructive's own packages), enrich each external dependent with
weekly downloads (api.npmjs.org), repo URL + maintainers (registry.npmjs.org), GitHub stars/owner (gh api),
and the owning GitHub user/org profile (company, blog, name). Employer = GitHub profile 'company' field (self-reported)."""
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from _common import use_data_dir as _use_data_dir, GITHUB_ORG, NPM_MAINTAINERS, OWN_ORGS, clone_dir
_use_data_dir('npm')
import json, csv, re, subprocess, urllib.request, urllib.parse, time, sys
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0,"."); import importlib; dlmod=importlib.import_module("02_downloads")
raw=json.load(open("raw_dependents.json"))
own={r["package"] for r in csv.DictReader(open("constructive_packages.csv"))}
allpy=set(json.load(open("raw_pyramation_pkgs.json")))
OWN_MAINT=set(NPM_MAINTAINERS)
edges={}  # dep -> {depends_on:set, sources:set, maint}
for target,rec in raw.items():
    for src in ("npm","eco"):
        for p in rec.get(src,[]):
            n=p["name"]
            if n in own or n in allpy: continue
            e=edges.setdefault(n,{"depends_on":set(),"sources":set(),"maint":set(),"desc":"","eco_repo":None})
            e["depends_on"].add(target); e["sources"].add("npmjs.com" if src=="npm" else "ecosyste.ms")
            e["maint"].update(m for m in p.get("maintainers",[]) if m)
            if p.get("description"): e["desc"]=p["description"]
            if p.get("repo"): e["eco_repo"]=p["repo"]
print("external dependents:",len(edges))
def get(url):
    for i in range(5):
        try:
            with urllib.request.urlopen(urllib.request.Request(url,headers={"User-Agent":"customer-finder","Accept":"application/vnd.npm.install-v1+json" if False else "application/json"}),timeout=60) as r: return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code==404: return None
            time.sleep(3*(i+1))
        except Exception: time.sleep(3*(i+1))
try: meta=json.load(open("cache_registry.json"))
except: meta={}
def reg(n):
    if n in meta: return
    d=get("https://registry.npmjs.org/"+urllib.parse.quote(n,safe="@"))
    if not d: meta[n]={}; return
    latest=(d.get("dist-tags") or {}).get("latest"); v=(d.get("versions") or {}).get(latest,{})
    repo=d.get("repository") or v.get("repository") or ""
    if isinstance(repo,dict): repo=repo.get("url","")
    meta[n]={"repo":repo,"homepage":d.get("homepage") or "","maintainers":[m.get("name") for m in d.get("maintainers",[])],
             "author":(d.get("author") or {}).get("name") if isinstance(d.get("author"),dict) else d.get("author"),
             "created":(d.get("time") or {}).get("created","")[:10],"modified":(d.get("time") or {}).get("modified","")[:10],
             "deps":{**(v.get("dependencies") or {}),**{k:"peer:"+x for k,x in (v.get("peerDependencies") or {}).items()}}}
with ThreadPoolExecutor(8) as ex: list(ex.map(reg,list(edges)))
json.dump(meta,open("cache_registry.json","w"))
dlmod.fetch_many(list(edges)); dl=dlmod.cache
def gh_repo(url):
    m=re.search(r'github\.com[/:]([^/]+)/([^/#?\s]+)',url or "")
    return (m.group(1),re.sub(r'\.git$','',m.group(2))) if m else None
try: ghc=json.load(open("cache_github.json"))
except: ghc={}
def gh(path):
    if path in ghc: return ghc[path]
    r=subprocess.run(["gh","api",path],capture_output=True,text=True)
    try: ghc[path]=json.loads(r.stdout) if r.returncode==0 else {"_err":r.stdout[:200]}
    except: ghc[path]={"_err":"parse"}
    return ghc[path]
rows=[]
def build(n):
    e=edges[n]; m=meta.get(n,{})
    repo=m.get("repo") or e["eco_repo"] or ""
    rp=gh_repo(repo) or gh_repo(m.get("homepage",""))
    stars=owner_login=owner_type=company=blog=pname=loc=bio=""
    if rp:
        r=gh(f"repos/{rp[0]}/{rp[1]}")
        if "_err" not in r:
            stars=r.get("stargazers_count"); owner_login=r["owner"]["login"]; owner_type=r["owner"]["type"]
        else: owner_login=rp[0]
        u=gh(f"users/{owner_login}")
        if "_err" not in u:
            owner_type=owner_type or u.get("type"); company=(u.get("company") or "").strip(); blog=u.get("blog") or ""; pname=u.get("name") or ""; loc=u.get("location") or ""; bio=(u.get("bio") or "").replace("\n"," ")[:160]
    maint=sorted(set(m.get("maintainers") or [])|e["maint"])
    if owner_type=="Organization":
        org=f"{pname or owner_login} (GitHub org {owner_login})"; person=""; employer=""
        conf="high (repo owned by GitHub org)"
    else:
        org=""; person=f"{pname} (@{owner_login})" if owner_login else (m.get("author") or "")
        employer=company; conf="medium (self-reported GitHub company field)" if company else ""
    return {"dependent_pkg":n,"depends_on":";".join(sorted(e["depends_on"])),"weekly_downloads":dl.get(n),"repo":f"https://github.com/{rp[0]}/{rp[1]}" if rp else repo,
            "stars":stars,"maintainers":";".join(maint),"org/company":org,"person":person,"employer":employer,"owner_blog":blog,"owner_location":loc,"owner_bio":bio,
            "npm_url":"https://www.npmjs.com/package/"+n,"created":m.get("created",""),"last_modified":m.get("modified",""),"description":e["desc"].replace("\n"," "),
            "source":"+".join(sorted(e["sources"]))+"; downloads: api.npmjs.org last-week; repo/maintainers: registry.npmjs.org; stars/profile: GitHub API",
            "confidence":conf}
with ThreadPoolExecutor(6) as ex: rows=list(ex.map(build,list(edges)))
json.dump(ghc,open("cache_github.json","w"))
rows.sort(key=lambda r:-(r["weekly_downloads"] or 0))
with open("dependents.csv","w",newline="") as f:
    w=csv.DictWriter(f,fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
print("wrote",len(rows))
