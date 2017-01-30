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

"""GitHub repository URL."""
re_github_repo = re.compile(
    r'^(http[s]?|git)://github.com/(?P<owner>[\w\-_]+)/(?P<repo>[\w\-_]+)(.git)?'
)

re_commit_author = re.compile(
    r'^author (?P<name>.+) <(?P<email>.+)> (?P<time>\d+) (?P<tz>[+-]\d+)$',
    re.MULTILINE
)


# Helpers

def fail(msg, retcode=1):
    """Show failure message and exit."""
    print("Error: {0:s}".format(msg))
    sys.exit(retcode)


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
    print("Processing '%s'..." % app)

    # Store usefull values
    app_url = info['url']
    app_rev = info['revision']
    app_state = info["state"]
    app_level = info.get("level")

    previous_state = already_built_file.get(app, {}).get("state", {})

    manifest = {}
    timestamp = None

    previous_rev = already_built_file.get(app, {}).get("git", {}).get("revision", None)
    previous_url = already_built_file.get(app, {}).get("git", {}).get("url")
    previous_level = already_built_file.get(app, {}).get("level")

    if previous_rev == app_rev and previous_url == app_url:
        print("%s[%s] is already up to date in target output, ignore" % (app, app_rev))
        result_dict[app] = already_built_file[app]
        if previous_state != app_state:
            result_dict[app]["state"] = app_state
            print("... but has changed of state, updating it from '%s' to '%s'" % (previous_state, app_state))
        if previous_level != app_level or app_level is None:
            result_dict[app]["level"] = app_level
            print("... but has changed of level, updating it from '%s' to '%s'" % (previous_level, app_level))
        continue

    # Hosted on GitHub
    github_repo = re_github_repo.match(app_url)
    if github_repo:
        owner = github_repo.group('owner')
        repo = github_repo.group('repo')

        raw_url = 'https://raw.githubusercontent.com/%s/%s/%s/manifest.json' % (
            owner, repo, app_rev
        )
        try:
            # Retrieve and load manifest
            r = requests.get(raw_url, auth=token)
            r.raise_for_status()
            manifest = r.json()
        except requests.exceptions.RequestException as e:
            print("-> Error: unable to request %s, %s" % (raw_url, e))
            continue
        except ValueError as e:
            print("-> Error: unable to decode manifest.json, %s" % e)
            continue

        api_url = 'https://api.github.com/repos/%s/%s/commits/%s' % (
            owner, repo, app_rev
        )
        try:
            # Retrieve last commit information
            r = requests.get(api_url, auth=token)
            r.raise_for_status()
            info2 = r.json()
        except requests.exceptions.RequestException as e:
            print("-> Error: unable to request %s, %s" % (api_url, e))
            continue
        except ValueError as e:
            print("-> Error: unable to decode API response, %s" % e)
            continue
        else:
            commit_date = parse(info2['commit']['author']['date'])
            timestamp = int(time.mktime(commit_date.timetuple()))

    # Git repository with HTTP/HTTPS (Gogs, GitLab, ...)
    elif app_url.startswith('http') and app_url.endswith('.git'):
        raw_url = '%s/raw/%s/manifest.json' % (app_url[:-4], app_rev)
        try:
            # Attempt to retrieve and load raw manifest
            r = requests.get(raw_url, verify=False, auth=token)
            r.raise_for_status()
            manifest = r.json()
        except requests.exceptions.RequestException as e:
            print("-> Error: unable to request %s, %s" % (raw_url, e))
            continue
        except ValueError as e:
            print("-> Error: unable to decode manifest.json, %s" % e)
            continue

        obj_url = '%s/objects/%s/%s' % (
            app_url, app_rev[0:2], app_rev[2:]
        )
        try:
            # Retrieve last commit information
            r = requests.get(obj_url, verify=False)
            r.raise_for_status()
            commit = zlib.decompress(r.content).decode('utf-8').split('\x00')[1]
        except requests.exceptions.RequestException as e:
            print("-> Error: unable to request %s, %s" % (obj_url, e))
            continue
        except zlib.error as e:
            print("-> Error: unable to decompress commit object, %s" % e)
            continue
        else:
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

    try:
        result_dict[manifest['id']] = {
            'git': {
                'branch': info['branch'],
                'revision': app_rev,
                'url': app_url
            },
            'lastUpdate': timestamp,
            'manifest': manifest,
            'state': info['state'],
            'level': info.get('level', '?')
        }
    except KeyError as e:
        print("-> Error: invalid app info or manifest, %s" % e)
        continue

# Write resulting file
with open(args.output, 'w') as f:
    f.write(json.dumps(result_dict, sort_keys=True))

print("\nDone! Written in %s" % args.output)
