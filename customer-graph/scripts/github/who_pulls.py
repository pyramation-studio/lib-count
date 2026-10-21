import os as _os, sys as _sys
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from _common import use_data_dir as _use_data_dir, GITHUB_ORG, NPM_MAINTAINERS, OWN_ORGS, clone_dir
# (no chdir: argv[1] is a lockfile path given by the caller)
import json,sys,re
f=sys.argv[1]; targets=('libpg-query','pgsql-parser','pgsql-deparser','@pgsql/types','@libpg-query/parser','pgsql-enums','@pgsql/quotes','@pgsql/traverse','plpgsql-parser')
s=open(f).read()
res=set()
if f.endswith('.json'):
    j=json.loads(s)
    for k,v in j.get('packages',{}).items():
        for t in targets:
            if t in (v.get('dependencies') or {}) or t in (v.get('optionalDependencies') or {}) or t in (v.get('peerDependencies') or {}): res.add(f"{k.split('node_modules/')[-1] or '(root)'} -> {t}")
else:
    # pnpm/yarn: block-based
    blocks=re.split(r'\n(?=\S)|\n  (?=\S)',s)
    for b in blocks:
        head=b.strip().split('\n')[0]
        for t in targets:
            if re.search(r"^\s+'?%s'?:"%re.escape(t),b,re.M) or re.search(r'^\s+"?%s"? '%re.escape(t),b,re.M):
                res.add(f"{head[:80]} -> {t}")
for r in sorted(res): print(r)
