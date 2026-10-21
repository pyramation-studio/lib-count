"""TEMPLATE for manual research annotations. Keep real entries OUT of git.

Copy this file to $CG_DATA_DIR/annotations_local.py (gitignored) and fill it in; this
module will load it automatically if present. In the pgpm version these become rows in
graph_people.annotation / graph_people.employment_claim, always with a source + confidence.
"""
import os, importlib.util

# dependent repo (owner/name) -> (employer_or_org, employer_source, confidence, category, notes)
#   confidence: high | medium | low | n/a
#   category:   company | oss-project | developer | affiliated | noise
A = {
    # 'example-org/example-repo': ('Example Inc.', 'GitHub org profile + example.com', 'high', 'company', 'uses pgsql-parser in packages/core'),
}

# repo -> reason it should be excluded/flagged as noise (fixtures, forks, own repos, placeholders)
NOISE = {
    # 'someone/fork-of-something': 'fork of upstream/something',
}

# repo or npm package -> free-text note explaining an add/remove transition
NOTES = {
    # 'example-org/example-repo': 'replaced libpg-query with an in-house parser (commit msg)',
}

_local = os.path.join(os.environ.get("CG_DATA_DIR", os.path.join(os.getcwd(), "data")), "annotations_local.py")
if os.path.exists(_local):
    _spec = importlib.util.spec_from_file_location("annotations_local", _local)
    _m = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(_m)
    A.update(getattr(_m, "A", {})); NOISE.update(getattr(_m, "NOISE", {})); NOTES.update(getattr(_m, "NOTES", {}))
