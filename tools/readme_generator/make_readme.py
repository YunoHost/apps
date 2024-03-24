#! /usr/bin/env python3

import os
import argparse
import json
from pathlib import Path
from copy import deepcopy

from typing import Dict, Optional, List, Tuple

import toml
from jinja2 import Environment, FileSystemLoader
from babel.support import Translations
from babel.messages.pofile import PoFileParser
from langcodes import Language

README_GEN_DIR = Path(__file__).resolve().parent
APPS_REPO_ROOT = README_GEN_DIR.parent.parent


def value_for_lang(values: Dict, lang: str):
    if not isinstance(values, dict):
        return values
    if lang in values:
        return values[lang]
    elif "en" in values:
        return values["en"]
    else:
        return list(values.values())[0]


def generate_READMEs(app_path: Path):
    if not app_path.exists():
        raise Exception("App path provided doesn't exists ?!")

    if (app_path / "manifest.json").exists():
        manifest = json.load(open(app_path / "manifest.json"))
    else:
        manifest = toml.load(open(app_path / "manifest.toml"))

    upstream = manifest.get("upstream", {})

    catalog = toml.load((APPS_REPO_ROOT / "apps.toml").open(encoding="utf-8"))
    from_catalog = catalog.get(manifest["id"], {})

    antifeatures_list = toml.load(
        (APPS_REPO_ROOT / "antifeatures.toml").open(encoding="utf-8")
    )

    if not upstream and not (app_path / "doc" / "DISCLAIMER.md").exists():
        print(
            "There's no 'upstream' key in the manifest, and doc/DISCLAIMER.md doesn't exists - therefore assuming that we shall not auto-update the README.md for this app yet."
        )
        return

    poparser = PoFileParser({})
    poparser.parse(open("messages.pot"))

    # we only want to translate a README if all strings are translatables so we
    # do this loop to detect which language provides a full translation
    fully_translated_langs: List[str] = []
    for available_translations in os.listdir("translations"):
        translations = Translations.load("translations", available_translations)

        is_fully_translated = True
        for sentence in poparser.catalog:
            # ignore empty strings
            if not sentence.strip():
                continue

            if sentence not in translations._catalog:
                is_fully_translated = False
                break

            if not translations._catalog[sentence]:
                is_fully_translated = False
                break

        if is_fully_translated:
            fully_translated_langs.append(available_translations)
        else:
            print(
                "WARNING: skip generating translated README for "
                f"{Language(available_translations).language_name()} ({available_translations}) "
                "because it is not fully translated yet."
            )

    fully_translated_langs.sort()

    screenshots: List[str] = []

    screenshots_dir = app_path / "doc" / "screenshots"
    if screenshots_dir.exists():
        for entry in screenshots_dir.iterdir():
            # only pick files (no folder) on the root of 'screenshots'
            if not entry.is_file():
                continue
            # ignore '.gitkeep' or any file whose name begins with a dot
            if entry.name.startswith("."):
                continue
            screenshots.append(str(entry.relative_to(app_path)))

    def generate_single_README(lang_suffix: str, lang: str):
        env = Environment(
            loader=FileSystemLoader(README_GEN_DIR / "templates"),
            extensions=["jinja2.ext.i18n"],
        )
        translations = Translations.load("translations", [lang])
        env.install_gettext_translations(translations)

        template = env.get_template("README.md.j2")

        if (app_path / "doc" / f"DESCRIPTION{lang_suffix}.md").exists():
            description = (
                app_path / "doc" / f"DESCRIPTION{lang_suffix}.md"
            ).read_text()
        # Fallback to english if maintainer too lazy to translate the description
        elif (app_path / "doc" / "DESCRIPTION.md").exists():
            description = (app_path / "doc" / "DESCRIPTION.md").read_text()
        else:
            description = None

        disclaimer: Optional[str]
        if (app_path / "doc" / f"DISCLAIMER{lang_suffix}.md").exists():
            disclaimer = (app_path / "doc" / f"DISCLAIMER{lang_suffix}.md").read_text()
        # Fallback to english if maintainer too lazy to translate the disclaimer idk
        elif (app_path / "doc" / "DISCLAIMER.md").exists():
            disclaimer = (app_path / "doc" / "DISCLAIMER.md").read_text()
        else:
            disclaimer = None

        # TODO: Add url to the documentation... and actually create that documentation :D
        antifeatures = {
            a: deepcopy(antifeatures_list[a])
            for a in from_catalog.get("antifeatures", [])
        }
        for k, v in antifeatures.items():
            antifeatures[k]["title"] = value_for_lang(v["title"], lang)
            if manifest.get("antifeatures", {}).get(k, None):
                antifeatures[k]["description"] = value_for_lang(
                    manifest.get("antifeatures", {}).get(k, None), lang
                )
            else:
                antifeatures[k]["description"] = value_for_lang(
                    antifeatures[k]["description"], lang
                )

        out: str = template.render(
            lang=lang,
            upstream=upstream,
            description=description,
            screenshots=screenshots,
            disclaimer=disclaimer,
            antifeatures=antifeatures,
            manifest=manifest,
        )
        (app_path / f"README{lang_suffix}.md").write_text(out)

    generate_single_README("", "en")

    for lang in fully_translated_langs:
        generate_single_README("_" + lang, lang)

    links_to_other_READMEs = []
    for language in fully_translated_langs:
        translations = Translations.load("translations", [language])
        language_name_in_itself = Language.get(language).autonym()
        links_to_other_READMEs.append(
            (
                f"README_{language}.md",
                translations.gettext("Read the README in %(language)s")
                % {"language": language_name_in_itself},
            )
        )

    env = Environment(loader=FileSystemLoader(README_GEN_DIR / "templates"))
    out: str = env.get_template("ALL_README.md.j2").render(
        links_to_other_READMEs=links_to_other_READMEs
    )
    (app_path / "ALL_README.md").write_text(out)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Automatically (re)generate README for apps"
    )
    parser.add_argument(
        "app_path", type=Path, help="Path to the app to generate/update READMEs for"
    )

    args = parser.parse_args()
    generate_READMEs(Path(args.app_path))
