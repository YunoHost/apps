#!/usr/bin/env python2
import re
import os
import sys
import time
import json
import zlib
import argparse

import requests
from dateutil.parser import parse


# Regular expression patterns

re_commit_author = re.compile(
    r'^author (?P<name>.+) <(?P<email>.+)> (?P<time>\d+) (?P<tz>[+-]\d+)$',
    re.MULTILINE
)


# Helpers

def fail(msg, retcode=1):
    """Show failure message and exit."""
    print("Error: {0:s}".format(msg))
    sys.exit(retcode)


def include_translations_in_manifest(app_name, manifest):
    for i in os.listdir("locales"):
        if not i.endswith("json"):
            continue

        if i == "en.json":
            continue

        current_lang = i.split(".")[0]
        translations = json.load(open(os.path.join("locales", i), "r"))

        key = "%s_manifest_description" % app_name
        if key in translations and translations[key]:
            manifest["description"][current_lang] = translations[key]

        for category, questions in manifest["arguments"].items():
            for question in questions:
                key = "%s_manifest_arguments_%s_%s" % (app_name, category, question["name"])
                # don't overwrite already existing translation in manifests for now
                if key in translations and translations[key] and not current_lang not in question["ask"]:
                    print "[ask]", current_lang, key
                    question["ask"][current_lang] = translations[key]

                key = "%s_manifest_arguments_%s_help_%s" % (app_name, category, question["name"])
                # don't overwrite already existing translation in manifests for now
                if key in translations and translations[key] and not current_lang not in question.get("help", []):
                    print "[help]", current_lang, key
                    question["help"][current_lang] = translations[key]

    return manifest


def get_json(url, verify=True):

    try:
        # Retrieve and load manifest
        if ".github" in url:
            r = requests.get(url, verify=verify, auth=token)
        else:
            r = requests.get(url, verify=verify)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.RequestException as e:
        print("-> Error: unable to request %s, %s" % (url, e))
        return None
    except ValueError as e:
        print("-> Error: unable to decode json from %s : %s" % (url, e))
        return None

def get_zlib(url, verify=True):

    try:
        # Retrieve last commit information
        r = requests.get(obj_url, verify=verify)
        r.raise_for_status()
        return zlib.decompress(r.content).decode('utf-8').split('\x00')
    except requests.exceptions.RequestException as e:
        print("-> Error: unable to request %s, %s" % (obj_url, e))
        return None
    except zlib.error as e:
        print("-> Error: unable to decompress object from %s : %s" % (url, e))
        return None

# Main

# Create argument parser
parser = argparse.ArgumentParser(description='Process YunoHost application list.')

# Add arguments and options
parser.add_argument("input", help="Path to json input file")
parser.add_argument("-o", "--output", help="Path to result file. If not specified, '-build' suffix will be added to input filename.")
parser.add_argument("-g", "--github", help="Github token <username>:<password>")

# Parse args
args = parser.parse_args()

try:
    # Retrieve apps list from json file
    with open(args.input) as f:
        apps_list = json.load(f)
except IOError as e:
    fail("%s file not found" % args.input)

# Get list name from filename
list_name = os.path.splitext(os.path.basename(args.input))[0]
print(":: Building %s list..." % list_name)

# Args default
if not args.output:
    args.output = '%s-build.json' % list_name

already_built_file = {}
if os.path.exists(args.output):
    try:
        already_built_file = json.load(open(args.output))
    except Exception as e:
        print("Error while trying to load already built file: %s" % e)

# GitHub credentials
if args.github:
    token = (args.github.split(':')[0], args.github.split(':')[1])
else:
    token = None

