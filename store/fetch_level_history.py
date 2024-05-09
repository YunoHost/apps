import toml
import json
import os
from datetime import datetime


def _time_points_until_today():

    year = 2017
    month = 1
    day = 1
    today = datetime.today()
    date = datetime(year, month, day)

    while date < today:
        yield date

        day += 14
        if day > 15:
            day = 1
            month += 1

        if month > 12:
            month = 1
            year += 1

        date = datetime(year, month, day)


time_points_until_today = list(_time_points_until_today())


def get_lists_history():

    os.system("rm -rf ./.tmp")
    os.system("git clone https://github.com/YunoHost/apps ./.tmp/apps")

    for t in time_points_until_today:
        print(t.strftime("%b %d %Y"))

        # Fetch repo at this date
        cmd = 'cd ./.tmp/apps; git checkout `git rev-list -1 --before="%s" master`'
        os.system(cmd % t.strftime("%b %d %Y"))

        if t < datetime(2019, 4, 4):
            # Merge community and official
            community = json.loads(open("./.tmp/apps/community.json").read())
            official = json.loads(open("./.tmp/apps/official.json").read())
            for key in official:
                official[key]["state"] = "official"
            merged = {}
            merged.update(community)
            merged.update(official)
        else:
            try:
                merged = toml.loads(open("./.tmp/apps/apps.toml").read())
            except Exception:
                try:
                    merged = json.loads(open("./.tmp/apps/apps.json").read())
                except Exception:
                    pass

        # Save it
        json.dump(
            merged, open("./.tmp/merged_lists.json.%s" % t.strftime("%y-%m-%d"), "w")
        )


def make_count_summary():

    history = []

    last_time_point = time_points_until_today[-1]
    json_at_last_time_point = json.loads(
        open(
            "./.tmp/merged_lists.json.%s" % last_time_point.strftime("%y-%m-%d")
        ).read()
    )
    relevant_apps_to_track = [
        app
        for app, infos in json_at_last_time_point.items()
        if infos.get("state") in ["working", "official"]
    ]

    for d in time_points_until_today:

        print("Analyzing %s ..." % d.strftime("%y-%m-%d"))

        # Load corresponding json
        j = json.loads(
            open("./.tmp/merged_lists.json.%s" % d.strftime("%y-%m-%d")).read()
        )
        d_label = d.strftime("%b %d %Y")

        summary = {}
        summary["date"] = d_label
        for level in range(0, 10):
            summary["level-%s" % level] = len(
                [
                    k
                    for k, infos in j.items()
                    if infos.get("state") in ["working", "official"]
                    and infos.get("level", None) == level
                ]
            )

        history.append(summary)

        for app in relevant_apps_to_track:

            infos = j.get(app, {})

            if not infos or infos.get("state") not in ["working", "official"]:
                level = -1
            else:
                level = infos.get("level", -1)
                try:
                    level = int(level)
                except Exception:
                    level = -1

    json.dump(history, open(".cache/history.json", "w"))


def make_news():

    news_per_date = {
        d.strftime("%b %d %Y"): {
            "broke": [],
            "repaired": [],
            "removed": [],
            "added": [],
        }
        for d in time_points_until_today
    }
    previous_j = {}

    def level(infos):
        lev = infos.get("level")
        if lev is None or (isinstance(lev, str) and not lev.isdigit()):
            return -1
        else:
            return int(lev)

    for d in time_points_until_today:
        d_label = d.strftime("%b %d %Y")

        print("Analyzing %s ..." % d.strftime("%y-%m-%d"))

        # Load corresponding json
        j = json.loads(
            open("./.tmp/merged_lists.json.%s" % d.strftime("%y-%m-%d")).read()
        )

        apps_current = set(
            k
            for k, infos in j.items()
            if infos.get("state") in ["working", "official"] and level(infos) != -1
        )
        apps_current_good = set(
            k for k, infos in j.items() if k in apps_current and level(infos) > 4
        )
        apps_current_broken = set(
            k for k, infos in j.items() if k in apps_current and level(infos) <= 4
        )

        apps_previous = set(
            k
            for k, infos in previous_j.items()
            if infos.get("state") in ["working", "official"] and level(infos) != -1
        )
        apps_previous_good = set(
            k
            for k, infos in previous_j.items()
            if k in apps_previous and level(infos) > 4
        )
        apps_previous_broken = set(
            k
            for k, infos in previous_j.items()
            if k in apps_previous and level(infos) <= 4
        )

        news = news_per_date[d_label]
        for app in set(apps_previous_good & apps_current_broken):
            news["broke"].append((app, j[app]["url"]))
        for app in set(apps_previous_broken & apps_current_good):
            news["repaired"].append((app, j[app]["url"]))
        for app in set(apps_current - apps_previous):
            news["added"].append((app, j[app]["url"]))
        for app in set(apps_previous - apps_current):
            news["removed"].append((app, previous_j[app]["url"]))

        previous_j = j

    json.dump(news_per_date, open(".cache/news.json", "w"))


get_lists_history()
make_count_summary()
make_news()
