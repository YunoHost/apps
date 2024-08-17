#!/usr/bin/env python3

import sys
import tomlkit
import hashlib
import argparse
import hmac
from functools import cache
import tempfile
import aiohttp
import logging
from pathlib import Path
import re

from typing import Optional
from git import Actor, Repo, GitCommandError
from sanic import HTTPResponse, Request, Sanic, response

# add apps/tools to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from readme_generator.make_readme import generate_READMEs

TOOLS_DIR = Path(__file__).resolve().parent.parent

DEBUG = False
UNSAFE = False

APP = Sanic(__name__)


@cache
def github_webhook_secret() -> str:
    return (
        (TOOLS_DIR / ".github_webhook_secret")
        .open("r", encoding="utf-8")
        .read()
        .strip()
    )


@cache
def github_login() -> str:
    return (TOOLS_DIR / ".github_login").open("r", encoding="utf-8").read().strip()


@cache
def github_token() -> str:
    return (TOOLS_DIR / ".github_token").open("r", encoding="utf-8").read().strip()


@APP.route("/github", methods=["GET"])
async def github_get(request: Request) -> HTTPResponse:
    return response.text(
        "You aren't supposed to go on this page using a browser, it's for webhooks push instead."
    )


@APP.route("/github", methods=["POST"])
async def github_post(request: Request) -> HTTPResponse:
    if UNSAFE and (signatures_reply := check_webhook_signatures(request)):
        return signatures_reply

    event = request.headers.get("X-Github-Event")
    if event == "push":
        return on_push(request)

    if event == "issue_comment":
        infos = request.json
        valid_pr_comment = (
            infos["action"] == "created"
            and infos["issue"]["state"] == "open"
            and "pull_request" in infos["issue"]
        )
        pr_infos = await get_pr_infos(request)

        if valid_pr_comment:
            return on_pr_comment(request, pr_infos)
        else:
            return response.empty()

    return response.json({"error": f"Unknown event '{event}'"}, 422)


async def get_pr_infos(request: Request) -> dict:
    pr_infos_url = request.json["issue"]["pull_request"]["url"]
    async with aiohttp.ClientSession() as session:
        async with session.get(pr_infos_url) as resp:
            pr_infos = await resp.json()
    return pr_infos


def check_webhook_signatures(request: Request) -> Optional[HTTPResponse]:
    logging.warning("Unsafe webhook!")
    header_signature = request.headers.get("X-Hub-Signature")
    if header_signature is None:
        logging.error("no header X-Hub-Signature")
        return response.json({"error": "No X-Hub-Signature"}, 403)

    sha_name, signature = header_signature.split("=")
    if sha_name != "sha1":
        logging.error("signing algo isn't sha1, it's '%s'" % sha_name)
        return response.json({"error": "Signing algorightm is not sha1 ?!"}, 501)

    # HMAC requires the key to be bytes, but data is string
    mac = hmac.new(
        github_webhook_secret().encode(), msg=request.body, digestmod=hashlib.sha1
    )

    if not hmac.compare_digest(str(mac.hexdigest()), str(signature)):
        return response.json({"error": "Bad signature ?!"}, 403)
    return None


def on_push(request: Request) -> HTTPResponse:
    data = request.json
    repository = data["repository"]["full_name"]
    branch = data["ref"].split("/", 2)[2]

    if repository.startswith("YunoHost-Apps/"):

        logging.info(f"{repository} -> branch '{branch}'")

        need_push = False
        with tempfile.TemporaryDirectory() as folder_str:
            folder = Path(folder_str)
            repo = Repo.clone_from(
                f"https://{github_login()}:{github_token()}@github.com/{repository}",
                to_path=folder,
            )

            # First rebase the testing branch if possible
            if branch in ["master", "testing"]:
                result = git_repo_rebase_testing_fast_forward(repo)
                need_push = need_push or result

            repo.git.checkout(branch)
            result = generate_and_commit_readmes(repo)
            need_push = need_push or result

            if not need_push:
                logging.debug("nothing to do")
                return response.text("nothing to do")

            logging.debug(f"Pushing {repository}")
            repo.remote().push(quiet=False, all=True)

        return response.text("ok")


def on_pr_comment(request: Request, pr_infos: dict) -> HTTPResponse:
    body = request.json["comment"]["body"].strip()[:100].lower()

    # Check the comment contains proper keyword trigger

    BUMP_REV_COMMANDS = ["!bump", "!new_revision", "!newrevision"]
    if any(trigger.lower() in body for trigger in BUMP_REV_COMMANDS):
        bump_revision(request, pr_infos)
        return response.text("ok")

    REJECT_WISHLIST_COMMANDS = ["!reject", "!nope"]
    if any(trigger.lower() in body for trigger in REJECT_WISHLIST_COMMANDS):
        reason = ""
        for command in REJECT_WISHLIST_COMMANDS:
            try:
                reason = re.search(f"{command} (.*)", body).group(1).rstrip()
            except:
                pass
        reject_wishlist(request, pr_infos, reason)
        return response.text("ok")

    return response.empty()


