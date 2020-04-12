#!/usr/bin/python3

import sys
import os
import re
import json
import subprocess
import yaml
import time

now = time.time()

catalog = json.load(open("apps.json"))

my_env = os.environ.copy()
my_env["GIT_TERMINAL_PROMPT"] = "0"

os.makedirs(".apps_cache", exist_ok=True)
os.makedirs("builds/", exist_ok=True)

def error(msg):
    msg = "[Applist builder error] " + msg
    if os.path.exists("/usr/bin/sendxmpppy"):
        subprocess.call(["sendxmpppy", msg], stdout=open(os.devnull, 'wb'))
    print(msg + "\n")

# Progress bar helper, stolen from https://stackoverflow.com/a/34482761
def progressbar(it, prefix="", size=60, file=sys.stdout):
    count = len(it)
    def show(j, name=""):
        name += "          "
        x = int(size*j/count)
        file.write("%s[%s%s] %i/%i %s\r" % (prefix, "#"*x, "."*(size-x), j,  count, name))
        file.flush()
    show(0)
    for i, item in enumerate(it):
        yield item
        show(i+1, item[0])
    file.write("\n")
    file.flush()

###################################
# App git clones cache management #
###################################

def app_cache_folder(app):
    return os.path.join(".apps_cache", app)


def git(cmd, in_folder=None):

    if in_folder:
        cmd = "-C " + in_folder + " " + cmd
    cmd = "git " + cmd
    return subprocess.check_output(cmd.split(), env=my_env).strip().decode("utf-8")


def refresh_all_caches():

    for app, infos in progressbar(sorted(catalog.items()), "Updating git clones: ", 40):
        app = app.lower()
        if not os.path.exists(app_cache_folder(app)):
            try:
                init_cache(app, infos)
            except Exception as e:
                error("Could not init cache for %s: %s" % (app, e))
        else:
            try:
                refresh_cache(app, infos)
            except Exception as e:
                error("Could not refresh cache for %s: %s" % (app, e))


def init_cache(app, infos):

    if infos["state"] == "notworking":
        depth = 5
    if infos["state"] == "inprogress":
        depth = 20
    else:
        depth = 40

    git("clone --quiet --depth {depth} --single-branch --branch master {url} {folder}".format(depth=depth, url=infos["url"], folder=app_cache_folder(app)))


def refresh_cache(app, infos):

    # Don't refresh if already refreshed during last hour
    fetch_head = app_cache_folder(app) + "/.git/FETCH_HEAD"
    if os.path.exists(fetch_head) and now - os.path.getmtime(fetch_head) < 3600:
        return

    git("remote set-url origin " + infos["url"], in_folder=app_cache_folder(app))
    git("fetch --quiet origin master --force", in_folder=app_cache_folder(app))
    git("reset origin/master --hard", in_folder=app_cache_folder(app))


################################
# Actual list build management #
################################

def build_catalog():

    result_dict = {}

    for app, infos in progressbar(sorted(catalog.items()), "Processing: ", 40):

        app = app.lower()

        try:
            app_dict = build_app_dict(app, infos)
        except Exception as e:
            error("Processing %s failed: %s" % (app, str(e)))
            continue

        result_dict[app_dict["id"]] = app_dict

    #####################
    # Current version 2 #
    #####################
    categories = yaml.load(open("categories.yml").read())
    os.system("mkdir -p ./builds/default/v2/")
    with open("builds/default/v2/apps.json", 'w') as f:
        f.write(json.dumps({"apps": result_dict, "categories": categories}, sort_keys=True))

    ####################
    # Legacy version 1 #
    ####################
    os.system("mkdir -p ./builds/default/v1/")
    with open("./builds/default/v1/apps.json", 'w') as f:
        f.write(json.dumps(result_dict, sort_keys=True))

    ####################
    # Legacy version 0 #
    ####################
    official_apps = set(["agendav", "ampache", "baikal", "dokuwiki", "etherpad_mypads", "hextris", "jirafeau", "kanboard", "my_webapp", "nextcloud", "opensondage", "phpmyadmin", "piwigo", "rainloop", "roundcube", "searx", "shellinabox", "strut", "synapse", "transmission", "ttrss", "wallabag2", "wordpress", "zerobin"])

    official_apps_dict = {k: v for k, v in result_dict.items() if k in official_apps}
    community_apps_dict = {k: v for k, v in result_dict.items() if k not in official_apps}

    # We need the official apps to have "validated" as state to be recognized as official
    for app, infos in official_apps_dict.items():
        infos["state"] = "validated"

    os.system("mkdir -p ./builds/default/v0/")
    with open("./builds/default/v0/official.json", 'w') as f:
        f.write(json.dumps(official_apps_dict, sort_keys=True))

    with open("./builds/default/v0/community.json", 'w') as f:
        f.write(json.dumps(community_apps_dict, sort_keys=True))


