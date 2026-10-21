"""Check whether each GitHub dependent still references a Constructive package on its default branch.
Classifies: direct (in a package.json), transitive (lockfile only), absent, gone (repo 404/empty)."""
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from _common import use_data_dir as _use_data_dir, GITHUB_ORG, NPM_MAINTAINERS, OWN_ORGS, clone_dir
_use_data_dir('')
import csv, json, os, re, subprocess, hashlib, sys, concurrent.futures as cf, urllib.request
os.makedirs('cache',exist_ok=True)
def gh(path):
    fn='cache/'+hashlib.md5(path.encode()).hexdigest()+'.json'
    if os.path.exists(fn): return json.load(open(fn))
    r=subprocess.run(["gh","api",path],capture_output=True,text=True)
    j=json.loads(r.stdout) if r.returncode==0 and r.stdout.strip() else None
    json.dump(j,open(fn,'w')); return j
def raw(repo,ref,path):
    fn='cache/raw_'+hashlib.md5(f"{repo}@{ref}:{path}".encode()).hexdigest()
    if os.path.exists(fn): return open(fn,errors='ignore').read()
    try:
        with urllib.request.urlopen(f"https://raw.githubusercontent.com/{repo}/{ref}/{urllib.request.quote(path)}",timeout=60) as r: s=r.read().decode('utf8','ignore')
    except Exception: s=''
    open(fn,'w').write(s); return s
names=set()
for r in csv.DictReader(open('npm/constructive_packages.csv')): names.add(r['package'])
for r in csv.DictReader(open('constructive_repos.csv')): names.update(p for p in r['npm_packages'].split(';') if p and not p.startswith('_'))
names|={'pgsql-enums','@pyramation/pgsql-parser','@launchql/proto-cli','libpg-query','pgsql-parser','pgsql-deparser'}
alt='|'.join(sorted((re.escape(n) for n in names),key=len,reverse=True))
RX=re.compile(r'''(?:^|["'\s]|node_modules/|^\s*/)(%s)(?=["'@:\s])'''%alt,re.M)
LOCKS=('package-lock.json','pnpm-lock.yaml','yarn.lock','bun.lock','npm-shrinkwrap.json')
def check(full):
    repo=gh(f"repos/{full}")
    if not repo or 'default_branch' not in repo: return dict(repo=full,state='gone')
    real=repo['full_name']; br=repo['default_branch']
    tree=gh(f"repos/{real}/git/trees/{br}?recursive=1") or {}
    paths=[t['path'] for t in tree.get('tree',[]) if t.get('type')=='blob' and 'node_modules' not in t['path']]
    pj=sorted([p for p in paths if p.endswith('package.json') and 'fixture' not in p.lower()],key=lambda p:p.count('/'))[:40]
    lk=sorted([p for p in paths if p.split('/')[-1] in LOCKS],key=lambda p:p.count('/'))[:6]
    direct=set();trans=set()
    for p in pj:
        for m in RX.finditer(raw(real,br,p)): direct.add(m.group(1))
    for p in lk:
        for m in RX.finditer(raw(real,br,p)): trans.add(m.group(1))
    trans-=direct
    st='direct' if direct else ('transitive' if trans else 'absent')
    if not pj and not lk: st='no-js-manifest'
    return dict(repo=full,real=real,state=st,stars=repo.get('stargazers_count'),fork=repo.get('fork'),archived=repo.get('archived'),pushed_at=repo.get('pushed_at'),owner_type=repo['owner']['type'],
        direct=';'.join(sorted(direct)),transitive=';'.join(sorted(trans))[:500],manifests=len(pj),locks=';'.join(lk),truncated=tree.get('truncated',False))
rows=list(csv.DictReader(open('all_dependents_merged_raw.csv')))
todo=[r for r in rows if not r['dependent_repo'].startswith(tuple(o+'/' for o in OWN_ORGS)) and int(r['stars'])>=int(os.environ.get('MIN','0'))]
out=[]
with cf.ThreadPoolExecutor(6) as ex:
    for i,res in enumerate(ex.map(check,[r['dependent_repo'] for r in todo])):
        res['graph_stars']=todo[i]['stars']; res['graph_packages']=todo[i]['constructive_repo_package_per_github_graph']; out.append(res)
        if i%50==0: print(i,res['repo'],res['state'],file=sys.stderr,flush=True)
F=['repo','real','state','graph_stars','stars','fork','archived','pushed_at','owner_type','direct','transitive','manifests','locks','truncated','graph_packages']
with open('current_state.csv','w',newline='') as f:
    w=csv.DictWriter(f,fieldnames=F,extrasaction='ignore'); w.writeheader(); w.writerows(out)
import collections; print(collections.Counter(o['state'] for o in out))
