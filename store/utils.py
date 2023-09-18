import base64
import os
import json
import toml
import subprocess
import pycmarkgfm
from emoji import emojize
from flask import request


AVAILABLE_LANGUAGES = ["en"] + os.listdir("translations")
def get_locale():
    # try to guess the language from the user accept
    # The best match wins.
    return request.accept_languages.best_match(AVAILABLE_LANGUAGES)

def get_catalog():

    path = "../builds/default/v3/apps.json"
    mtime = os.path.getmtime(path)
    if get_catalog.mtime_catalog != mtime:

        get_catalog.mtime_catalog = mtime

        catalog = json.load(open(path))
        catalog['categories'] = {c['id']:c for c in catalog['categories']}
        catalog['antifeatures'] = {c['id']:c for c in catalog['antifeatures']}

        category_color = {
            "synchronization": "sky",
            "publishing": "yellow",
            "communication": "amber",
            "office": "lime",
            "productivity_and_management": "purple",
            "small_utilities": "black",
            "reading": "emerald",
            "multimedia": "fuchsia",
            "social_media": "rose",
            "games": "violet",
            "dev": "stone",
            "system_tools": "black",
            "iot": "orange",
            "wat": "teal",
        }

        for id_, category in catalog['categories'].items():
            category["color"] = category_color[id_]

        get_catalog.cache_catalog = catalog

    return get_catalog.cache_catalog

get_catalog.mtime_catalog = None
get_catalog()


def get_wishlist():

    path = "../wishlist.toml"
    mtime = os.path.getmtime(path)
    if get_wishlist.mtime_wishlist != mtime:

        get_wishlist.mtime_wishlist = mtime
        get_wishlist.cache_wishlist = toml.load(open(path))

    return get_wishlist.cache_wishlist

get_wishlist.mtime_wishlist = None
get_wishlist()


def get_stars():

    checksum = subprocess.check_output("find . -type f -printf '%T@,' | md5sum", shell=True).decode().split()[0]
    if get_stars.cache_checksum != checksum:
        stars = {}
        for folder, _, files in os.walk(".stars/"):
            app_id = folder.split("/")[-1]
            if not app_id:
                continue
            stars[app_id] = set(files)
        get_stars.cache_stars = stars
        get_stars.cache_checksum = checksum

    return get_stars.cache_stars

get_stars.cache_checksum = None
get_stars()


def human_to_binary(size: str) -> int:
    symbols = ("K", "M", "G", "T", "P", "E", "Z", "Y")
    factor = {}
    for i, s in enumerate(symbols):
        factor[s] = 1 << (i + 1) * 10

    suffix = size[-1]
    size = size[:-1]

    if suffix not in symbols:
        raise Exception(
            f"Invalid size suffix '{suffix}', expected one of {symbols}"
        )

    try:
        size_ = float(size)
    except Exception:
        raise Exception(f"Failed to convert size {size} to float")

    return int(size_ * factor[suffix])


def get_app_md_and_screenshots(app_folder, infos):

    locale = get_locale()

    if locale != "en" and os.path.exists(os.path.join(app_folder, "doc", f"DESCRIPTION_{locale}.md")):
        description_path = os.path.join(app_folder, "doc", f"DESCRIPTION_{locale}.md")
    elif os.path.exists(os.path.join(app_folder, "doc", "DESCRIPTION.md")):
        description_path = os.path.join(app_folder, "doc", "DESCRIPTION.md")
    else:
        description_path = None
    if description_path:
        with open(description_path) as f:
            infos["full_description_html"] = emojize(pycmarkgfm.gfm_to_html(f.read()), language="alias")
    else:
        infos["full_description_html"] = infos['manifest']['description'][locale]

    if locale != "en" and os.path.exists(os.path.join(app_folder, "doc", f"PRE_INSTALL_{locale}.md")):
        pre_install_path = os.path.join(app_folder, "doc", f"PRE_INSTALL_{locale}.md")
    elif os.path.exists(os.path.join(app_folder, "doc", "PRE_INSTALL.md")):
        pre_install_path = os.path.join(app_folder, "doc", "PRE_INSTALL.md")
    else:
        pre_install_path = None
    if pre_install_path:
        with open(pre_install_path) as f:
            infos["pre_install_html"] = emojize(pycmarkgfm.gfm_to_html(f.read()), language="alias")

    infos["screenshot"] = None

    screenshots_folder = os.path.join(app_folder, "doc", "screenshots")

    if os.path.exists(screenshots_folder):
        with os.scandir(screenshots_folder) as it:
            for entry in it:
                ext = os.path.splitext(entry.name)[1].replace(".", "").lower()
                if entry.is_file() and ext in ("png", "jpg", "jpeg", "webp", "gif"):
                    with open(entry.path, "rb") as img_file:
                        data = base64.b64encode(img_file.read()).decode("utf-8")
                        infos[
                            "screenshot"
                        ] = f"data:image/{ext};charset=utf-8;base64,{data}"
                    break

    ram_build_requirement = infos["manifest"]["integration"]["ram"]["build"]
    infos["manifest"]["integration"]["ram"]["build_binary"] = human_to_binary(ram_build_requirement)
