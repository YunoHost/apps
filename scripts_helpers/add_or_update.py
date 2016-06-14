#!/usr/bin/env python2

import os
import sys
import json

from urllib2 import urlopen

states = {
    1: "notworking",
    2: "inprogress",
    3: "working",
}

if __name__ == '__main__':
    if not len(sys.argv[1:]):
        print("I need a json file as first argument and a list of github urls")
        sys.exit(0)

    if len(sys.argv[1:]) < 2:
        print("I need a list of github urls after the json file")
        sys.exit(0)

    if not os.path.exists(sys.argv[1]):
        print("The json file '%s' doesn't exist" % sys.argv[1])

    content = json.load(open(sys.argv[1], "r"))

    for url in sys.argv[2:]:
        if url.endswith("/"):
            url = url[:-1]

        if url.endswith(".git"):
            url = url[:-len(".git")]

        if not url.startswith("https://github.com"):
            sys.stderr.write("WARNING: url '%s' doesn't starts with https://github.com, skip it\n" % url)

        owner, repo = filter(None, url.split("/"))[-2:]
        project_name = filter(None, url.split("/"))[-1].replace("_ynh", "")

        github_data = json.load(urlopen("https://api.github.com/repos/%(owner)s/%(repo)s/commits" % {"owner": owner, "repo": repo}))

        if project_name not in content:
            content[project_name] = {}
        else:
            print("INFO: project already in '%s', I'm updating it" % sys.argv[1])

        content[project_name]["url"] = url
        content[project_name]["revision"] = github_data[0]["sha"]
        content[project_name]["branch"] = "master"

        if sys.argv[1] == "official.json":
            content[project_name]["state"] = "validated"

        else:
            got_state = False
            while not got_state:
                answer = input("Give me a state for this repository (digit or name) in:\n%s\n\nState: " % "\n".join(["%s: %s" % x for x in sorted(states.items(), key=lambda x: x[0])]) + "\n")

                if answer in states:
                    answer = states[answer]
                    got_state = True
                elif answer in states.values():
                    got_state = True
                else:
                    print("Invalid state.\n")

            content[project_name]["state"] = answer

    open(sys.argv[1], "w").write("\n".join(json.dumps(content, indent=4, sort_keys=True).split(" \n")) + "\n")
    os.system("git diff")