# Loop through every apps
result_dict = {}
for app, info in apps_list.items():
    print("---")
    print("Processing '%s'..." % app)
    app = app.lower()

    # Store usefull values
    app_branch = info['branch']
    app_url = info['url']
    app_rev = info['revision']
    app_state = info["state"]
    app_level = info.get("level")
    app_maintained = info.get("maintained", True)
    app_featured = info.get("featured", False)
    app_high_quality = info.get("high_quality", False)

    forge_site = app_url.split('/')[2]
    owner = app_url.split('/')[3]
    repo = app_url.split('/')[4]
    if forge_site == "github.com":
        forge_type = "github"
    elif forge_site == "framagit.org":
        forge_type = "gitlab"
    elif forge_site == "code.ffdn.org":
        forge_type = "gogs"
    else:
        forge_type = "unknown"

    previous_state = already_built_file.get(app, {}).get("state", {})

    manifest = {}
    timestamp = None

    previous_rev = already_built_file.get(app, {}).get("git", {}).get("revision", None)
    previous_url = already_built_file.get(app, {}).get("git", {}).get("url")
    previous_level = already_built_file.get(app, {}).get("level")
    previous_maintained = already_built_file.get(app, {}).get("maintained")
    previous_featured = already_built_file.get(app, {}).get("featured")
    previous_high_quality = already_built_file.get(app, {}).get("high_quality")

    if forge_type == "github" and app_rev == "HEAD":

        if previous_rev is None:
            previous_rev = 'HEAD'

        url = "https://api.github.com/repos/{}/{}/git/refs/heads/{}".format(owner, repo, app_branch)
        head = get_json(url)
        app_rev = head["object"]["sha"]

        url = "https://api.github.com/repos/{}/{}/compare/{}...{}".format(owner, repo, previous_rev, app_branch)
        diff = get_json(url)

        if not diff["commits"]:
            app_rev = previous_rev if previous_rev != 'HEAD' else app_rev
        else:
            # Only if those files got updated, do we want to update the
            # commit (otherwise that would trigger an unecessary upgrade)
            ignore_files = [ "README.md", "LICENSE", ".gitignore", "check_process", ".travis.yml" ]
            diff_files = [ f for f in diff["files"] if f["filename"] not in ignore_files ]

            if diff_files:
                print("This app points to HEAD and significant changes where found between HEAD and previous commit")
                app_rev = diff["commits"][-1]["sha"]
            else:
                print("This app points to HEAD but no significant changes where found compared to HEAD, so keeping the previous commit")
                app_rev = previous_rev if previous_rev != 'HEAD' else app_rev

    print("Previous commit : %s" % previous_rev)
    print("Current commit : %s" % app_rev)

    if previous_rev == app_rev and previous_url == app_url:
        print("Already up to date, ignoring")
        result_dict[app] = already_built_file[app]
        if previous_state != app_state:
            result_dict[app]["state"] = app_state
            print("... but has changed of state, updating it from '%s' to '%s'" % (previous_state, app_state))
        if previous_level != app_level or app_level is None:
            result_dict[app]["level"] = app_level
            print("... but has changed of level, updating it from '%s' to '%s'" % (previous_level, app_level))
        if previous_maintained != app_maintained:
            result_dict[app]["maintained"] = app_maintained
            print("... but maintained status changed, updating it from '%s' to '%s'" % (previous_maintained, app_maintained))
        if previous_featured != app_featured:
            result_dict[app]["featured"] = app_featured
            print("... but featured status changed, updating it from '%s' to '%s'" % (previous_featured, app_featured))
        if previous_high_quality != app_high_quality:
            result_dict[app]["high_quality"] = app_high_quality
            print("... but high_quality status changed, updating it from '%s' to '%s'" % (previous_high_quality, app_high_quality))

        print "update translations but don't download anything"
        result_dict[app]['manifest'] = include_translations_in_manifest(app, result_dict[app]['manifest'])

        continue

    print("Revision changed ! Updating...")

    # Hosted on GitHub
    if forge_type == "github":

        raw_url = 'https://raw.githubusercontent.com/%s/%s/%s/manifest.json' % (
            owner, repo, app_rev
        )

        manifest = get_json(raw_url)
        if manifest is None:
            continue

        api_url = 'https://api.github.com/repos/%s/%s/commits/%s' % (
            owner, repo, app_rev
        )

        info2 = get_json(api_url)
        if info2 is None:
            continue

        commit_date = parse(info2['commit']['author']['date'])
        timestamp = int(time.mktime(commit_date.timetuple()))

    # Gitlab-type forge
    elif forge_type == "gitlab":

        raw_url = '%s/raw/%s/manifest.json' % (app_url, app_rev)
        manifest = get_json(raw_url, verify=True)
        if manifest is None:
            continue

        api_url = 'https://%s/api/v4/projects/%s%%2F%s/repository/commits/%s' % (forge_site, owner, repo, app_rev)
        commit = get_json(api_url)
        if commit is None:
            continue

        commit_date = parse(commit["authored_date"])
        timestamp = int(time.mktime(commit_date.timetuple()))

    # Gogs-type forge
    elif forge_type == "gogs":
        if not app_url.endswith('.git'):
            app_url += ".git"

        raw_url = '%s/raw/%s/manifest.json' % (app_url[:-4], app_rev)
        manifest = get_json(raw_url, verify=False)
        if manifest is None:
            continue

        obj_url = '%s/objects/%s/%s' % (
            app_url, app_rev[0:2], app_rev[2:]
        )
        commit = get_zlib(obj_url, verify=False)

        if commit is None or len(commit) < 2:
            continue
        else:
            commit = commit[1]

        # Extract author line and commit date
        commit_author = re_commit_author.search(commit)
        if not commit_author:
            print("-> Error: author line in commit not found")
            continue

        # Construct UTC timestamp
        timestamp = int(commit_author.group('time'))
        tz = commit_author.group('tz')
        if len(tz) != 5:
            print("-> Error: unexpected timezone length in commit")
            continue
        elif tz != '+0000':
            tdelta = (int(tz[1:3]) * 3600) + (int(tz[3:5]) * 60)
            if tz[0] == '+':
                timestamp -= tdelta
            elif tz[0] == '-':
                timestamp += tdelta
            else:
                print("-> Error: unexpected timezone format in commit")
                continue
    else:
        print("-> Error: unsupported VCS and/or protocol")
        continue

    if manifest["id"] != app or manifest["id"] != repo.replace("_ynh", ""):
        print("Warning: IDs different between list.json, manifest and repo name")
        print(" Manifest id       : %s" % manifest["id"])
        print(" Name in json list : %s" % app)
        print(" Repo name         : %s" % repo.replace("_ynh", ""))

    try:
        result_dict[manifest['id']] = {
            'git': {
                'branch': info['branch'],
                'revision': app_rev,
                'url': app_url
            },
            'lastUpdate': timestamp,
            'manifest': include_translations_in_manifest(manifest['id'], manifest),
            'state': info['state'],
            'level': info.get('level', '?'),
            'maintained': app_maintained,
            'high_quality': app_high_quality,
            'featured': app_featured
        }
    except KeyError as e:
        print("-> Error: invalid app info or manifest, %s" % e)
        continue

# Write resulting file
with open(args.output, 'w') as f:
    f.write(json.dumps(result_dict, sort_keys=True))

print("\nDone! Written in %s" % args.output)
