"""Scrape GitHub 'Used by' dependents pages for the repos of $CG_GITHUB_ORG (default constructive-io).
Usage: python3 scrape_dependents.py repo1 repo2 ...
Writes raw/dependents_<repo>.csv : constructive_repo,package_name,package_id,dependent_type,owner,repo,full_name,stars,forks
"""
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from _common import use_data_dir as _use_data_dir, GITHUB_ORG, NPM_MAINTAINERS, OWN_ORGS, clone_dir
_use_data_dir('')
import re, sys, time, csv, os, html as H, subprocess
UA="Mozilla/5.0 (X11; Linux x86_64) customer-finder-research"
def fetch(url, tries=6):
    delay=5
    for t in range(tries):
        r=subprocess.run(["curl","-sL","-A",UA,"-w","\n%{http_code}",url],capture_output=True,text=True)
        body,_,code=r.stdout.rpartition("\n")
        if code=="200": return body
        print(f"  {code} on {url}; sleep {delay}",file=sys.stderr); time.sleep(delay); delay*=2
    return None
ROW=re.compile(r'data-test-id="dg-repo-pkg-dependent">(.*?)octicon-repo-forked.*?</svg>\s*([\d,]+)',re.S)
def parse_rows(h):
    out=[]
    for m in ROW.finditer(h):
        blk=m.group(1)
        a=re.search(r'data-hovercard-type="(user|organization)"[^>]*href="/([^"]+)"',blk)
        rp=re.search(r'data-hovercard-type="repository"[^>]*href="/([^"]+)"',blk)
        st=re.search(r'octicon-star.*?</svg>\s*([\d,]+)',blk,re.S)
        if not rp: continue
        full=rp.group(1)
        out.append(dict(full_name=full,owner=full.split('/')[0],repo=full.split('/')[1],
            owner_hover=a.group(1) if a else '',stars=int(st.group(1).replace(',','')) if st else 0,forks=int(m.group(2).replace(',',''))))
    return out
def packages(h,repo):
    pk={}
    for m in re.finditer(r'href="/%s/%s/network/dependents\?package_id=([^"]+)"[^>]*>.*?select-menu-item-text">\s*([^<\s]+)'%(re.escape(GITHUB_ORG),re.escape(repo)),h,re.S):
        pk[H.unescape(m.group(1))]=m.group(2).strip()
    return pk
def scrape(repo):
    base=f"https://github.com/{GITHUB_ORG}/{repo}/network/dependents"
    h=fetch(base); time.sleep(1.5)
    if h is None: return []
    pk=packages(h,repo)
    sel=re.search(r'Box-title.*?select-menu-button[^>]*>.*?<span[^>]*>\s*([^<]+?)\s*</span>',h,re.S)
    if not pk: pk={'':'(default)'}
    rows=[]
    for pid,pname in pk.items():
        for dtype in ("REPOSITORY","PACKAGE"):
            url=f"{base}?dependent_type={dtype}"+(f"&package_id={pid}" if pid else "")
            n=0;page=0
            while url and page<200:
                h=fetch(url); time.sleep(1.2)
                if h is None: break
                for r in parse_rows(h):
                    r.update(constructive_repo=repo,package_name=pname,package_id=pid,dependent_type=dtype); rows.append(r); n+=1
                nx=re.search(r'href="([^"]*dependents_after=[^"]+)"[^>]*>\s*Next',h)
                url=H.unescape(nx.group(1)) if nx else None
                if url and url.startswith('/'): url="https://github.com"+url
                page+=1
            print(f"{repo} {pname} {dtype}: {n}",file=sys.stderr,flush=True)
    return rows
os.makedirs('raw',exist_ok=True)
F=['constructive_repo','package_name','package_id','dependent_type','owner','repo','full_name','owner_hover','stars','forks']
for repo in sys.argv[1:]:
    rows=scrape(repo)
    with open(f'raw/dependents_{repo}.csv','w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=F); w.writeheader(); w.writerows(rows)
    print(f"== {repo}: {len(rows)} rows, {len(set(r['full_name'] for r in rows))} unique",file=sys.stderr,flush=True)
