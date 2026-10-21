"""For a GitHub repo, reconstruct when Constructive packages were present in its JS manifests.
Blobless clone (commits+trees local); file contents fetched from raw.githubusercontent.com at sampled commits;
transitions refined by bisection. Usage: python3 git_history.py owner/repo [...]  -> appends JSON lines to history.jsonl"""
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from _common import use_data_dir as _use_data_dir, GITHUB_ORG, NPM_MAINTAINERS, OWN_ORGS, clone_dir
_use_data_dir('')
import subprocess, sys, os, re, json, urllib.request, urllib.parse, hashlib, concurrent.futures as cf, csv
names=set()
for r in csv.DictReader(open('npm/constructive_packages.csv')): names.add(r['package'])
for r in csv.DictReader(open('constructive_repos.csv')): names.update(p for p in r['npm_packages'].split(';') if p and not p.startswith('_'))
names|={'pgsql-enums','@pyramation/pgsql-parser','@launchql/proto-cli'}
alt='|'.join(sorted((re.escape(n) for n in names),key=len,reverse=True))
RX=re.compile(r'''(?:^|["'\s]|node_modules/|^\s*/)(%s)(?=["'@:\s])'''%alt,re.M)
LOCKS=('package-lock.json','pnpm-lock.yaml','yarn.lock','bun.lock','npm-shrinkwrap.json')
CD=clone_dir()
RC='cache/rawsha'; os.makedirs(RC,exist_ok=True)
def sh(cmd,cwd=None,timeout=900):
    return subprocess.run(cmd,cwd=cwd,capture_output=True,text=True,timeout=timeout).stdout
def raw(repo,sha,path):
    fn=RC+'/'+hashlib.md5(f"{repo}{sha}{path}".encode()).hexdigest()
    if os.path.exists(fn): return open(fn,errors='ignore').read()
    s=''
    for t in range(3):
        try:
            with urllib.request.urlopen(f"https://raw.githubusercontent.com/{repo}/{sha}/{urllib.parse.quote(path)}",timeout=90) as r: s=r.read().decode('utf8','ignore'); break
        except urllib.error.HTTPError as e:
            if e.code==404: break
        except Exception: pass
    open(fn,'w').write(s); return s
def files_at(d,sha):
    out=sh(['git','ls-tree','-r','--name-only',sha],cwd=d)
    ps=[p for p in out.split('\n') if p and 'node_modules' not in p]
    pj=sorted([p for p in ps if p.endswith('package.json') and 'fixture' not in p.lower()],key=lambda p:p.count('/'))[:20]
    lk=sorted([p for p in ps if p.split('/')[-1] in LOCKS],key=lambda p:p.count('/'))[:4]
    return pj,lk
def state(repo,d,sha,cache):
    if sha in cache: return cache[sha]
    pj,lk=files_at(d,sha)
    with cf.ThreadPoolExecutor(8) as ex:
        texts=list(ex.map(lambda p:(p,raw(repo,sha,p)),pj+lk))
    direct=set();trans=set()
    for p,t in texts:
        for m in RX.finditer(t): (direct if p.endswith('package.json') else trans).add(m.group(1))
    cache[sha]=(frozenset(direct),frozenset(trans-direct)); return cache[sha]
def present(s): return bool(s[0] or s[1])
def history(repo,samples=48):
    d=CD+'/'+repo.replace('/','__')
    if not os.path.exists(d+'/.git'):
        sh(['git','clone','-q','--filter=blob:none','--no-checkout','--single-branch',f'https://github.com/{repo}',d],timeout=1500)
    if not os.path.exists(d+'/.git'): return dict(repo=repo,error='clone failed')
    log=sh(['git','log','--first-parent','--reverse','--format=%H|%ad|%an|%s','--date=short','--','*package.json','*package-lock.json','*pnpm-lock.yaml','*yarn.lock','*bun.lock'],cwd=d)
    commits=[l.split('|',3) for l in log.strip().split('\n') if l]
    if not commits: return dict(repo=repo,error='no manifest commits')
    n=len(commits); idxs=sorted(set([0,n-1]+[round(i*(n-1)/(samples-1)) for i in range(samples)])) if n>samples else list(range(n))
    cache={}
    st={i:state(repo,d,commits[i][0],cache) for i in idxs}
    trans=[]
    for a,b in zip(idxs,idxs[1:]):
        if present(st[a])!=present(st[b]):
            lo,hi=a,b
            while hi-lo>1:
                mid=(lo+hi)//2; s=state(repo,d,commits[mid][0],cache)
                if present(s)==present(state(repo,d,commits[lo][0],cache)): lo=mid
                else: hi=mid
            sb=state(repo,d,commits[hi][0],cache); sl=state(repo,d,commits[lo][0],cache)
            c=commits[hi]
            trans.append(dict(kind='added' if present(sb) else 'removed',date=c[1],author=c[2],sha=c[0][:10],msg=c[3][:140],
                packages=';'.join(sorted((sb[0]|sb[1]) if present(sb) else (sl[0]|sl[1]))),direct=bool(sb[0] or sl[0])))
    if present(st[idxs[0]]):
        c=commits[0]; s=st[idxs[0]]
        trans.insert(0,dict(kind='added',date=c[1],author=c[2],sha=c[0][:10],msg=c[3][:140],packages=';'.join(sorted(s[0]|s[1])),direct=bool(s[0])))
    ever=set();direct_ever=set()
    for s in cache.values(): ever|=s[0]|s[1]; direct_ever|=s[0]
    head=st[idxs[-1]]
    return dict(repo=repo,n_manifest_commits=n,sampled=len(cache),present_now=present(head),ever=sorted(ever),direct_ever=sorted(direct_ever),transitions=trans,first_commit=commits[0][1],last_commit=commits[-1][1])
if __name__=='__main__':
    for r in sys.argv[1:]:
        try: res=history(r)
        except Exception as e: res=dict(repo=r,error=str(e)[:200])
        with open('history.jsonl','a') as f: f.write(json.dumps(res)+'\n')
        print(json.dumps(res)[:800],flush=True)
