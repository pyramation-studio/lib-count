"""Combine GitHub git-history transitions (history.jsonl) and npm packument history (npm_hist/npm_history.csv) into past_users.csv"""
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from _common import use_data_dir as _use_data_dir, GITHUB_ORG, NPM_MAINTAINERS, OWN_ORGS, clone_dir
_use_data_dir('')
import csv, json, subprocess, hashlib, os
def gh(path):
    fn='cache/'+hashlib.md5(path.encode()).hexdigest()+'.json'
    if os.path.exists(fn): return json.load(open(fn))
    r=subprocess.run(["gh","api",path],capture_output=True,text=True)
    j=json.loads(r.stdout) if r.returncode==0 and r.stdout.strip() else None
    json.dump(j,open(fn,'w')); return j
def who(repo,sha,name):
    c=gh(f"repos/{repo}/commits/{sha}") or {}
    login=((c.get('author') or {}).get('login')) or ''
    u=gh(f"users/{login}") if login and '[bot]' not in login else {}
    u=u or {}
    return login, (u.get('name') or name), (u.get('company') or '').strip()
cs={r['real'] or r['repo']:r for r in csv.DictReader(open('current_state.csv'))}
merged={r['dependent_repo']:r for r in csv.DictReader(open('merged_dependents.csv'))}
from annotations import NOISE  # manual {repo: reason} noise list; empty template in git
rows=[]
for l in open('history.jsonl'):
    d=json.loads(l); repo=d['repo']
    if 'error' in d or not d.get('transitions'): continue
    if d.get('present_now'): continue
    adds=[t for t in d['transitions'] if t['kind']=='added']; rems=[t for t in d['transitions'] if t['kind']=='removed']
    a=adds[0]; r=rems[-1]
    al,an,ac=who(repo,a['sha'],a['author']); rl,rn,rc=who(repo,r['sha'],r['author'])
    st=cs.get(repo,{}); m=merged.get(repo,{})
    pk=sorted(set(';'.join(t['packages'] for t in d['transitions']).split(';'))-{''})
    seg='dev-utils/Cosmos' if all(p in('inquirerer','nested-obj','makage','strfy-js') for p in pk) else 'postgres'
    rows.append(dict(source='github-git-history',name=repo,url='https://github.com/'+repo,stars=st.get('stars',''),owner_type=st.get('owner_type',''),segment=seg,
        packages=';'.join(pk),how=('direct' if d['direct_ever'] else 'transitive (lockfile only)'),
        added_date=a['date'],added_by=f"{an} (https://github.com/{al})" if al else an,added_by_company=ac,added_commit=f"https://github.com/{repo}/commit/{a['sha']}",added_msg=a['msg'],
        removed_date=r['date'],removed_by=f"{rn} (https://github.com/{rl})" if rl else rn,removed_by_company=rc,removed_commit=f"https://github.com/{repo}/commit/{r['sha']}",removed_msg=r['msg'],
        episodes=len(adds),company=m.get('employer','') or (st.get('owner_type')=='Organization' and repo.split('/')[0]) or '',noise=NOISE.get(repo,''),notes=''))
for r in csv.DictReader(open('npm_hist/npm_history.csv')):
    if r['status']!='removed': continue
    rows.append(dict(source='npm-registry-versions',name=r['pkg'],url='https://www.npmjs.com/package/'+r['pkg'],stars='',owner_type='',segment='postgres',packages=r['packages'],how='declared in published versions',
        added_date=r['added'],added_by='npm maintainers: '+r['maint'],added_by_company='',added_commit=f"v{r['first_version']}",added_msg='',
        removed_date=r['removed_date'],removed_by='',removed_by_company='',removed_commit=f"first version without: v{r['removed_in']} (latest v{r['latest']})",removed_msg='',
        episodes=1,company='',noise='',notes=f"repo {r['repo']}; {r['description']}"))
from annotations import NOTES  # manual {repo_or_pkg: note}; empty template in git
for r in rows: r['notes']=(NOTES.get(r['name'],'')+(' '+r['notes'] if r['notes'] else '')).strip()
rows.sort(key=lambda r:(r['noise']!='', r['segment']!='postgres', -int(r['stars'] or 0)))
F=list(rows[0].keys())
with open('past_users.csv','w',newline='') as f:
    w=csv.DictWriter(f,fieldnames=F); w.writeheader(); w.writerows(rows)
print(len(rows))
for r in rows[:45]: print(r['name'],r['stars'],r['segment'],r['packages'][:40],r['added_date'],r['added_by'],'|',r['removed_date'],r['removed_by'],r['removed_by_company'],'|',r['removed_msg'][:60],r['noise'])