def build_app_dict(app, infos):

    assert infos["branch"] == "master"

    # Make sure we have some cache
    this_app_cache = app_cache_folder(app)
    assert os.path.exists(this_app_cache), "No cache yet for %s" % app

    # If using head, find the most recent meaningful commit in logs
    if infos["revision"] == "HEAD":
        relevant_files = ["manifest.json", "actions.json", "hooks/", "scripts/", "conf/", "sources/"]
        most_recent_relevant_commit = "rev-list --full-history --all -n 1 -- " + " ".join(relevant_files)
        infos["revision"] = git(most_recent_relevant_commit, in_folder=this_app_cache)
        assert re.match(r"^[0-9a-f]+$", infos["revision"]), "Output was not a commit? '%s'" % infos["revision"]
    # Otherwise, validate commit exists
    else:
        assert infos["revision"] in git("rev-list --all", in_folder=this_app_cache).split("\n"), "Revision ain't in history ? %s" % infos["revision"]

    # Find timestamp corresponding to that commit
    timestamp = git("show -s --format=%ct " + infos["revision"], in_folder=this_app_cache)
    assert re.match(r"^[0-9]+$", timestamp), "Failed to get timestamp for revision ? '%s'" % timestamp
    timestamp = int(timestamp)

    # Build the dict with all the infos
    manifest = json.load(open(this_app_cache + "/manifest.json"))
    return {'id':manifest["id"],
            'git': {
                'branch': infos['branch'],
                'revision': infos["revision"],
                'url': infos["url"]
            },
            'lastUpdate': timestamp,
            'manifest': include_translations_in_manifest(manifest),
            'state': infos['state'],
            'level': infos.get('level', '?'),
            'maintained': infos.get("maintained", True),
            'high_quality': infos.get("high_quality", False),
            'featured': infos.get("featured", False),
            'category': infos.get('category', None),
            'subtags': infos.get('subtags', []),
            }


def include_translations_in_manifest(manifest):

    app_name = manifest["id"]

    for locale in os.listdir("locales"):
        if not locale.endswith("json"):
            continue

        if locale == "en.json":
            continue

        current_lang = locale.split(".")[0]
        translations = json.load(open(os.path.join("locales", locale), "r"))

        key = "%s_manifest_description" % app_name
        if translations.get(key, None):
            manifest["description"][current_lang] = translations[key]

        for category, questions in manifest["arguments"].items():
            for question in questions:
                key = "%s_manifest_arguments_%s_%s" % (app_name, category, question["name"])
                # don't overwrite already existing translation in manifests for now
                if translations.get(key) and not current_lang not in question["ask"]:
                    #print("[ask]", current_lang, key)
                    question["ask"][current_lang] = translations[key]

                key = "%s_manifest_arguments_%s_help_%s" % (app_name, category, question["name"])
                # don't overwrite already existing translation in manifests for now
                if translations.get(key) and not current_lang not in question.get("help", []):
                    #print("[help]", current_lang, key)
                    question["help"][current_lang] = translations[key]

    return manifest


######################

if __name__ == "__main__":
    refresh_all_caches()
    build_catalog()
