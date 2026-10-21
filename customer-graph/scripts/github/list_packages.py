import os as _os, sys as _sys
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from _common import use_data_dir as _use_data_dir, GITHUB_ORG, NPM_MAINTAINERS, OWN_ORGS, clone_dir
_use_data_dir('')
import subprocess, json, base64, csv, sys
def gh(path):
    r=subprocess.run(["gh","api",path],capture_output=True,text=True)
    return json.loads(r.stdout) if r.returncode==0 else None
# repos.tsv: name<TAB>stars<TAB>forks<TAB>archived<TAB>fork<TAB>description, e.g. from
#   gh repo list $CG_GITHUB_ORG --limit 1000 --json name,stargazerCount,forkCount,isArchived,isFork,description \
#     --jq '.[]|[.name,.stargazerCount,.forkCount,.isArchived,.isFork,.description]|@tsv' > $CG_DATA_DIR/repos.tsv
rows=[l.rstrip('\n').split('\t') for l in open('repos.tsv')]
out=[]
for name,stars,forks,arch,fork,desc in rows:
    if fork=='true': continue
    info=gh(f"repos/{GITHUB_ORG}/{name}")
    br=info['default_branch'] if info else 'main'
    tree=gh(f"repos/{GITHUB_ORG}/{name}/git/trees/{br}?recursive=1")
    pkgs=[]
    if tree:
        pjs=[t['path'] for t in tree['tree'] if t['path'].endswith('package.json') and 'node_modules' not in t['path'] and '__fixtures__' not in t['path'] and 'fixtures' not in t['path'] and t['path'].count('/')<=3]
        for p in pjs[:120]:
            c=gh(f"repos/{GITHUB_ORG}/{name}/contents/{p}?ref={br}")
            if not c: continue
            try: j=json.loads(base64.b64decode(c['content']))
            except Exception: continue
            if j.get('name') and not j.get('private'): pkgs.append(j['name'])
    out.append([name,stars,forks,arch,desc,';'.join(sorted(set(pkgs)))])
    print(name,stars,len(pkgs),file=sys.stderr)
with open('constructive_repos.csv','w',newline='') as f:
    w=csv.writer(f); w.writerow(['repo','stars','forks','archived','description','npm_packages']); w.writerows(sorted(out,key=lambda r:-int(r[1])))
