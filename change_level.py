#!/usr/bin/env python

import os
import sys
import json


if __name__ == '__main__':
    if len(sys.argv[1:]) < 3:
        print "Usage: ./change_level.py <official.json|community.json> <app_id> <level>"
        sys.exit(1)

    app_list_name, app_id, level = sys.argv[1:4]

    if not os.path.exists(app_list_name):
        print "Error: the file '%s' doesn't exist" % app_list_name
        sys.exit(1)

    app_list = json.load(open(app_list_name))

    if app_id not in app_list:
        print "Error: app '%s' is not present in %s" % (app_id, app_list_name)
        sys.exit(1)

    if not level.isdigit():
        print "Error: app level must be a number, it's '%s'" % level
        sys.exit(1)

    if not 0 <= int(level) <= 10:
        print "Error: app level must be between 0 and 10, it's '%s'" % level
        sys.exit(1)

    app_list[app_id]["level"] = int(level)

    open(app_list_name, "w").write("\n".join(json.dumps(app_list, indent=4, sort_keys=True).split(" \n")) + "\n")
