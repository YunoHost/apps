import json
from argparse import ArgumentParser
import subprocess
import os
import shutil

def main(args):
    fileListName = args.list

    # Check if the list exsit
    if not os.path.isfile(fileListName):
        print("list {0} doesn't exist".format(fileListName))
        return 1

    # Get the list as json
    fileList = open(fileListName).read()
    jsonList = json.loads(fileList)

    # No prompt for git
    my_env = os.environ.copy()
    my_env["GIT_TERMINAL_PROMPT"] = "0"

    tempAppDir = "testedApp"

    for app in jsonList:
        url = jsonList[app]["url"]
        branch = jsonList[app]["branch"]
        revision = jsonList[app]["revision"]

        # Cloning the repo
        print('Cloning {0}'.format(app))
        try:
            subprocess.check_output(["git", "clone", "--single-branch", "--branch", branch, url, tempAppDir], env=my_env)
        except subprocess.CalledProcessError:
            # The repo doesn't exist, the test fail
            print('url {0} or branch {1} is not valid'.format(url, branch))
            return 1

        # HEAD always exist so remove tempAppDir and continue
        if revision != "HEAD":

            print("Check if revision {0} exist.".format(revision))
            cmd = "git log | grep {0}".format(revision)
            try:
                subprocess.check_output(cmd, shell=True, cwd=tempAppDir)
            except subprocess.CalledProcessError:
                print("revision {0} doesn't exist in this url {1}".format(revision, url))
                return 1

        print("pass")
        shutil.rmtree(tempAppDir)


if __name__ == '__main__':
    parser = ArgumentParser()
    parser.add_argument('--list', required=True, type=str)

    main(parser.parse_args())
