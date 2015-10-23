#!/usr/bin/env python2
import sys
import os
import argparse
import time
import json
import requests
import datetime
from dateutil.parser import parse

# Create argument parser
parser = argparse.ArgumentParser(description='Process YunoHost application list.')

# Add arguments and options
parser.add_argument("input", help="Path to json input file")
parser.add_argument("-o", "--output", help="Path to result file. If not specified, '-build' suffix will be added to input filename.")
parser.add_argument("-g", "--github", help="Github token <username>:<password>")

# Parse args
args = parser.parse_args()

# Open list json file
try:
    apps_list = json.load(open(args.input))
except IOError as e:
    print "Error: %s file not found" % args.input
    sys.exit(1)

# Get list name from filename
list_name = os.path.splitext(os.path.basename(args.input))[0]
print 'Building %s list' % list_name
print

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
    print 'Processing %s ' % app
    owner, repo = filter(None, info['url'].split("/"))[-2:]

    try:
        res = requests.get('https://raw.githubusercontent.com/%s/%s/%s/manifest.json' % (owner, repo, info['revision']), auth=token)
    except:
        print 'Fail: ', info['url']
        continue
    if res.status_code != 200:
        print '%s returned an error %d' % (info['url'], res.status_code)
        continue

    # Load manifest
    manifest = json.loads(res.text)

    try:
        res = requests.get('https://api.github.com/repos/%s/%s/commits/%s' % (owner, repo, info['revision']), auth=token)
        info2 = json.loads(res.text)
        date = info2['commit']['author']['date']
        parsed_date = parse(date)
        timestamp = int(time.mktime(parsed_date.timetuple()))
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
    except KeyboardInterrupt:
         sys.exit(1)
    except Exception as e:
        print 'Fail: ', manifest['id']
        print e
        continue

# Write resulting file
with open(args.output , 'w') as f:
    f.write(json.dumps(result_dict, sort_keys=True))
    print 'Done!'
    print
    print 'Written in %s' % args.output
