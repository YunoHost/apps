import pycmarkgfm
import time
import re
import toml
import base64
import hashlib
import hmac
import os
import random
import urllib
import json
import sys
from slugify import slugify
from flask import Flask, send_from_directory, render_template, session, redirect, request
from github import Github, InputGitAuthor

locale = "en"
app = Flask(__name__, static_url_path='/assets', static_folder="assets")
catalog = json.load(open("../builds/default/v3/apps.json"))
catalog['categories'] = {c['id']:c for c in catalog['categories']}

try:
    config = toml.loads(open("config.toml").read())
except Exception as e:
    print("You should create a config.toml with the appropriate key/values, cf config.toml.example")
    sys.exit(1)

mandatory_config_keys = [
    "DISCOURSE_SSO_SECRET",
    "DISCOURSE_SSO_ENDPOINT",
    "CALLBACK_URL_AFTER_LOGIN_ON_DISCOURSE",
    "GITHUB_LOGIN",
    "GITHUB_TOKEN",
    "GITHUB_EMAIL",
    "APPS_CACHE",
]

for key in mandatory_config_keys:
    if key not in config:
        print(f"Missing key in config.toml: {key}")
        sys.exit(1)

if config.get("DEBUG"):
    app.debug = True
    app.config["DEBUG"] = True
    app.config['TEMPLATES_AUTO_RELOAD'] = True

category_color = {
    "synchronization": "sky",
    "publishing": "yellow",
    "communication": "amber",
    "office": "lime",
    "productivity_and_management": "purple",
    "small_utilities": "",
    "reading": "emerald",
    "multimedia": "fuchsia",
    "social_media": "rose",
    "games": "violet",
    "dev": "stone",
    "system_tools": "white",
    "iot": "orange",
    "wat": "teal",
}

for id_, category in catalog['categories'].items():
    category["color"] = category_color[id_]

wishlist = toml.load(open("../wishlist.toml"))

# This is the secret key used for session signing
app.secret_key = ''.join([str(random.randint(0, 9)) for i in range(99)])


@app.route('/favicon.ico')
def favicon():
    return send_from_directory('assets', 'favicon.png')


@app.route('/login_using_discourse')
def login_using_discourse():
    """
    Send auth request to Discourse:
    """

    nonce, url = create_nonce_and_build_url_to_login_on_discourse_sso()

    session.clear()
    session["nonce"] = nonce

    return redirect(url)


@app.route('/sso_login_callback')
def sso_login_callback():
    response = base64.b64decode(request.args['sso'].encode()).decode()
    user_data = urllib.parse.parse_qs(response)
    if user_data['nonce'][0] != session.get("nonce"):
        return "Invalid nonce", 401
    else:
        session.clear()
        session['user'] = {
            "id": user_data["external_id"][0],
            "username": user_data["username"][0],
            "avatar_url": user_data["avatar_url"][0],
        }
        return redirect("/")


@app.route('/logout')
def logout():
    session.clear()
    return redirect("/")


@app.route('/')
def index():
    return render_template("index.html", user=session.get('user', {}), catalog=catalog)


@app.route('/catalog')
def browse_catalog():
    return render_template("catalog.html", init_search=request.args.get("search"), init_category=request.args.get("category"), user=session.get('user', {}), catalog=catalog, timestamp_now=int(time.time()))


@app.route('/app/<app_id>')
def app_info(app_id):
    infos = catalog["apps"].get(app_id)
    app_folder = os.path.join(config["APPS_CACHE"], app_id)
    if not infos or not os.path.exists(app_folder):
        return f"App {app_id} not found", 404

    if os.path.exists(os.path.join(app_folder, "doc", f"DESCRIPTION_{locale}.md")):
        description_path = os.path.join(app_folder, "doc", f"DESCRIPTION_{locale}.md")
    elif os.path.exists(os.path.join(app_folder, "doc", "DESCRIPTION.md")):
        description_path = os.path.join(app_folder, "doc", "DESCRIPTION.md")
    else:
        description_path = None
    if description_path:
        with open(description_path) as f:
            infos["full_description_html"] = pycmarkgfm.gfm_to_html(f.read())
    else:
        infos["full_description_html"] = infos['manifest']['description'][locale]

    if os.path.exists(os.path.join(app_folder, "doc", f"PRE_INSTALL_{locale}.md")):
        pre_install_path = os.path.join(app_folder, "doc", f"PRE_INSTALL_{locale}.md")
    elif os.path.exists(os.path.join(app_folder, "doc", "PRE_INSTALL.md")):
        pre_install_path = os.path.join(app_folder, "doc", "PRE_INSTALL.md")
    else:
        pre_install_path = None
    if pre_install_path:
        with open(pre_install_path) as f:
            infos["pre_install_html"] = pycmarkgfm.gfm_to_html(f.read())

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

    return render_template("app.html", user=session.get('user', {}), app_id=app_id, infos=infos)


@app.route('/wishlist')
def browse_wishlist():
    return render_template("wishlist.html", user=session.get('user', {}), wishlist=wishlist)


