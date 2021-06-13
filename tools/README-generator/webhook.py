import os
import hmac
import shlex
import hashlib
import asyncio
import tempfile

from sanic import Sanic
from sanic.response import text
from sanic.exceptions import abort

from make_readme import generate_READMEs

app = Sanic(__name__)

github_webhook_secret = open("github_webhook_secret", "r").read().strip()

login = open("login").read().strip()
token = open("token").read().strip()

my_env = os.environ.copy()
my_env["GIT_TERMINAL_PROMPT"] = "0"
my_env["GIT_AUTHOR_NAME"] = "Yunohost-Bot"
my_env["GIT_AUTHOR_EMAIL"] = "yunohost@yunohost.org"
my_env["GIT_COMMITTER_NAME"] = "Yunohost-Bot"
my_env["GIT_COMMITTER_EMAIL"] = "yunohost@yunohost.org"


async def git(cmd, in_folder=None):

    if not isinstance(cmd, list):
        cmd = cmd.split()
    if in_folder:
        cmd = ["-C", in_folder] + cmd
    cmd = ["git"] + cmd
    cmd = " ".join(map(shlex.quote, cmd))
    command = await asyncio.create_subprocess_shell(cmd, env=my_env, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)
    data = await command.stdout.read()
    return data.decode().strip()


@app.route("/github", methods=["GET"])
def main_route(request):
    return text("You aren't supposed to go on this page using a browser, it's for webhooks push instead.")


@app.route("/github", methods=["POST"])
async def on_push(request):
    header_signature = request.headers.get("X-Hub-Signature")
    if header_signature is None:
        print("no header X-Hub-Signature")
        abort(403)

    sha_name, signature = header_signature.split("=")
    if sha_name != "sha1":
        print("signing algo isn't sha1, it's '%s'" % sha_name)
        abort(501)

    # HMAC requires the key to be bytes, but data is string
    mac = hmac.new(github_webhook_secret.encode(), msg=request.body, digestmod=hashlib.sha1)

    if not hmac.compare_digest(str(mac.hexdigest()), str(signature)):
        abort(403)

    data = request.json

    repository = data["repository"]["full_name"]
    branch = data["ref"].split("/", 2)[2]

    with tempfile.TemporaryDirectory() as folder:
        await git(["clone", f"https://{login}:{token}@github.com/{repository}", "--single-branch", "--branch", branch, folder])
        generate_READMEs(folder)

        await git(["add", "README*.md"], in_folder=folder)

        diff_not_empty = await asyncio.create_subprocess_shell(" ".join(["git", "diff", "HEAD", "--compact-summary"]), cwd=folder, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)
        diff_not_empty = await diff_not_empty.stdout.read()
        diff_not_empty = diff_not_empty.decode().strip()
        if not diff_not_empty:
            return text("nothing to do")

        await git(["commit", "-a", "-m", "Auto-update README", "--author='Yunohost-Bot <>'"], in_folder=folder)
        await git(["push", "origin", branch, "--quiet"], in_folder=folder)

    return text("ok")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8123)
