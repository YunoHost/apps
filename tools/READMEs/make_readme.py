from jinja2 import Environment, FileSystemLoader
import json
import os
import sys

if len(sys.argv) <= 1:
    raise Exception("You should provide the path to the app as first arg")

app = sys.argv[1]

if not os.path.exists(app):
    raise Exception("App path provided doesn't exists ?!")

env = Environment(loader=FileSystemLoader('./templates'))

for lang, lang_suffix in [("en", ""), ("fr", "_fr")]:

    template = env.get_template(f'README{lang_suffix}.md.j2')

    manifest = json.load(open(os.path.join(app, "manifest.json")))
    upstream = manifest.get("upstream", {})

    if os.path.exists(os.path.join(app, "doc", "screenshots")):
        screenshots = os.listdir(os.path.join(app, "doc", "screenshots"))
        if ".gitkeep" in screenshots:
            screenshots.remove(".gitkeep")
    else:
        screenshots = []

    if os.path.exists(os.path.join(app, "doc", f"DISCLAIMER{lang_suffix}.md")):
        disclaimer = open(os.path.join(app, "doc", f"DISCLAIMER{lang_suffix}.md")).read()
    # Fallback to english if maintainer too lazy to translate the disclaimer idk
    elif os.path.exists(os.path.join(app, "doc", f"DISCLAIMER.md")):
        disclaimer = open(os.path.join(app, "doc", f"DISCLAIMER.md")).read()
    else:
        disclaimer = None

    out = template.render(lang=lang, upstream=upstream, screenshots=screenshots, disclaimer=disclaimer, manifest=manifest)
    with open(os.path.join(app, f"README{lang_suffix}.md"), "w") as f:
        f.write(out)
