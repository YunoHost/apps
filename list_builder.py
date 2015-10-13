#!/usr/bin/env python2
import sys
import time
import json
import requests
import datetime
from dateutil.parser import parse

try:
    json_list = sys.argv[1]
    token = (sys.argv[2], sys.argv[3])
except IndexError:
    print 'Usage: %s <community|official> <github_username> <github_token>' % sys.argv[0]
    print
    print 'Build a YunoHost app list from a simplfied list, output results in <community|official>.new.json'
    sys.exit(1)

json_text = requests.get('https://raw.githubusercontent.com/YunoHost/apps/master/%s.json' % (json_list), auth=token).text
imported_json = json.loads(json_text)

result_dict = {}

for app, info in imported_json.items():
    owner, repo = filter(None, info['url'].split("/"))[-2:]
    try:
        res = requests.get('https://raw.githubusercontent.com/%s/%s/%s/manifest.json' % (owner, repo, info['revision']), auth=token)
    except:
        print 'Fail: ', info['url']
        continue
    if res.status_code != 200:
        print '%s returned an error %d' % (info['url'], res.status_code)
        continue

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
    print manifest['id']


with open('%s.new.json' % json_list, 'w') as f:
    f.write(json.dumps(result_dict, sort_keys=True))
    print 'Done!'
    print
    print 'Written in %s.new.json' % json_list
