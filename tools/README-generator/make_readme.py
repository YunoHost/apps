#! /usr/bin/python3

import argparse
import json
import os

from jinja2 import Environment, FileSystemLoader


def generate_READMEs(app_path):

    if not os.path.exists(app_path):
        raise Exception("App path provided doesn't exists ?!")

    manifest = json.load(open(os.path.join(app_path, "manifest.json")))
    upstream = manifest.get("upstream", {})

    if not upstream and not os.path.exists(os.path.join(app_path, "doc", "DISCLAIMER.md")):
        print("There's no 'upstream' key in the manifest, and doc/DISCLAIMER.md doesn't exists - therefore assuming that we shall not auto-update the README.md for this app yet.")
        return

    env = Environment(loader=FileSystemLoader('./templates'))

    for lang, lang_suffix in [("en", ""), ("fr", "_fr")]:

        template = env.get_template(f'README{lang_suffix}.md.j2')

        if os.path.exists(os.path.join(app_path, "doc", "screenshots")):
            screenshots = os.listdir(os.path.join(app_path, "doc", "screenshots"))
            if ".gitkeep" in screenshots:
                screenshots.remove(".gitkeep")
        else:
            screenshots = []

        if os.path.exists(os.path.join(app_path, "doc", f"DISCLAIMER{lang_suffix}.md")):
            disclaimer = open(os.path.join(app_path, "doc", f"DISCLAIMER{lang_suffix}.md")).read()
        # Fallback to english if maintainer too lazy to translate the disclaimer idk
        elif os.path.exists(os.path.join(app_path, "doc", "DISCLAIMER.md")):
            disclaimer = open(os.path.join(app_path, "doc", "DISCLAIMER.md")).read()
        else:
            disclaimer = None

        out = template.render(lang=lang, upstream=upstream, screenshots=screenshots, disclaimer=disclaimer, manifest=manifest)
        with open(os.path.join(app_path, f"README{lang_suffix}.md"), "w") as f:
            f.write(out)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Automatically (re)generate README for apps')
    parser.add_argument('app_path',
                        help='Path to the app to generate/update READMEs for')

    args = parser.parse_args()
    generate_READMEs(args.app_path)
