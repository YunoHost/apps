#!venv/bin/python3

from github import Github
from github.Workflow import Workflow

# API token for yunohost-bot, with "delete_repo" right
g = Github("TOKEN_REPLACE_ME")
u = g.get_user("yunohost-bot")

print("| Repository ".ljust(22) + " | Decision |")
print("| ".ljust(22, '-')       + " | -------- |")

for repo in u.get_repos():
    delete = False
    if repo.parent.full_name.split('/')[0] == "YunoHost-Apps":
        prs = []
        for pr in repo.parent.get_pulls(state='open', sort='created'):
            prs.append(pr)
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
