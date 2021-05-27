import subprocess
import os
from pathlib import Path
import shutil

from github_webhook import Webhook
from flask import Flask
from make_readme import generate_READMEs

app = Flask(__name__)

github_webhook_secret = open("github_webhook_secret", "r").read().strip()
webhook = Webhook(app, endpoint="/github", secret=github_webhook_secret)

login = open("login").read().strip()
token = open("token").read().strip()

my_env = os.environ.copy()
my_env["GIT_TERMINAL_PROMPT"] = "0"
my_env["GIT_AUTHOR_NAME"] = "Yunohost-Bot"
my_env["GIT_AUTHOR_EMAIL"] = "yunohost@yunohost.org"
my_env["GIT_COMMITTER_NAME"] = "Yunohost-Bot"
my_env["GIT_COMMITTER_EMAIL"] = "yunohost@yunohost.org"


def git(cmd, in_folder=None):

    if not isinstance(cmd, list):
        cmd = cmd.split()
    if in_folder:
        cmd = ["-C", in_folder] + cmd
    cmd = ["git"] + cmd
    return subprocess.check_output(cmd, env=my_env).strip().decode("utf-8")


@app.route("/github")
def main_route():
    return "You aren't supposed to go on this page using a browser, it's for webhooks push instead."


@webhook.hook()
def on_push(data):

    repository = data["repository"]["full_name"]
    branch = data["ref"].split("/", 2)[2]

    folder = subprocess.check_output(["mktemp", "-d"]).decode('utf-8').strip()
    try:
        git(["clone", f"https://{login}:{token}@github.com/{repository}", "--single-branch", "--branch", branch, folder])
        generate_READMEs(Path(folder))

        git(["add", "README*.md"], in_folder=folder)

        diff_not_empty = bool(subprocess.check_output(["git", "diff", "HEAD", "--compact-summary"], cwd=folder).strip().decode("utf-8"))
        if not diff_not_empty:
            return

        git(["commit", "-a", "-m", "Auto-update README", "--author='Yunohost-Bot <>'"], in_folder=folder)
        git(["push", "origin", branch, "--quiet"], in_folder=folder)
    finally:
        if os.path.exists(folder):
            shutil.rmtree(folder)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8123)
