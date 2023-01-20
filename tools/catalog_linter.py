import toml
import sys

catalog = toml.load(open('apps.toml'))
catalog = {app: infos for app, infos in catalog.items() if infos.get('state') == "working"}
categories = toml.load(open('categories.toml')).keys()

def check_apps():

    for app, infos in catalog.items():

        repo_name = infos.get("url", "").split("/")[-1]
        if repo_name != app + "_ynh":
            yield f"{app}: repo name should be {app}_ynh, not in {repo_name}"

        category = infos.get("category")
        if not category:
            yield f"{app}: missing category"
        if category not in categories:
            yield f"{app}: category {category} is not defined in categories.toml"

errors = list(check_apps())

for error in errors:
    print(error)

if errors:
    sys.exit(1)
