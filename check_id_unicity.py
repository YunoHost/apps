import sys
import json
import requests


def get_json(url, verify=True, token=None):
    """
    Make a get request

    Args:
        url: (str): write your description
        verify: (bool): write your description
        token: (str): write your description
    """

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
        print("-> Error: unable to decode JSON from %s : %s" % (url, e))
        return None


def main(apps):
    """
    Main entry point.

    Args:
        apps: (dict): write your description
    """
    for app_id, app_data in apps.items():
        url = app_data["url"]
        github_repo_name = url.split("/")[-1].replace("_ynh", "")

        if app_id != github_repo_name:
            print "[%s] GitHub repo name is not coherent with app id: '%s' vs '%s' (%s)" % (app_id, app_id, url.split("/")[-1], url)

        owner, repo_name = url.split("/")[-2:]

        raw_url = "https://raw.githubusercontent.com/%s/%s/%s/manifest.json" % (
            owner, repo_name, app_data["revision"]
        )

        manifest = get_json(raw_url)

        if manifest is None:
            continue

        manifest_id = manifest["id"]
        if app_id != manifest_id:
            print "[%s] manifest id is different from app id: '%s' vs '%s' (manifest_id" % (app_id, app_id, manifest_id)

        if manifest_id != github_repo_name:
            print "[%s] manifest id is different from GitHub repo name: '%s' vs '%s' (%s)" % (app_id, manifest_id, url.split("/")[-1], url)


if __name__ == '__main__':
    if not sys.argv[1:]:
        print "Usage: python check_id_unicity.py list.json"
        sys.exit(1)

    main(json.load(open(sys.argv[1])))
