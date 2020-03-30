import sys
import json


if __name__ == '__main__':
    for builded_file in sys.argv[1:]:
        app_list = builded_file.split("-")[0]
        en = json.load(open("locales-%s/en.json" % app_list, "r"))

        builded_file = json.load(open(builded_file, "r"))

        for app, data in builded_file.items():
            if "en" in data["manifest"]["description"]:
                key = "%s_manifest_description" % app
                en[key] = data["manifest"]["description"]["en"]

            for category, questions in data["manifest"]["arguments"].items():
                for question in questions:
                    if "en" in question["ask"]:
                        key = "%s_manifest_arguments_%s_%s" % (app, category, question["name"])
                        en[key] = question["ask"]["en"]

                    if "en" in question.get("help", {}):
                        key = "%s_manifest_arguments_%s_help_%s" % (app, category, question["name"])
                        en[key] = question["help"]["en"]

        open("locales-%s/en.json" % app_list, "w").write(json.dumps(en, sort_keys=True, indent=4))
