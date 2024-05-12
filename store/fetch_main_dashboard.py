import os
import sys
import requests
import json
import toml
from github import Github

sys.path = [os.path.dirname(__file__)] + sys.path
from utils import get_catalog


try:
    config = toml.loads(open("config.toml").read())
except Exception:
    print(
        "You should create a config.toml with the appropriate key/values, cf config.toml.example"
    )
    sys.exit(1)

github_token = config.get("GITHUB_TOKEN")

if github_token is None:
    print("You should add a GITHUB_TOKEN to config.toml")
    sys.exit(1)

g = Github(github_token)

catalog = get_catalog()
main_ci_apps_results = requests.get(
    "https://ci-apps.yunohost.org/ci/api/results"
).json()
nextdebian_ci_apps_results = requests.get(
    "https://ci-apps-bookworm.yunohost.org/ci/api/results"
).json()


def get_github_infos(github_orga_and_repo):

    repo = g.get_repo(github_orga_and_repo)
    infos = {}

    pulls = [p for p in repo.get_pulls()]

    infos["nb_prs"] = len(pulls)
    infos["nb_issues"] = repo.open_issues_count - infos["nb_prs"]

    testings = [p for p in pulls if p.head.ref == "testing"]
    testing = testings[0] if testings else None
    ci_auto_updates = [p for p in pulls if p.head.ref.startswith("ci-auto-update")]
    ci_auto_update = (
        sorted(ci_auto_updates, key=lambda p: p.created_at, reverse=True)[0]
        if ci_auto_updates
        else None
    )

    for p in ([testing] if testing else []) + (
        [ci_auto_update] if ci_auto_update else []
    ):

        if p.head.label != "YunoHost-Apps:testing" and not (
            p.user.login == "yunohost-bot" and p.head.ref.startswith("ci-auto-update-")
        ):
            continue

        infos["testing" if p.head.ref == "testing" else "ci-auto-update"] = {
            "branch": p.head.ref,
            "url": p.html_url,
            "timestamp_created": int(p.created_at.timestamp()),
            "timestamp_updated": int(p.updated_at.timestamp()),
            "statuses": [
                {
                    "state": s.state,
                    "context": s.context,
                    "url": s.target_url,
                    "timestamp": int(s.updated_at.timestamp()),
                }
                for s in repo.get_commit(p.head.sha).get_combined_status().statuses
            ],
        }

    return infos


consolidated_infos = {}
for app, infos in catalog["apps"].items():

    if infos["state"] != "working":
        continue

    print(app)

    consolidated_infos[app] = {
        "public_level": infos["level"],
        "url": infos["git"]["url"],
        "timestamp_latest_commit": infos["lastUpdate"],
        "maintainers": infos["manifest"]["maintainers"],
        "antifeatures": infos["antifeatures"],
        "packaging_format": infos["manifest"]["packaging_format"],
        "ci_results": {
            "main": (
                {
                    "level": main_ci_apps_results[app]["level"],
                    "timestamp": main_ci_apps_results[app]["timestamp"],
                }
                if app in main_ci_apps_results
                else None
            ),
            "nextdebian": (
                {
                    "level": nextdebian_ci_apps_results[app]["level"],
                    "timestamp": nextdebian_ci_apps_results[app]["timestamp"],
                }
                if app in nextdebian_ci_apps_results
                else None
            ),
        },
    }

    if infos["git"]["url"].lower().startswith("https://github.com/"):
        consolidated_infos[app].update(
            get_github_infos(
                infos["git"]["url"].lower().replace("https://github.com/", "")
            )
        )

open(".cache/dashboard.json", "w").write(json.dumps(consolidated_infos))
