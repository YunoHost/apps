#!/usr/bin/env python3
"""
Update app catalog: commit, and create a merge request
"""

import argparse
import logging
import tempfile
import textwrap
import time
from collections import OrderedDict
from typing import Any

from pathlib import Path
import jinja2
import requests
import toml
from git import Repo

APPS_REPO = "YunoHost/apps"

CI_RESULTS_URL = "https://ci-apps.yunohost.org/ci/api/results"

REPO_APPS_ROOT = Path(Repo(__file__, search_parent_directories=True).working_dir)


def github_token() -> str | None:
    github_token_path = REPO_APPS_ROOT.parent / ".github_token"
    if github_token_path.exists():
        return github_token_path.open("r", encoding="utf-8").read().strip()
    return None


def get_ci_results() -> dict[str, dict[str, Any]]:
    return requests.get(CI_RESULTS_URL, timeout=10).json()


def ci_result_is_outdated(result) -> bool:
    # 3600 * 24 * 60 = ~2 months
    return (int(time.time()) - result.get("timestamp", 0)) > 3600 * 24 * 60


def update_catalog(catalog, ci_results) -> dict:
    """
    Actually change the catalog data
    """
    # Re-sort the catalog keys / subkeys
    for app, infos in catalog.items():
        catalog[app] = OrderedDict(sorted(infos.items()))
    catalog = OrderedDict(sorted(catalog.items()))

    def app_level(app):
        if app not in ci_results:
            return 0
        if ci_result_is_outdated(ci_results[app]):
            return 0
        return ci_results[app]["level"]

    for app, info in catalog.items():
        info["level"] = app_level(app)

    return catalog


def list_changes(catalog, ci_results) -> dict[str, list[tuple[str, int, int]]]:
    """
    Lists changes for a pull request
    """

    changes = {
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
            changes["missing"].append(app)
            continue

        if ci_result_is_outdated(ci_results[app]):
            changes["outdated"].append(app)
            continue

        ci_level = ci_results[app]["level"]
        current_level = infos.get("level")

        if ci_level == current_level:
            continue

        if current_level is None or ci_level > current_level:
            changes["improvements"].append((app, current_level, ci_level))
            continue

        if ci_level < current_level:
            if ci_level <= 4 < current_level:
                changes["major_regressions"].append((app, current_level, ci_level))
            else:
                changes["minor_regressions"].append((app, current_level, ci_level))

    return changes


def pretty_changes(changes: dict[str, list[tuple[str, int, int]]]) -> str:
    pr_body_template = textwrap.dedent("""
        {%- if changes["major_regressions"] %}
        ### Major regressions 😭
        {% for app in changes["major_regressions"] %}
        - [ ] [{{app.0}}: {{app.1}} → {{app.2}}](https://ci-apps.yunohost.org/ci/apps/{{app.0}}/latestjob)
        {%- endfor %}
        {% endif %}
        {%- if changes["minor_regressions"] %}
        ### Minor regressions 😬
        {% for app in changes["minor_regressions"] %}
        - [ ] [{{app.0}}: {{app.1}} → {{app.2}}](https://ci-apps.yunohost.org/ci/apps/{{app.0}}/latestjob)
        {%- endfor %}
        {% endif %}
        {%- if changes["improvements"] %}
        ### Improvements 🥳
        {% for app in changes["improvements"] %}
        - [{{app.0}}: {{app.1}} → {{app.2}}](https://ci-apps.yunohost.org/ci/apps/{{app.0}}/latestjob)
        {%- endfor %}
        {% endif %}
        {%- if changes["missing"] %}
        ### Missing 🫠
        {% for app in changes["missing"] %}
        - [{{app}} (See latest job if it exists)](https://ci-apps.yunohost.org/ci/apps/{{app.0}}/latestjob)
        {%- endfor %}
        {% endif %}
        {%- if changes["outdated"] %}
        ### Outdated ⏰
        {% for app in changes["outdated"] %}
        - [ ] [{{app}} (See latest job if it exists)](https://ci-apps.yunohost.org/ci/apps/{{app.0}}/latestjob)
        {%- endfor %}
        {% endif %}
    """)

    return jinja2.Environment().from_string(pr_body_template).render(changes=changes)


def make_pull_request(pr_body: str) -> None:
    pr_data = {
        "title": "Update app levels according to CI results",
        "body": pr_body,
        "head": "update_app_levels",
        "base": "master"
    }

    with requests.Session() as s:
        s.headers.update({"Authorization": f"token {github_token()}"})
        response = s.post(f"https://api.github.com/repos/{APPS_REPO}/pulls", json=pr_data)

        if response.status_code == 422:
            response = s.get(f"https://api.github.com/repos/{APPS_REPO}/pulls", data={"head": "update_app_levels"})
            response.raise_for_status()
            pr_number = response.json()[0]["number"]

            # head can't be updated
            del pr_data["head"]
            response = s.patch(f"https://api.github.com/repos/{APPS_REPO}/pulls/{pr_number}", json=pr_data)
            response.raise_for_status()
            existing_url = response.json()["html_url"]
            logging.warning(f"An existing Pull Request has been updated at {existing_url} !")
        else:
            response.raise_for_status()

            new_url = response.json()["html_url"]
            logging.info(f"Opened a Pull Request at {new_url} !")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--commit", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--pr", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("-v", "--verbose", action=argparse.BooleanOptionalAction)
    args = parser.parse_args()

    logging.getLogger().setLevel(logging.INFO)
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    with tempfile.TemporaryDirectory(prefix="update_app_levels_") as tmpdir:
        logging.info("Cloning the repository...")
        apps_repo = Repo.clone_from(f"git@github.com:{APPS_REPO}", to_path=tmpdir)
        assert apps_repo.working_tree_dir is not None
        apps_toml_path = Path(apps_repo.working_tree_dir) / "apps.toml"

        # Load the app catalog and filter out the non-working ones
        catalog = toml.load(apps_toml_path.open("r", encoding="utf-8"))

        new_branch = apps_repo.create_head("update_app_levels", apps_repo.refs.master)
        apps_repo.head.reference = new_branch

        logging.info("Retrieving the CI results...")
        ci_results = get_ci_results()

        # Now compute changes, then update the catalog
        changes = list_changes(catalog, ci_results)
        pr_body = pretty_changes(changes)
        catalog = update_catalog(catalog, ci_results)

        # Save the new catalog
        updated_catalog = toml.dumps(catalog)
        updated_catalog = updated_catalog.replace(",]", " ]")
        apps_toml_path.open("w", encoding="utf-8").write(updated_catalog)

        if args.commit:
            logging.info("Committing and pushing the new catalog...")
            apps_repo.index.add("apps.toml")
            apps_repo.index.commit("Update app levels according to CI results")
            apps_repo.remote().push(force=True)

        if args.verbose:
            print(pr_body)

        if args.pr:
            logging.info("Opening a pull request...")
            make_pull_request(pr_body)


if __name__ == "__main__":
    main()
