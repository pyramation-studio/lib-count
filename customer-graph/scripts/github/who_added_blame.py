"""For enriched dependents, find which package.json line declares a constructive package and use GraphQL blame to get the commit author who added it."""
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from _common import use_data_dir as _use_data_dir, GITHUB_ORG, NPM_MAINTAINERS, OWN_ORGS, clone_dir
_use_data_dir('')
import csv, json, subprocess, base64, hashlib, os, re, sys
def gh(path):
    fn='cache/'+hashlib.md5(path.encode()).hexdigest()+'.json'
    if os.path.exists(fn): return json.load(open(fn))
    r=subprocess.run(["gh","api",path],capture_output=True,text=True)
    j=json.loads(r.stdout) if r.returncode==0 and r.stdout.strip() else None
    json.dump(j,open(fn,'w')); return j
PAT=re.compile(r'"(libpg-query|pgsql-parser|pgsql-deparser|pgsql-enums|@pgsql/[\w-]+|@libpg-query/[\w-]+|plpgsql-parser|pg-proto-parser|kubernetesjs|@kubernetesjs/[\w-]+|@pgpmjs/[\w-]+|@pgpm/[\w-]+|@constructive-io/[\w-]+|@launchql/[\w-]+|inquirerer|makage|nested-obj|strfy-js|schema-typescript|find-and-require-package-json)"\s*:')
Q='''query($o:String!,$n:String!,$p:String!){repository(owner:$o,name:$n){defaultBranchRef{target{... on Commit{blame(path:$p){ranges{startingLine endingLine commit{oid committedDate messageHeadline author{name email user{login}}}}}}}}}}'''
out=[]
for r in csv.DictReader(open('enriched_raw.csv')):
    k=r['dependent_repo']
    if k.startswith(tuple(o+'/' for o in OWN_ORGS)) or not r['package_json_usage']: continue
    repo=gh(f"repos/{k}") or {}; br=repo.get('default_branch','main')
    tree=gh(f"repos/{k}/git/trees/{br}?recursive=1") or {}
    pjs=sorted([t['path'] for t in tree.get('tree',[]) if t['path'].endswith('package.json') and 'node_modules' not in t['path'] and 'fixture' not in t['path']],key=lambda p:p.count('/'))[:25]
    for p in pjs:
        c=gh(f"repos/{k}/contents/{p}?ref={br}")
        if not c or 'content' not in c: continue
        lines=base64.b64decode(c['content']).decode('utf8','ignore').split('\n')
        hits=[(i+1,m.group(1)) for i,l in enumerate(lines) for m in [PAT.search(l)] if m]
        if not hits: continue
        o,n=k.split('/')
        res=subprocess.run(["gh","api","graphql","-f",f"query={Q}","-f",f"o={o}","-f",f"n={n}","-f",f"p={p}"],capture_output=True,text=True)
        try: ranges=json.loads(res.stdout)['data']['repository']['defaultBranchRef']['target']['blame']['ranges']
        except Exception: print('fail',k,p,res.stderr[:200],file=sys.stderr); continue
        for ln,pkg in hits:
            for rg in ranges:
                if rg['startingLine']<=ln<=rg['endingLine']:
                    cm=rg['commit']; a=cm['author'] or {}
                    out.append([k,p,pkg,(a.get('user') or {}).get('login',''),a.get('name',''),cm['committedDate'][:10],cm['oid'][:10],cm['messageHeadline'][:100]])
        print(k,p,len(hits),file=sys.stderr)
with open('who_added_blame.csv','w',newline='') as f:
    w=csv.writer(f); w.writerow(['dependent_repo','package_json','package','last_touched_by_login','author_name','date','commit','message']); w.writerows(out)
print(len(out))
