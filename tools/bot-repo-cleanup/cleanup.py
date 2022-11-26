#!venv/bin/python3

# Obtained with `pip install PyGithub`, better within a venv
from github import Github
from github.Workflow import Workflow

# API token for yunohost-bot, with "delete_repo" right
g = Github("TOKEN_REPLACE_ME")
u = g.get_user("yunohost-bot")

# Let's build a minimalistic summary table
print("| Repository ".ljust(22) + " | Decision |")
print("| ".ljust(22, '-')       + " | -------- |")

# For each repositories belonging to the bot (user `u`), assume we will not delete it
for repo in u.get_repos():
    delete = False
    # Proceed iff the repository is a fork (`parent` key is set) of a repository in our apps organization
    if repo.parent.full_name.split('/')[0] == "YunoHost-Apps":
        prs = []
        # Build the list of PRs currently opened in the repository
        # (the get_pulls method returns an iterable, not the full list)
        for pr in repo.parent.get_pulls(state='open', sort='created'):
            prs.append(pr)
        # If none of the PRs are opened by the bot, delete the repository
        if not any([ (pr.user == u) for pr in prs ]):
            delete = True
    else:
        print("| "+repo.name.ljust(20) + " | Skipping |")
        continue
    if delete:
        print("| "+repo.name.ljust(20) + " | Deleting |")
        repo.delete()
    else:
        print("| "+repo.name.ljust(20) + " | Keeping  |")
