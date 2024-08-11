#!/usr/bin/env python3

import os
import argparse
import tempfile
import logging
from pathlib import Path
from typing import Optional
from git import Repo
from .utils import set_apps_path


DEFAULT_GIT_REPO = "https://github.com/YunoHost/apps"

# This provides a reference to the tempfile, thus keeping it alive until sys.exit
APPS_REPO_TMPDIR: Optional[tempfile.TemporaryDirectory] = None

# This is the actual value returned by from_args()
APPS_REPO_PATH: Optional[Path] = None

APPS_CACHE_PATH: Optional[Path] = None


def add_args(parser: argparse.ArgumentParser, allow_temp: bool = True) -> None:
    env_apps_dir_str = os.environ.get("YNH_APPS_DIR")
    env_apps_dir = Path(env_apps_dir_str) if env_apps_dir_str is not None else None

    repo_group = parser.add_mutually_exclusive_group(required=False)
    repo_group.add_argument(
        "-l",
        "--apps-dir",
        type=Path,
        default=env_apps_dir,
        help="Path to a local 'apps' repository",
    )
    if allow_temp:
        repo_group.add_argument(
            "-r",
            "--apps-repo",
            type=str,
            default=DEFAULT_GIT_REPO,
            help="Git url to clone the remote 'apps' repository",
        )
    parser.add_argument(
        "-c",
        "--apps-cache",
        type=Path,
        help="Path to the apps cache directory (default=<apps repo>/.apps_cache)",
    )


def from_args(args: Optional[argparse.Namespace]) -> Path:
    global APPS_REPO_PATH
    global APPS_REPO_TMPDIR

    if APPS_REPO_PATH is not None:
        return APPS_REPO_PATH

    assert args is not None
    if args.apps_dir is not None:
        APPS_REPO_PATH = args.apps_dir
    elif args.apps_repo is not None:
        APPS_REPO_TMPDIR = tempfile.TemporaryDirectory(prefix="yunohost_apps_")
        APPS_REPO_PATH = Path(APPS_REPO_TMPDIR.name)
        logging.info("Cloning the 'apps' repository...")
        repo = Repo.clone_from(args.apps_repo, to_path=APPS_REPO_PATH)
        assert repo.working_tree_dir is not None
    else:
        raise RuntimeError("You need to pass either --apps-repo or --apps-dir!")

    assert APPS_REPO_PATH is not None
    set_apps_path(APPS_REPO_PATH)
    return APPS_REPO_PATH


def cache_path(args: Optional[argparse.Namespace]) -> Path:
    global APPS_CACHE_PATH

    if APPS_CACHE_PATH is not None:
        return APPS_CACHE_PATH

    assert args is not None
    if args.apps_cache is not None:
        APPS_CACHE_PATH = args.apps_cache
    else:
        if APPS_REPO_PATH is None:
            from_args(args)
        assert APPS_REPO_PATH is not None
        APPS_CACHE_PATH = APPS_REPO_PATH / ".apps_cache"

    assert APPS_CACHE_PATH is not None
    return APPS_CACHE_PATH
