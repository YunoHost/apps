import os
import sys
import json


if __name__ == '__main__':
    if os.path.exists("locales/en.json"):
        print "This script should be run only once, the first time to generate locales/, after that you should use update_translations.py"
        print "Abort"
        sys.exit(1)

    other_langs = {}

    keys = []

    en = {}

    for builded_file in sys.argv[1:]:
        builded_file = json.load(open(builded_file, "r"))

        for app, data in builded_file.items():
            if "en" in data["manifest"]["description"]:
                key = "%s_manifest_description" % app
                en[key] = data["manifest"]["description"]["en"]
                keys.append(key)

                for i in data["manifest"]["description"]:
                    if i not in other_langs:
                        other_langs[i] = {x: "" for x in keys}

                for i, translations in other_langs.items():
                    translations[key] = data["manifest"]["description"].get(i, "")

            for category, questions in data["manifest"]["arguments"].items():
                for question in questions:
                    if "en" not in question["ask"]:
                        continue

                    key = "%s_manifest_arguments_%s_%s" % (app, category, question["name"])
                    en[key] = question["ask"]["en"]

                    keys.append(key)

                    for i in question["ask"]:
                        if i not in other_langs:
                            other_langs[i] = {x: "" for x in keys}

                    for i, translations in other_langs.items():
                        translations[key] = question["ask"].get(i, "")

    if not os.path.exists("locales"):
        os.makedirs("locales")

    open("locales/en.json", "w").write(json.dumps(en, sort_keys=True, indent=4))

    for i, translations in other_langs.items():
        open("locales/%s.json" % i, "w").write(json.dumps(translations, sort_keys=True, indent=4))
