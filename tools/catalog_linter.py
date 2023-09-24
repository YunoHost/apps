#!/usr/bin/env python3

import json
import sys
from functools import cache
from pathlib import Path
from typing import Any, Dict, Generator, List, Tuple

import jsonschema
import toml

APPS_ROOT = Path(__file__).parent.parent


@cache
def get_catalog() -> Dict[str, Dict[str, Any]]:
    catalog_path = APPS_ROOT / "apps.toml"
    return toml.load(catalog_path)


@cache
def get_categories() -> Dict[str, Any]:
    categories_path = APPS_ROOT / "categories.toml"
    return toml.load(categories_path)


@cache
def get_antifeatures() -> Dict[str, Any]:
    antifeatures_path = APPS_ROOT / "antifeatures.toml"
    return toml.load(antifeatures_path)


def validate_schema() -> Generator[str, None, None]:
    with open(APPS_ROOT / "schemas" / "apps.toml.schema.json", encoding="utf-8") as file:
        apps_catalog_schema = json.load(file)
    validator = jsonschema.Draft202012Validator(apps_catalog_schema)
    for error in validator.iter_errors(get_catalog()):
        yield f"at .{'.'.join(error.path)}: {error.message}"


def check_app(app: str, infos: Dict[str, Any]) -> Generator[str, None, None]:
    if "state" not in infos:
        yield "state is missing"
        return

    if infos["state"] != "working":
        return

    repo_name = infos.get("url", "").split("/")[-1]
    if repo_name != f"{app}_ynh":
        yield f"repo name should be {app}_ynh, not in {repo_name}"

    antifeatures = infos.get("antifeatures", [])
    for antifeature in antifeatures:
        if antifeature not in get_antifeatures():
            yield f"unknown antifeature {antifeature}"

    category = infos.get("category")
    if not category:
        yield "category is missing"
    else:
        if category not in get_categories():
            yield f"unknown category {category}"

        subtags = infos.get("subtags", [])
        for subtag in subtags:
            if subtag not in get_categories()[category].get("subtags", []):
                yield f"unknown subtag {category} / {subtag}"


def check_all_apps() -> Generator[Tuple[str, List[str]], None, None]:
    for app, info in get_catalog().items():
        errors = list(check_app(app, info))
        if errors:
            yield app, errors


def main() -> None:
    has_errors = False

    schema_errors = list(validate_schema())
    if schema_errors:
        has_errors = True
        print("Error while validating catalog against schema:")
    for error in schema_errors:
        print(f"  - {error}")
    if schema_errors:
        print()

    for app, errors in check_all_apps():
        has_errors = True
        print(f"{app}:")
        for error in errors:
            print(f"  - {error}")

    if has_errors:
        sys.exit(1)


if __name__ == "__main__":
    main()
