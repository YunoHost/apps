#!/usr/bin/env python3

import hashlib
import hmac
from functools import cache
import tempfile
from pathlib import Path

from git import Actor, Repo
from sanic import HTTPResponse, Request, Sanic, response

from make_readme import generate_READMEs

app = Sanic(__name__)


@cache
def github_webhook_secret() -> str:
    return Path("github_webhook_secret").resolve().open(encoding="utf-8").read().strip()

@cache
def github_login() -> str:
    return Path("login").resolve().open(encoding="utf-8").read().strip()

@cache
def github_token() -> str:
    return Path("token").resolve().open(encoding="utf-8").read().strip()


@app.route("/github", methods=["GET"])
async def main_route(request: Request) -> HTTPResponse:
    return response.text(
        "You aren't supposed to go on this page using a browser, it's for webhooks push instead."
    )


@app.route("/github", methods=["POST"])
async def on_push(request: Request) -> HTTPResponse:
    header_signature = request.headers.get("X-Hub-Signature")
    if header_signature is None:
        print("no header X-Hub-Signature")
        return response.json({"error": "No X-Hub-Signature"}, 403)

    sha_name, signature = header_signature.split("=")
    if sha_name != "sha1":
        print("signing algo isn't sha1, it's '%s'" % sha_name)
        return response.json({"error": "Signing algorightm is not sha1 ?!"}, 501)

    # HMAC requires the key to be bytes, but data is string
    mac = hmac.new(
        github_webhook_secret().encode(), msg=request.body, digestmod=hashlib.sha1
    )

    if not hmac.compare_digest(str(mac.hexdigest()), str(signature)):
        return response.json({"error": "Bad signature ?!"}, 403)

    data = request.json

    repository = data["repository"]["full_name"]
    branch = data["ref"].split("/", 2)[2]

    print(f"{repository} -> branch '{branch}'")

    with tempfile.TemporaryDirectory() as folder_str:
        folder = Path(folder_str)
        repo = Repo.clone_from(
            f"https://{github_login()}:{github_token()}@github.com/{repository}",
            to_path=folder,
            single_branch=True,
            branch=branch
        )

        generate_READMEs(folder)

        repo.git.add("README*.md")

        diff_empty = len(repo.index.diff("HEAD")) == 0
        if diff_empty:
            print("nothing to do")
            return response.text("nothing to do")

        repo.index.commit(
            "Auto-update READMEs",
            author=Actor("yunohost-bot", "yunohost@yunohost.org")
        )
        repo.remote().push(quiet=False)

    return response.text("ok")


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8123, debug=True)
