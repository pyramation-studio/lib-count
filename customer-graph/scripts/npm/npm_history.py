"""npm side: find packages that depended on a Constructive package in ANY version (ecosyste.ms latest=false + npm dependents),
then walk each packument's version history to get first/last version with the dep, and whether latest still has it."""
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from _common import use_data_dir as _use_data_dir, GITHUB_ORG, NPM_MAINTAINERS, OWN_ORGS, clone_dir
_use_data_dir('')
import csv, json, os, re, sys, time, urllib.request, urllib.parse, hashlib, concurrent.futures as cf
C='npm_hist/cache'; os.makedirs(C,exist_ok=True)
def get(url):
    fn=C+'/'+hashlib.md5(url.encode()).hexdigest()
    if os.path.exists(fn): return json.load(open(fn))
    for t in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'customer-finder'}),timeout=90) as r: j=json.loads(r.read())
            break
        except urllib.error.HTTPError as e:
            if e.code==404: j=None; break
            time.sleep(3*(t+1)); j=None
        except Exception: time.sleep(3*(t+1)); j=None
    json.dump(j,open(fn,'w')); return j
cpk=[r for r in csv.DictReader(open('npm/constructive_packages.csv'))]
names={r['package'] for r in cpk}|{'pgsql-enums','@pyramation/pgsql-parser','pg-deparser'}
own_maint=set(NPM_MAINTAINERS)
targets=[r['package'] for r in sorted(cpk,key=lambda r:-int(r['weekly_downloads'] or 0))]+['pgsql-enums','pg-deparser','@pyramation/pgsql-parser']
cands={}
def eco(t):
    res=[];page=1
    while page<20:
        d=get(f"https://packages.ecosyste.ms/api/v1/registries/npmjs.org/packages/{urllib.parse.quote(t,safe='')}/dependent_packages?latest=false&per_page=100&page={page}")
        if not d: break
        res+= [x['name'] for x in d]
        if len(d)<100: break
        page+=1
    return t,res
with cf.ThreadPoolExecutor(4) as ex:
    for t,res in ex.map(eco,targets):
        for n in res: cands.setdefault(n,set()).add(t)
for r in csv.DictReader(open('npm/dependents.csv')): cands.setdefault(r['dependent_pkg'],set()).add(r['depends_on'])
extra=os.environ.get('EXTRA')
if extra:
    for n in open(extra).read().split(): cands.setdefault(n,set()).add('(from github repo)')
print(len(cands),'candidate npm packages',file=sys.stderr)
def scan(n):
    p=get('https://registry.npmjs.org/'+urllib.parse.quote(n,safe='@'))
    if not p or 'versions' not in p: return None
    maint=[m.get('name') for m in p.get('maintainers',[])]
    if set(maint)&own_maint: return None
    tm=p.get('time',{}); vers=sorted(p['versions'],key=lambda v:tm.get(v,''))
    hist=[]
    for v in vers:
        m=p['versions'][v]; s=set()
        for sec in ('dependencies','peerDependencies','optionalDependencies','devDependencies'):
            for d,spec in (m.get(sec) or {}).items():
                if d in names: s.add(f"{d}" + ('' if sec=='dependencies' else f"({sec[:3]})"))
                elif isinstance(spec,str) and spec.startswith('npm:') and spec[4:].rsplit('@',1)[0] in names: s.add(spec[4:].rsplit('@',1)[0]+'(alias)')
        hist.append((v,tm.get(v,'')[:10],s))
    withdep=[h for h in hist if h[2]]
    if not withdep: return dict(pkg=n,status='never-declared',maint=maint)
    latest=p.get('dist-tags',{}).get('latest',vers[-1])
    lh=[h for h in hist if h[0]==latest]; still=bool(lh and lh[0][2])
    first=withdep[0]; last=withdep[-1]
    idx=hist.index(last); nxt=hist[idx+1] if idx+1<len(hist) and not still else None
    repo=(p.get('repository') or {}); repo=repo.get('url','') if isinstance(repo,dict) else str(repo)
    allp=set().union(*[h[2] for h in withdep])
    return dict(pkg=n,status='still-present' if still else 'removed',maint=maint,packages=';'.join(sorted(allp)),first_version=first[0],added=first[1],last_version_with=last[0],last_with_date=last[1],
        removed_in=nxt[0] if nxt else '',removed_date=nxt[1] if nxt else '',latest=latest,latest_date=tm.get(latest,'')[:10],n_versions=len(hist),repo=repo,description=(p.get('description') or '')[:150],homepage=p.get('homepage',''))
out=[]
with cf.ThreadPoolExecutor(6) as ex:
    for r in ex.map(scan,sorted(cands)):
        if r: r['ecosystems_targets']=';'.join(sorted(cands[r['pkg']])); out.append(r)
F=['pkg','status','packages','first_version','added','last_version_with','last_with_date','removed_in','removed_date','latest','latest_date','n_versions','maint','repo','homepage','description','ecosystems_targets']
with open('npm_hist/npm_history.csv','w',newline='') as f:
    w=csv.DictWriter(f,fieldnames=F,extrasaction='ignore'); w.writeheader()
    for r in out: r['maint']=';'.join(r.get('maint') or []); w.writerow(r)
import collections; print(collections.Counter(r['status'] for r in out))
