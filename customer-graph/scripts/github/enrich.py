"""Enrich dependents with >=MIN stars via gh api. Caches JSON in cache/."""
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from _common import use_data_dir as _use_data_dir, GITHUB_ORG, NPM_MAINTAINERS, OWN_ORGS, clone_dir
_use_data_dir('')
import csv, glob, json, os, subprocess, base64, sys, re, hashlib
MIN=int(os.environ.get('MIN_STARS','10'))
os.makedirs('cache',exist_ok=True)
def gh(path):
    fn='cache/'+hashlib.md5(path.encode()).hexdigest()+'.json'
    if os.path.exists(fn): return json.load(open(fn))
    r=subprocess.run(["gh","api",path],capture_output=True,text=True)
    j=json.loads(r.stdout) if r.returncode==0 and r.stdout.strip() else None
    json.dump(j,open(fn,'w')); return j
# constructive package names
cpk=set()
for r in csv.DictReader(open('constructive_repos.csv')):
    cpk.update(p for p in r['npm_packages'].split(';') if p)
# aggregate raw
d={}
for f in glob.glob('raw/dependents_*.csv'):
    for r in csv.DictReader(open(f)):
        e=d.setdefault(r['full_name'],{'stars':int(r['stars']),'owner':r['owner'],'graph':set(),'types':set()})
        e['graph'].add(f"{r['constructive_repo']}:{r['package_name']}"); e['types'].add(r['dependent_type'])
with open('all_dependents_merged_raw.csv','w',newline='') as f:
    w=csv.writer(f); w.writerow(['dependent_repo','url','stars','owner','dependent_types','constructive_repo_package_per_github_graph'])
    for k,v in sorted(d.items(),key=lambda x:-x[1]['stars']):
        w.writerow([k,'https://github.com/'+k,v['stars'],v['owner'],';'.join(sorted(v['types'])),';'.join(sorted(v['graph']))])
out=[]
for k,v in sorted(d.items(),key=lambda x:-x[1]['stars']):
    if v['stars']<MIN: continue
    repo=gh(f"repos/{k}") or {}
    if repo.get('full_name') and repo['full_name']!=k: pass
    owner=(repo.get('owner') or {}).get('login',v['owner'])
    otype=(repo.get('owner') or {}).get('type','')
    prof=gh(f"users/{owner}") or {}
    orgs=[]
    if otype=='User':
        orgs=[o['login'] for o in (gh(f"users/{owner}/orgs") or [])]
    # package.json check
    used=set()
    br=repo.get('default_branch','main')
    tree=gh(f"repos/{k}/git/trees/{br}?recursive=1") or {}
    pjs=[t['path'] for t in tree.get('tree',[]) if t['path'].endswith('package.json') and 'node_modules' not in t['path'] and 'fixture' not in t['path']]
    pjs=sorted(pjs,key=lambda p:p.count('/'))[:25]
    for p in pjs:
        c=gh(f"repos/{k}/contents/{p}?ref={br}")
        if not c or 'content' not in c: continue
        try: j=json.loads(base64.b64decode(c['content']))
        except Exception: continue
        for sec in ('dependencies','devDependencies','peerDependencies','optionalDependencies'):
            for n,ver in (j.get(sec) or {}).items():
                if n in cpk or n in ('libpg-query','pgsql-deparser','pgsql-enums','@pgsql/types','@pgsql/enums','@launchql/proto-cli','pgsql-parser') or n.startswith(('@pgsql/','@libpg-query/','@launchql/','@pgpmjs/','@constructive-io/','@pgpm/','@kubernetesjs/')):
                    used.add(f"{n}@{ver}" + ("" if sec=='dependencies' else f" ({sec[:3]})"))
    out.append(dict(dependent_repo=k,url='https://github.com/'+k,stars=repo.get('stargazers_count',v['stars']),
        description=(repo.get('description') or '')[:200],homepage=repo.get('homepage') or '',archived=repo.get('archived',''),pushed_at=repo.get('pushed_at',''),
        constructive_graph=';'.join(sorted(v['graph'])),package_json_usage=';'.join(sorted(used)),
        owner=owner,owner_type=otype,owner_name=prof.get('name') or '',owner_company=prof.get('company') or '',owner_blog=prof.get('blog') or '',
        owner_location=prof.get('location') or '',owner_bio=(prof.get('bio') or prof.get('description') or '').replace('\n',' ')[:200],
        owner_twitter=prof.get('twitter_username') or '',owner_followers=prof.get('followers',''),user_orgs=';'.join(orgs)))
    print(k,file=sys.stderr)
F=list(out[0].keys())
with open('enriched_raw.csv','w',newline='') as f:
    w=csv.DictWriter(f,fieldnames=F); w.writeheader(); w.writerows(out)
print(len(d),'unique dependents;',len(out),'>=',MIN)
