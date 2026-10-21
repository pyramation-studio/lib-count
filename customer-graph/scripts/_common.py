"""Shared helpers for the exploration scripts.

All scripts read/write relative to a data directory that is NOT in git:
  CG_DATA_DIR   (default: ./data under the current working directory)
GitHub-side scripts work in $CG_DATA_DIR, npm-side scripts in $CG_DATA_DIR/npm.
Caches go to $CG_DATA_DIR/cache (GitHub) and $CG_DATA_DIR/npm/cache* (npm).
Other knobs (all optional):
  CG_GITHUB_ORG        GitHub org whose repos/dependents are scanned (default constructive-io)
  CG_NPM_MAINTAINERS   comma-separated npm maintainers whose packages are "ours" (default pyramation)
  CG_CLONE_DIR         scratch dir for blobless git clones (default $CG_DATA_DIR/clones)
"""
import os

def data_dir(sub=""):
    root = os.path.abspath(os.environ.get("CG_DATA_DIR", os.path.join(os.getcwd(), "data")))
    d = os.path.join(root, sub) if sub else root
    os.makedirs(d, exist_ok=True)
    return d

def use_data_dir(sub=""):
    """chdir into the data dir so the scripts' relative file names land there."""
    d = data_dir(sub)
    os.chdir(d)
    return d

GITHUB_ORG = os.environ.get("CG_GITHUB_ORG", "constructive-io")
NPM_MAINTAINERS = [m.strip() for m in os.environ.get("CG_NPM_MAINTAINERS", "pyramation").split(",") if m.strip()]

# GitHub owners treated as "ours / affiliated" (excluded or flagged in outputs)
OWN_ORGS = [o.strip() for o in os.environ.get("CG_OWN_ORGS", "constructive-io,launchql,pyramation,hyperweb-io,cosmology-tech").split(",") if o.strip()]

# GitHub owners treated as "ours / affiliated" (excluded or flagged in outputs)
OWN_ORGS = [o.strip() for o in os.environ.get("CG_OWN_ORGS", "constructive-io,launchql,pyramation,hyperweb-io,cosmology-tech").split(",") if o.strip()]

def clone_dir():
    d = os.path.abspath(os.environ.get("CG_CLONE_DIR", os.path.join(data_dir(), "clones")))
    os.makedirs(d, exist_ok=True)
    return d
