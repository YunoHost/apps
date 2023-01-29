#!venv/bin/python3

import sys, os, time
import urllib.request, json
import re

# Debug
from rich.traceback import install
install(show_locals=True)

from github import Github

#####
#
# CONFIG
#
#####

# API token for yunohost-bot, need public.repo permission
g = Github(open(".github_token").read().strip())

# Path to the file to be updated
path=".github/workflows/updater.yml"

# Body of the PR message
body="""
Auto-updater actions need upgrading to continue working:
- actions/checkout@v3
- peter-evans/create-pull-request@v4
"""

# Name of the branch created for the PR
new_branch="upgrade-auto-updater"

#####
#
# CRAWL REPOSITORIES
#
#####

u = g.get_user("yunohost-bot")
org = g.get_organization("yunohost-apps")

# For each repositories belonging to the bot (user `u`)
for repo in org.get_repos():
    # Determine base branch, either `testing` or default branch
    try:
        base_branch = repo.get_branch("testing").name
    except:
        base_branch = repo.default_branch
    # Make sure the repository has an auto-updater
    try:
        repo.get_contents(path, ref="refs/heads/"+base_branch)
    except:
        print("No updater in "+repo.full_name)
        continue
    # Process the repo
    try:
        print("Processing "+repo.full_name)

        # Get the commit base for the new branch, and create it
        commit_sha = repo.get_branch(base_branch).commit.sha
        new_branch_ref = repo.create_git_ref(ref="refs/heads/"+new_branch, sha=commit_sha)

        # Get current file contents
        contents = repo.get_contents(path, ref=new_branch_ref.ref)

        # Update the file
        updater_yml = contents.decoded_content.decode("unicode_escape")
        updater_yml = re.sub(r'(?m)uses: actions/checkout@v[\d]+', "uses: actions/checkout@v3", updater_yml)
        updater_yml = re.sub(r'(?m)uses: peter-evans/create-pull-request@v[\d]+', "uses: peter-evans/create-pull-request@v4", updater_yml)
        updated = repo.update_file(path=contents.path,
                                   message="Upgrade auto-updater",
                                   content=updater_yml,
                                   sha=contents.sha,
                                   branch=new_branch)

        # Open the PR
        pr = repo.create_pull(title="Upgrade auto-updater", body=body, head=new_branch, base=base_branch)

        print(repo.full_name+" updated with PR \#"+ pr.id)
        break
    except Exception as e:
        print(e)
        print("...failed. Deleting new branch.")
        repo.get_git_ref("heads/"+new_branch).delete()
        break
