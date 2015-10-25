#!/usr/bin/env python2
import re
import os
import sys
import time
import json
import argparse

import requests
from dateutil.parser import parse


## Regular expression patterns

"""GitHub repository URL."""
re_github_repo = re.compile(r'^(http[s]?|git)://github.com/(?P<owner>[\w\-_]+)/(?P<repo>[\w\-_]+)(.git)?')


## Helpers

def fail(msg, retcode=1):
    """Show failure message and exit."""
    print("Error: {0:s}".format(msg))
    sys.exit(retcode)


## Main

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

# GitHub credentials
if args.github:
    token = (args.github.split(':')[0], args.github.split(':')[1])
else:
    token = None

# Loop through every apps
result_dict = {}
for app, info in apps_list.items():
    print("Processing '%s'..." % app)

    manifest = {}
    timestamp = None

    ## Hosted on GitHub
    github_repo = re_github_repo.match(info['url'])
    if github_repo:
        owner = github_repo.group('owner')
        repo = github_repo.group('repo')

        raw_url = 'https://raw.githubusercontent.com/%s/%s/%s/manifest.json' % (
                owner, repo, info['revision']
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
                owner, repo, info['revision']
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
    else:
        print("-> Error: unsupported VCS")
        continue

    try:
        result_dict[manifest['id']] = {
            'git': {
                'branch': info['branch'],
                'revision': info['revision'],
                'url': info['url']
            },
            'lastUpdate': timestamp,
            'manifest': manifest,
            'state': info['state']
        }
    except KeyError as e:
        print("-> Error: invalid app info or manifest, %s" % e)
        continue

# Write resulting file
with open(args.output , 'w') as f:
    f.write(json.dumps(result_dict, sort_keys=True))

print("\nDone! Written in %s" % args.output)
