#! /usr/bin/env python3

import argparse
import json
import os
from pathlib import Path

from jinja2 import Environment, FileSystemLoader


def generate_READMEs(app_path: str):

    app_path = Path(app_path)

    if not app_path.exists():
        raise Exception("App path provided doesn't exists ?!")

    manifest = json.load(open(app_path / "manifest.json"))
    upstream = manifest.get("upstream", {})

    catalog = json.load(open(Path(os.path.abspath(__file__)).parent.parent.parent / "apps.json"))
    from_catalog = catalog.get(manifest['id'], {})

    if not upstream and not (app_path / "doc" / "DISCLAIMER.md").exists():
        print(
            "There's no 'upstream' key in the manifest, and doc/DISCLAIMER.md doesn't exists - therefore assuming that we shall not auto-update the README.md for this app yet."
        )
        return

    env = Environment(loader=FileSystemLoader(Path(__file__).parent / "templates"))

    for lang, lang_suffix in [("en", ""), ("fr", "_fr")]:

        template = env.get_template(f"README{lang_suffix}.md.j2")

        if (app_path / "doc" / f"DESCRIPTION{lang_suffix}.md").exists():
            description = (app_path / "doc" / f"DESCRIPTION{lang_suffix}.md").read_text()
        # Fallback to english if maintainer too lazy to translate the description
        elif (app_path / "doc" / "DESCRIPTION.md").exists():
            description = (app_path / "doc" / "DESCRIPTION.md").read_text()
        else:
            description = None

        if (app_path / "doc" / "screenshots").exists():
            screenshots = os.listdir(os.path.join(app_path, "doc", "screenshots"))
            if ".gitkeep" in screenshots:
                screenshots.remove(".gitkeep")
        else:
            screenshots = []

        if (app_path / "doc" / f"DISCLAIMER{lang_suffix}.md").exists():
            disclaimer = (app_path / "doc" / f"DISCLAIMER{lang_suffix}.md").read_text()
        # Fallback to english if maintainer too lazy to translate the disclaimer idk
        elif (app_path / "doc" / "DISCLAIMER.md").exists():
            disclaimer = (app_path / "doc" / "DISCLAIMER.md").read_text()
        else:
            disclaimer = None

        # Get the current branch using git inside the app path
        default_branch = from_catalog.get('branch', 'master')
        current_branch = os.popen(f"git -C {app_path} rev-parse --abbrev-ref HEAD").read().strip()

        if default_branch != current_branch:
            os.system(f"git -C {app_path} fetch origin {default_branch} 2>/dev/null")
            default_branch_version = os.popen(f"git -C {app_path} show FETCH_HEAD:manifest.json | jq -r .version").read().strip()
        else:
            default_branch_version = None  # we don't care in that case

        out = template.render(
            lang=lang,
            upstream=upstream,
            description=description,
            screenshots=screenshots,
            disclaimer=disclaimer,
            manifest=manifest,
            current_branch=current_branch,
            default_branch=default_branch,
            default_branch_version=default_branch_version,
        )
        (app_path / f"README{lang_suffix}.md").write_text(out)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Automatically (re)generate README for apps"
    )
    parser.add_argument(
        "app_path", help="Path to the app to generate/update READMEs for"
    )

    args = parser.parse_args()
    generate_READMEs(args.app_path)
