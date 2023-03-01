#!venv/bin/python3

import sys, os, time
import urllib.request, json
import re

from github import Github
import github

# Debug
from rich.traceback import install
install(width=150, show_locals=True, locals_max_length=None, locals_max_string=None)

#####
#
# CONFIG
#
#####

# API token for yunohost-bot, need public.repo permission
g = Github(open(".github_token").read().strip())

# Path to the file to be updated
path=".github/workflows/updater.yml"

# Title of the PR
title="[autopatch] Upgrade auto-updater"

# Body of the PR message
body="""
Auto-updater actions need upgrading to continue working:
- actions/checkout@v3
- peter-evans/create-pull-request@v4
"""

# Author of the commit
author=github.InputGitAuthor(open(".github_login").read().strip(), open(".github_email").read().strip())

# Name of the branch created for the PR
new_branch="upgrade-auto-updater"

#####
#
# CACHE
#
#####

with open('processed.txt') as f:
    processed = f.read().splitlines()

#####
#
# CRAWL REPOSITORIES
#
#####

u = g.get_user("yunohost-bot")
org = g.get_organization("yunohost-apps")

# For each repositories belonging to the bot (user `u`)
i=0
for repo in org.get_repos():
    if repo.full_name not in processed:

        # Determine base branch, either `testing` or default branch
        try:
            base_branch = repo.get_branch("testing").name
        except:
            base_branch = repo.default_branch

        # Make sure the repository has an auto-updater
        try:
            repo.get_contents(path, ref="refs/heads/"+base_branch)
        except:
            with open('processed.txt', 'a') as pfile:
                pfile.write(repo.full_name+'\n')
            time.sleep(1.5)
            continue

        # Process the repo
        print("Processing "+repo.full_name)

        try:
            # Get the commit base for the new branch, and create it
            commit_sha = repo.get_branch(base_branch).commit.sha
            new_branch_ref = repo.create_git_ref(ref="refs/heads/"+new_branch, sha=commit_sha)
        except:
            new_branch_ref = repo.get_git_ref(ref="heads/"+new_branch)

        # Get current file contents
        contents = repo.get_contents(path, ref=new_branch_ref.ref)

        # Update the file
        updater_yml = contents.decoded_content.decode("unicode_escape")
        updater_yml = re.sub(r'(?m)uses: actions/checkout@v[\d]+', "uses: actions/checkout@v3", updater_yml)
        updater_yml = re.sub(r'(?m)uses: peter-evans/create-pull-request@v[\d]+', "uses: peter-evans/create-pull-request@v4", updater_yml)
        updated = repo.update_file(contents.path,
                                    message=title,
                                    content=updater_yml,
                                    sha=contents.sha,
                                    branch=new_branch,
                                    author=author)

        # Wait a bit to preserve the API rate limit
        time.sleep(1.5)

        # Open the PR
        pr = repo.create_pull(title="Upgrade auto-updater", body=body, head=new_branch, base=base_branch)

        print(repo.full_name+" updated with PR #"+ str(pr.id))
        i=i+1

        # Wait a bit to preserve the API rate limit
        time.sleep(1.5)

        with open('processed.txt', 'a') as pfile:
            pfile.write(repo.full_name+'\n')

print("Done. "+str(i)+" repos processed")
