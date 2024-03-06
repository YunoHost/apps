#! /usr/bin/env python3

import argparse
import json
import os
from pathlib import Path

import toml
from jinja2 import Environment, FileSystemLoader


def value_for_lang(values, lang):
    if not isinstance(values, dict):
        return values
    if lang in values:
        return values[lang]
    elif "en" in values:
        return values["en"]
    else:
        return list(values.values())[0]

def generate_READMEs(app_path: str):

    app_path = Path(app_path)

    if not app_path.exists():
        raise Exception("App path provided doesn't exists ?!")

    if os.path.exists(app_path / "manifest.json"):
        manifest = json.load(open(app_path / "manifest.json"))
    else:
        manifest = toml.load(open(app_path / "manifest.toml"))

    upstream = manifest.get("upstream", {})

    catalog = toml.load(open(Path(os.path.abspath(__file__)).parent.parent.parent / "apps.toml"))
    from_catalog = catalog.get(manifest['id'], {})

    antifeatures_list = toml.load(open(Path(os.path.abspath(__file__)).parent.parent.parent / "antifeatures.toml"))

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

        # TODO: Add url to the documentation... and actually create that documentation :D
        antifeatures = { a: antifeatures_list[a] for a in from_catalog.get('antifeatures', [])}
        for k, v in antifeatures.items():
            antifeatures[k]['title'] = value_for_lang(v['title'], lang)
            if manifest.get("antifeatures", {}).get(k, None):
                antifeatures[k]['description'] = value_for_lang(manifest.get("antifeatures", {}).get(k, None), lang)
            else:
                antifeatures[k]['description'] = value_for_lang(antifeatures[k]['description'], lang)

        out = template.render(
            lang=lang,
            upstream=upstream,
            description=description,
            screenshots=screenshots,
            disclaimer=disclaimer,
            antifeatures=antifeatures,
            manifest=manifest,
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