def bump_revision(request: Request, pr_infos: dict) -> HTTPResponse:
    data = request.json
    repository = data["repository"]["full_name"]
    branch = pr_infos["head"]["ref"]

    if repository.startswith("YunoHost-Apps/"):

        logging.info(f"Will bump revision on {repository} branch {branch}...")
        with tempfile.TemporaryDirectory() as folder_str:
            folder = Path(folder_str)
            repo = Repo.clone_from(
                f"https://{github_login()}:{github_token()}@github.com/{repository}",
                to_path=folder,
            )
            repo.git.checkout(branch)

            manifest_file = folder / "manifest.toml"
            manifest = tomlkit.load(manifest_file.open("r", encoding="utf-8"))
            version, revision = manifest["version"].split("~ynh")
            revision = str(int(revision) + 1)
            manifest["version"] = "~ynh".join([version, revision])
            tomlkit.dump(manifest, manifest_file.open("w", encoding="utf-8"))

            repo.git.add("manifest.toml")
            repo.index.commit(
                "Bump package revision",
                author=Actor("yunohost-bot", "yunohost@yunohost.org"),
            )

            logging.debug(f"Pushing {repository}")
            repo.remote().push(quiet=False, all=True)
            return response.text("ok")


def reject_wishlist(request: Request, pr_infos: dict, reason=None) -> HTTPResponse:
    data = request.json
    repository = data["repository"]["full_name"]
    branch = pr_infos["head"]["ref"]

    if repository == "YunoHost/apps" and branch.startswith("add-to-wishlist"):

        logging.info(
            f"Will put the suggested app in the rejected list on {repository} branch {branch}..."
        )
        with tempfile.TemporaryDirectory() as folder_str:
            folder = Path(folder_str)
            repo = Repo.clone_from(
                f"https://{github_login()}:{github_token()}@github.com/{repository}",
                to_path=folder,
            )
            repo.git.checkout(branch)

            rejectedlist_file = folder / "rejectedlist.toml"
            rejectedlist = tomlkit.load(rejectedlist_file.open("r", encoding="utf-8"))

            wishlist_file = folder / "wishlist.toml"
            wishlist = tomlkit.load(wishlist_file.open("r", encoding="utf-8"))

            suggestedapp_slug = branch.replace("add-to-wishlist-", "")
            suggestedapp = {suggestedapp_slug: wishlist[suggestedapp_slug]}
            suggestedapp[suggestedapp_slug]["rejection_pr"] = pr_infos["html_url"]
            suggestedapp[suggestedapp_slug]["reason"] = reason

            wishlist.pop(suggestedapp_slug)
            rejectedlist.update(suggestedapp)

            tomlkit.dump(rejectedlist, rejectedlist_file.open("w", encoding="utf-8"))
            tomlkit.dump(wishlist, wishlist_file.open("w", encoding="utf-8"))

            repo.git.add("rejectedlist.toml")
            repo.git.add("wishlist.toml")

            suggestedapp_name = suggestedapp[suggestedapp_slug]["name"]
            repo.index.commit(
                f"Reject {suggestedapp_name} from catalog",
                author=Actor("yunohost-bot", "yunohost@yunohost.org"),
            )

            logging.debug(f"Pushing {repository}")
            repo.remote().push(quiet=False, all=True, force=True)
            return response.text("ok")


def generate_and_commit_readmes(repo: Repo) -> bool:
    assert repo.working_tree_dir is not None
    generate_READMEs(Path(repo.working_tree_dir))

    repo.git.add("README*.md")
    repo.git.add("ALL_README.md")

    diff_empty = len(repo.index.diff("HEAD")) == 0
    if diff_empty:
        return False

    repo.index.commit(
        "Auto-update READMEs", author=Actor("yunohost-bot", "yunohost@yunohost.org")
    )
    return True


def git_repo_rebase_testing_fast_forward(repo: Repo) -> bool:
    try:
        repo.git.checkout("testing")
    except GitCommandError:
        return False
    if not repo.is_ancestor("testing", "master"):
        return False
    repo.git.merge("master", ff_only=True)
    return True


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("-d", "--debug", action="store_true")
    parser.add_argument(
        "-u",
        "--unsafe",
        action="store_true",
        help="Disable Github signature checks on webhooks, for debug only.",
    )
    args = parser.parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    global DEBUG, UNSAFE
    DEBUG = args.debug
    UNSAFE = args.unsafe

    APP.run(host="127.0.0.1", port=8123, debug=args.debug)


if __name__ == "__main__":
    main()
