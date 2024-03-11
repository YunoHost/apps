#!/usr/bin/env python3

import json
import sys
from difflib import SequenceMatcher
from typing import Any, Dict, Generator, List, Tuple

import jsonschema
from appslib.utils import (
    REPO_APPS_ROOT,  # pylint: disable=import-error
    get_antifeatures,
    get_catalog,
    get_categories,
    get_graveyard,
    get_wishlist,
)


def validate_schema() -> Generator[str, None, None]:
    with open(
        REPO_APPS_ROOT / "schemas" / "apps.toml.schema.json", encoding="utf-8"
    ) as file:
        apps_catalog_schema = json.load(file)
    validator = jsonschema.Draft202012Validator(apps_catalog_schema)
    for error in validator.iter_errors(get_catalog()):
        yield f"at .{'.'.join(error.path)}: {error.message}"


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


def check_all_apps() -> Generator[Tuple[str, List[Tuple[str, bool]]], None, None]:
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
        print(f"{app}:")
        for error, is_fatal in errors:
            if is_fatal:
                has_errors = True
            level = "error" if is_fatal else "warning"
            print(f"  - {level}: {error}")

    if has_errors:
        sys.exit(1)


if __name__ == "__main__":
    main()
