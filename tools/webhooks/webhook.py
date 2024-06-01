#!/usr/bin/env python3

import sys
import hashlib
import argparse
import hmac
from functools import cache
import tempfile
import logging
from pathlib import Path

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
    return (TOOLS_DIR / ".github_webhook_secret").open("r", encoding="utf-8").read().strip()

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
    
    return response.json({"error": f"Unknown event '{event}'"}, 422)


def check_webhook_signatures(request: Request) -> HTTPResponse | None:
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
    parser.add_argument("-u", "--unsafe", action="store_true",
                        help="Disable Github signature checks on webhooks, for debug only.")
    args = parser.parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)


    global DEBUG, UNSAFE
    DEBUG = args.debug
    UNSAFE = args.unsafe

    APP.run(host="127.0.0.1", port=8123, debug=args.debug)

if __name__ == "__main__":
    main()