@app.route('/wishlist/add', methods=['GET', 'POST'])
def add_to_wishlist():
    if request.method == "POST":

        user = session.get('user', {})
        if not user:
            errormsg = "You must be logged in to submit an app to the wishlist"
            return render_template("wishlist_add.html", user=session.get('user', {}), successmsg=None, errormsg=errormsg)

        name = request.form['name'].strip().replace("\n", "")
        description = request.form['description'].strip().replace("\n", "")
        upstream = request.form['upstream'].strip().replace("\n", "")
        website = request.form['website'].strip().replace("\n", "")

        checks = [
            (len(name) >= 3, "App name should be at least 3 characters"),
            (len(name) <= 30, "App name should be less than 30 characters"),
            (len(description) >= 5, "App name should be at least 5 characters"),
            (len(description) <= 100, "App name should be less than 100 characters"),
            (len(upstream) >= 10, "Upstream code repo URL should be at least 10 characters"),
            (len(upstream) <= 150, "Upstream code repo URL should be less than 150 characters"),
            (len(website) <= 150, "Website URL should be less than 150 characters"),
            (re.match(r"^[\w\.\-\(\)\ ]+$", name), "App name contains special characters"),
        ]

        for check, errormsg in checks:
            if not check:
                return render_template("wishlist_add.html", user=session.get('user', {}), successmsg=None, errormsg=errormsg)

        slug = slugify(name)
        github = Github(config["GITHUB_TOKEN"])
        author = InputGitAuthor(config["GITHUB_LOGIN"], config["GITHUB_EMAIL"])
        repo = github.get_repo("Yunohost/apps")
        current_wishlist_rawtoml = repo.get_contents("wishlist.toml", ref="app-store") # FIXME : ref=repo.default_branch)
        current_wishlist_sha = current_wishlist_rawtoml.sha
        current_wishlist_rawtoml = current_wishlist_rawtoml.decoded_content.decode()
        new_wishlist = toml.loads(current_wishlist_rawtoml)

        if slug in new_wishlist:
            return render_template("wishlist_add.html", user=session.get('user', {}), successmsg=None, errormsg=f"An entry with the name {slug} already exists in the wishlist")

        new_wishlist[slug] = {
            "name": name,
            "description": description,
            "upstream": upstream,
            "website": website,
        }

        new_wishlist = dict(sorted(new_wishlist.items()))
        new_wishlist_rawtoml = toml.dumps(new_wishlist)
        new_branch = f"add-to-wishlist-{slug}"
        try:
            # Get the commit base for the new branch, and create it
            commit_sha = repo.get_branch("app-store").commit.sha # FIXME app-store -> repo.default_branch
            repo.create_git_ref(ref=f"refs/heads/{new_branch}", sha=commit_sha)
        except exception as e:
            print("... Failed to create branch ?")
            print(e)
            errormsg = "Failed to create the pull request to add the app to the wishlist ... please report the issue to the yunohost team"
            return render_template("wishlist_add.html", user=session.get('user', {}), successmsg=None, errormsg=errormsg)

        message = f"Add {name} to wishlist"
        repo.update_file(
            "wishlist.toml",
            message=message,
            content=new_wishlist_rawtoml,
            sha=current_wishlist_sha,
            branch=new_branch,
            author=author,
        )

        # Wait a bit to preserve the API rate limit
        time.sleep(1.5)

        body = f"""
### Add {name} to wishlist

Proposed by **{session['user']['username']}**

- [ ] Confirm app is self-hostable and generally makes sense to possibly integrate in YunoHost
- [ ] Confirm app's license is opensource/free software (or not-totally-free, case by case TBD)
- [ ] Description describes concisely what the app is/does
        """

        # Open the PR
        pr = repo.create_pull(
            title=message, body=body, head=new_branch, base="app-store"  # FIXME app-store -> repo.default_branch
        )

        successmsg = f"Your proposed app has succesfully been submitted. It must now be validated by the YunoHost team. You can track progress here: https://github.com/YunoHost/apps/pull/{pr.number}"
        return render_template("wishlist_add.html", user=session.get('user', {}), successmsg=successmsg)
    else:
        return render_template("wishlist_add.html", user=session.get('user', {}), successmsg=None, errormsg=None)


################################################

def create_nonce_and_build_url_to_login_on_discourse_sso():
    """
    Redirect the user to DISCOURSE_ROOT_URL/session/sso_provider?sso=URL_ENCODED_PAYLOAD&sig=HEX_SIGNATURE
    """

    nonce = ''.join([str(random.randint(0, 9)) for i in range(99)])

    url_data = {"nonce": nonce, "return_sso_url": config["CALLBACK_URL_AFTER_LOGIN_ON_DISCOURSE"]}
    url_encoded = urllib.parse.urlencode(url_data)
    payload = base64.b64encode(url_encoded.encode()).decode()
    sig = hmac.new(config["DISCOURSE_SSO_SECRET"].encode(), msg=payload.encode(), digestmod=hashlib.sha256).hexdigest()
    data = {"sig": sig, "sso": payload}
    url = f"{config['DISCOURSE_SSO_ENDPOINT']}?{urllib.parse.urlencode(data)}"

    return nonce, url
