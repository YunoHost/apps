#!/usr/bin/env python3

import argparse
import json
import sys
from pathlib import Path
from difflib import SequenceMatcher
from typing import Any, Dict, Generator, List, Tuple

import jsonschema
import appslib.get_apps_repo as get_apps_repo
from appslib.utils import (
    get_antifeatures,  # pylint: disable=import-error
    get_catalog,
    get_categories,
    get_graveyard,
    get_wishlist,
)


def validate_schema(data: dict, schema_path: Path) -> List[str]:
    schema = json.load(schema_path.open("r", encoding="utf-8"))
    validator = jsonschema.Draft202012Validator(schema)
    return [
        f"at .{'.'.join(error.path)}: {error.message}"
        for error in validator.iter_errors(data)
    ]


def validate_schema_pretty(apps_path: Path, data: dict, name: str) -> bool:
    schema_path = apps_path / "schemas" / f"{name}.toml.schema.json"
    schema_errors = list(validate_schema(data, schema_path))
    if schema_errors:
        print(f"Error while validating {name} against schema:")
        for error in schema_errors:
            print(f"  - {error}")
        print()
    return bool(schema_errors)


def check_app(
    app: str, infos: Dict[str, Any]
) -> Generator[Tuple[str, bool], None, None]:
    if "state" not in infos:
        yield "state is missing", True
        return

    # validate that the app is not (anymore?) in the wishlist
    # we use fuzzy matching because the id in catalog may not be the same exact id as in the wishlist
    # some entries are ignore-hard-coded, because e.g. radarr an readarr are really different apps...
    ignored_wishlist_entries = ["readarr"]
    wishlist_matches = [
        wish
        for wish in get_wishlist()
        if wish not in ignored_wishlist_entries
        and SequenceMatcher(None, app, wish).ratio() > 0.9
    ]
    if wishlist_matches:
        yield f"app seems to be listed in wishlist: {wishlist_matches}", True

    ignored_graveyard_entries = ["mailman"]
    graveyard_matches = [
        grave
        for grave in get_graveyard()
        if grave not in ignored_graveyard_entries
        and SequenceMatcher(None, app, grave).ratio() > 0.9
    ]
    if graveyard_matches:
        yield f"app seems to be listed in graveyard: {graveyard_matches}", True

    repo_name = infos.get("url", "").split("/")[-1]
    if repo_name != f"{app}_ynh":
        yield f"repo name should be {app}_ynh, not in {repo_name}", True

    antifeatures = infos.get("antifeatures", [])
    for antifeature in antifeatures:
        if antifeature not in get_antifeatures():
            yield f"unknown antifeature {antifeature}", True

    category = infos.get("category")
    if not category:
        yield "category is missing", True
    else:
        if category not in get_categories():
            yield f"unknown category {category}", True

        subtags = infos.get("subtags", [])
        for subtag in subtags:
            if subtag not in get_categories().get(category, {}).get("subtags", []):
                yield f"unknown subtag {category} / {subtag}", False


def check_all_apps() -> bool:
    has_errors = False
    for app, info in get_catalog().items():
        errors = list(check_app(app, info))
        if errors:
            print(f"{app}:")
        for error, is_fatal in errors:
            if is_fatal:
                has_errors = True
            level = "error" if is_fatal else "warning"
            print(f"  - {level}: {error}")
    return has_errors


def main() -> None:
    parser = argparse.ArgumentParser()
    get_apps_repo.add_args(parser)
    args = parser.parse_args()
    apps_path = get_apps_repo.from_args(args)

    has_errors = False

    has_errors |= validate_schema_pretty(apps_path, get_antifeatures(), "antifeatures")
    has_errors |= validate_schema_pretty(apps_path, get_catalog(), "apps")
    has_errors |= validate_schema_pretty(apps_path, get_categories(), "categories")
    has_errors |= validate_schema_pretty(apps_path, get_graveyard(), "graveyard")
    has_errors |= validate_schema_pretty(apps_path, get_wishlist(), "wishlist")

    has_errors |= check_all_apps()

    sys.exit(has_errors)


if __name__ == "__main__":
    main()
