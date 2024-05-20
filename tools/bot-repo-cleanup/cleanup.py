#!/usr/bin/env python3

from pathlib import Path

# Obtained with `pip install PyGithub`, better within a venv
from github import Github
from github.Workflow import Workflow

TOOLS_DIR = Path(__file__).resolve().parent.parent

# API token for yunohost-bot, with "delete_repo" right

token = (TOOLS_DIR / ".github_token").open("r", encoding="utf-8").read().strip()
g = Github(token)
u = g.get_user("yunohost-bot")

# Let's build a minimalistic summary table
print("| Repository ".ljust(22) + " | Decision |")
print("| ".ljust(22, "-") + " | -------- |")

# For each repositories belonging to the bot (user `u`)
for repo in u.get_repos():
    # Proceed iff the repository is a fork (`parent` key is set) of a repository in our apps organization
    if repo.parent.full_name.split("/")[0] != "YunoHost-Apps":
        print("| " + repo.name.ljust(20) + " | Skipping |")
    else:
        # If none of the PRs are opened by the bot, delete the repository
        if not any(
            [
                (pr.user == u)
                for pr in list(repo.parent.get_pulls(state="open", sort="created"))
            ]
        ):
            print("| " + repo.name.ljust(20) + " | Deleting |")
            repo.delete()
        else:
            print("| " + repo.name.ljust(20) + " | Keeping  |")
