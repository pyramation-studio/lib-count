import os as _os, sys as _sys
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from _common import use_data_dir as _use_data_dir, GITHUB_ORG, NPM_MAINTAINERS, OWN_ORGS, clone_dir
_use_data_dir('')
import csv,json,subprocess,hashlib,os
def gh(path):
    fn='cache/'+hashlib.md5(path.encode()).hexdigest()+'.json'
    if os.path.exists(fn): return json.load(open(fn))
    r=subprocess.run(["gh","api",path],capture_output=True,text=True)
    j=json.loads(r.stdout) if r.returncode==0 and r.stdout.strip() else None
    json.dump(j,open(fn,'w')); return j
seen={};rows=[]
for r in csv.DictReader(open('who_added_blame.csv')):
    l=r['last_touched_by_login']
    if not l or 'bot' in l or l in NPM_MAINTAINERS: continue
    if (r['dependent_repo'],l) in seen: continue
    seen[(r['dependent_repo'],l)]=1
    u=gh(f"users/{l}") or {}
    rows.append([r['dependent_repo'],r['package'],l,'https://github.com/'+l,u.get('name') or r['author_name'],u.get('company') or '',u.get('blog') or '',u.get('location') or '',u.get('twitter_username') or '',(u.get('bio') or '').replace('\n',' ')[:150],r['date'],r['message'][:90]])
with open('champions.csv','w',newline='') as f:
    w=csv.writer(f); w.writerow(['dependent_repo','package','login','github_url','name','company_field','blog','location','twitter','bio','last_touched_date','commit_message']); w.writerows(rows)
for x in rows: print(' | '.join(x[:10]))
