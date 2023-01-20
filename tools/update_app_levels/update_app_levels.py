import time
import toml
import requests
import tempfile
import os
import sys
import json
from collections import OrderedDict

token = open(os.path.dirname(__file__) + "/../../.github_token").read().strip()

tmpdir = tempfile.mkdtemp(prefix="update_app_levels_")
os.system(f"git clone 'https://oauth2:{token}@github.com/yunohost/apps' {tmpdir}")
os.system(f"git -C {tmpdir} checkout -b update_app_levels")

# Load the app catalog and filter out the non-working ones
catalog = toml.load(open(f"{tmpdir}/apps.toml"))

# Fetch results from the CI
CI_RESULTS_URL = "https://ci-apps.yunohost.org/ci/logs/list_level_stable_amd64.json"
ci_results = requests.get(CI_RESULTS_URL).json()

comment = {
    "major_regressions": [],
    "minor_regressions": [],
    "improvements": [],
    "outdated": [],
    "missing": [],
}

for app, infos in catalog.items():

    if infos.get("state") != "working":
        continue

    if app not in ci_results:
        comment["missing"].append(app)
        continue

    # 3600 * 24 * 60 = ~2 months
    if (int(time.time()) - ci_results[app].get("timestamp", 0)) > 3600 * 24 * 60:
        comment["outdated"].append(app)
        continue

    ci_level = ci_results[app]["level"]
    current_level = infos.get("level")

    if ci_level == current_level:
        continue
    elif current_level is None or ci_level > current_level:
        comment["improvements"].append((app, current_level, ci_level))
    elif ci_level < current_level:
        if ci_level <= 4 and current_level > 4:
            comment["major_regressions"].append((app, current_level, ci_level))
        else:
            comment["minor_regressions"].append((app, current_level, ci_level))

    infos["level"] = ci_level

# Also re-sort the catalog keys / subkeys
for app, infos in catalog.items():
    catalog[app] = OrderedDict(sorted(infos.items()))
catalog = OrderedDict(sorted(catalog.items()))

updated_catalog = toml.dumps(catalog)
updated_catalog = updated_catalog.replace(",]", " ]")
open(f"{tmpdir}/apps.toml", "w").write(updated_catalog)

os.system(f"git -C {tmpdir} commit apps.toml -m 'Update app levels according to CI results'")
os.system(f"git -C {tmpdir} push origin update_app_levels --force")
os.system(f"rm -rf {tmpdir}")

PR_body = ""
if comment["major_regressions"]:
    PR_body += "\n### Major regressions\n\n"
    for app, current_level, new_level in comment['major_regressions']:
        PR_body += f"- [ ] {app} | {current_level} -> {new_level} | https://ci-apps.yunohost.org/ci/apps/{app}/latestjob\n"
if comment["minor_regressions"]:
    PR_body += "\n### Minor regressions\n\n"
    for app, current_level, new_level in comment['minor_regressions']:
        PR_body += f"- [ ] {app} | {current_level} -> {new_level} | https://ci-apps.yunohost.org/ci/apps/{app}/latestjob\n"
if comment["improvements"]:
    PR_body += "\n### Improvements\n\n"
    for app, current_level, new_level in comment['improvements']:
        PR_body += f"- {app} | {current_level} -> {new_level} | https://ci-apps.yunohost.org/ci/apps/{app}/latestjob\n"
if comment["missing"]:
    PR_body += "\n### Missing results\n\n"
    for app in comment['missing']:
        PR_body += f"- {app} | https://ci-apps.yunohost.org/ci/apps/{app}/latestjob\n"
if comment["outdated"]:
    PR_body += "\n### Outdated results\n\n"
    for app in comment['outdated']:
        PR_body += f"- [ ] {app} | https://ci-apps.yunohost.org/ci/apps/{app}/latestjob\n"

PR = {"title": "Update app levels according to CI results",
      "body": PR_body,
      "head": "update_app_levels",
      "base": "master"}

with requests.Session() as s:
    s.headers.update({"Authorization": f"token {token}"})
r = s.post("https://api.github.com/repos/yunohost/apps/pulls", json.dumps(PR))

if r.status_code != 200:
    print(r.text)
    sys.exit(1)
