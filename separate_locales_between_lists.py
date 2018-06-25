import os
import sys
import json

# TODO
# when an app is moved from one list to another find a way to migrate string?


if __name__ == '__main__':
    # en = json.load(open("locales/en.json", "r"))

    for apps_list in sys.argv[1:]:
        if not os.path.exists(apps_list):
            print "Error: file %s doesn't exists" % apps_list
            sys.exit(1)

        folder = "locales-%s" % (apps_list.split(".")[0])

        apps_list = json.load(open(apps_list, "r"))
        apps = tuple(apps_list.keys())

        if not os.path.exists(folder):
            os.mkdir(folder)

        for existing_translations in os.listdir("locales"):
            if not existing_translations.endswith(".json"):
                print "skip non json file %s", existing_translations
                continue

            language = existing_translations[:-len(".json")]
            existing_translations = json.load(open("locales/" + existing_translations, "r"))

            new_content = {}
            for key, value in existing_translations.items():
                if key.startswith(apps):
                    new_content[key] = value

            file_name = folder + "/" + language + ".json"
            print "writting %s..." % file_name
            open(file_name, "w").write(json.dumps(new_content, sort_keys=True, indent=4))
