import os as _os, sys as _sys
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from _common import use_data_dir as _use_data_dir, GITHUB_ORG, NPM_MAINTAINERS, OWN_ORGS, clone_dir
_use_data_dir('')
import csv
from annotations import A
rows=list(csv.DictReader(open('enriched_raw.csv')))
champ={}
for r in csv.DictReader(open('champions.csv')):
    champ.setdefault(r['dependent_repo'],[]).append(f"{r['name']} (https://github.com/{r['login']}; {r['company_field'] or 'no company field'})")
F=['dependent_repo','url','stars','segment','constructive_repo_package','package_json_usage','owner','owner_type','person_name','employer','employer_source','confidence','category','website','location','champions_on_dep_line','description','notes']
out=[]
for r in rows:
    k=r['dependent_repo']
    if k.startswith(GITHUB_ORG+'/'): continue
    g=r['constructive_graph']
    pg=any(x in g for x in ('pgsql-parser:','libpg-query-node:','constructive:','pgpm','launchql','supabase-test','agentic-db','postgres-ast'))
    seg='postgres' if pg else ('kubernetes' if 'kubernetesjs:' in g else 'dev-utils (mostly Cosmos/Hyperweb ecosystem)')
    emp,src,conf,cat,notes=A.get(k,('','','','',''))
    if not emp:
        if r['owner_type']=='Organization': emp,src,conf,cat=(r['owner_name'] or r['owner'],'GitHub org profile','medium','company')
        elif r['owner_company']: emp,src,conf,cat=(r['owner_company'],'GitHub company field','medium','developer')
        else: emp,src,conf,cat=('Unknown','','low','developer')
    if k.startswith(tuple(o+'/' for o in OWN_ORGS)): cat='affiliated'
    if seg.startswith('dev-utils') and cat in('company','oss-project'): cat='ecosystem (Cosmos, transitive via Hyperweb tooling)'
    out.append(dict(dependent_repo=k,url=r['url'],stars=r['stars'],segment=seg,constructive_repo_package=g,package_json_usage=r['package_json_usage'],
        owner=r['owner'],owner_type=r['owner_type'],person_name=r['owner_name'] if r['owner_type']=='User' else '',employer=emp,employer_source=src,confidence=conf,category=cat,
        website=r['homepage'] or r['owner_blog'],location=r['owner_location'],champions_on_dep_line='; '.join(champ.get(k,[])),description=r['description'],notes=notes))
out.sort(key=lambda x:-int(x['stars']))
with open('merged_dependents.csv','w',newline='') as f:
    w=csv.DictWriter(f,fieldnames=F); w.writeheader(); w.writerows(out)
print(len(out)); import collections; print(collections.Counter(o['segment'] for o in out)); print(collections.Counter(o['category'] for o in out))
