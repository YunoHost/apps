import time
import re
import toml
import base64
import hashlib
import hmac
import os
import string
import random
import urllib
import json
import sys
from slugify import slugify
from flask import (
    Flask,
    send_from_directory,
    render_template,
    session,
    redirect,
    request,
)
from flask_babel import Babel
from flask_babel import gettext as _
from github import Github, InputGitAuthor

sys.path = [os.path.dirname(__file__)] + sys.path

from utils import (
    get_locale,
    get_catalog,
    get_wishlist,
    get_stars,
    get_app_md_and_screenshots,
)

app = Flask(__name__, static_url_path="/assets", static_folder="assets")

try:
    config = toml.loads(open("config.toml").read())
except Exception as e:
    print(
        "You should create a config.toml with the appropriate key/values, cf config.toml.example"
    )
    sys.exit(1)

mandatory_config_keys = [
    "DISCOURSE_SSO_SECRET",
    "DISCOURSE_SSO_ENDPOINT",
    "COOKIE_SECRET",
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
    app.config["TEMPLATES_AUTO_RELOAD"] = True

# This is the secret key used for session signing
app.secret_key = config["COOKIE_SECRET"]

babel = Babel(app, locale_selector=get_locale)


@app.template_filter("localize")
def localize(d):
    if not isinstance(d, dict):
        return d
    else:
        locale = get_locale()
        if locale in d:
            return d[locale]
        else:
            return d["en"]


###############################################################################


@app.route("/favicon.ico")
def favicon():
    return send_from_directory("assets", "favicon.png")


@app.route("/")
def index():
    return render_template(
        "index.html",
        locale=get_locale(),
        user=session.get("user", {}),
        catalog=get_catalog(),
    )


@app.route("/catalog")
def browse_catalog():
    return render_template(
        "catalog.html",
        locale=get_locale(),
        init_sort=request.args.get("sort"),
        init_search=request.args.get("search"),
        init_category=request.args.get("category"),
        init_starsonly=request.args.get("starsonly"),
        user=session.get("user", {}),
        catalog=get_catalog(),
        timestamp_now=int(time.time()),
        stars=get_stars(),
    )


@app.route("/popularity.json")
def popularity_json():
    return {app: len(stars) for app, stars in get_stars().items()}


@app.route("/app/<app_id>")
def app_info(app_id):
    infos = get_catalog()["apps"].get(app_id)
    app_folder = os.path.join(config["APPS_CACHE"], app_id)
    if not infos or not os.path.exists(app_folder):
        return f"App {app_id} not found", 404

    get_app_md_and_screenshots(app_folder, infos)

    return render_template(
        "app.html",
        locale=get_locale(),
        user=session.get("user", {}),
        app_id=app_id,
        infos=infos,
        catalog=get_catalog(),
        stars=get_stars(),
    )


@app.route("/app/<app_id>/<action>")
def star_app(app_id, action):
    assert action in ["star", "unstar"]
    if app_id not in get_catalog()["apps"] and app_id not in get_wishlist():
        return _("App %(app_id) not found", app_id=app_id), 404
    if not session.get("user", {}):
        return _("You must be logged in to be able to star an app"), 401

    app_star_folder = os.path.join(".stars", app_id)
    app_star_for_this_user = os.path.join(
        ".stars", app_id, session.get("user", {})["id"]
    )

    if not os.path.exists(app_star_folder):
        os.mkdir(app_star_folder)

    if action == "star":
        open(app_star_for_this_user, "w").write("")
    elif action == "unstar":
        try:
            os.remove(app_star_for_this_user)
        except FileNotFoundError:
            pass

    if app_id in get_catalog()["apps"]:
        return redirect(f"/app/{app_id}")
    else:
        return redirect("/wishlist")


@app.route("/wishlist")
def browse_wishlist():
    return render_template(
        "wishlist.html",
        init_sort=request.args.get("sort"),
        init_search=request.args.get("search"),
        init_starsonly=request.args.get("starsonly"),
        locale=get_locale(),
        user=session.get("user", {}),
        wishlist=get_wishlist(),
        stars=get_stars(),
    )


@app.route("/wishlist/add", methods=["GET", "POST"])
def add_to_wishlist():
    if request.method == "POST":
        user = session.get("user", {})
        if not user:
            errormsg = _("You must be logged in to submit an app to the wishlist")
            return render_template(
                "wishlist_add.html",
                locale=get_locale(),
                user=session.get("user", {}),
                csrf_token=None,
                successmsg=None,
                errormsg=errormsg,
            )

        csrf_token = request.form["csrf_token"]

        if csrf_token != session.get("csrf_token"):
            errormsg = _("Invalid CSRF token, please refresh the form and try again")
            return render_template(
                "wishlist_add.html",
                locale=get_locale(),
                user=session.get("user", {}),
                csrf_token=csrf_token,
                successmsg=None,
                errormsg=errormsg,
            )

        name = request.form["name"].strip().replace("\n", "")
        description = request.form["description"].strip().replace("\n", "")
        upstream = request.form["upstream"].strip().replace("\n", "")
        website = request.form["website"].strip().replace("\n", "")

        checks = [
            (len(name) >= 3, _("App name should be at least 3 characters")),
            (len(name) <= 30, _("App name should be less than 30 characters")),
            (
                len(description) >= 5,
                _("App description should be at least 5 characters"),
            ),
            (
                len(description) <= 100,
                _("App description should be less than 100 characters"),
            ),
            (
                len(upstream) >= 10,
                _("Upstream code repo URL should be at least 10 characters"),
            ),
            (
                len(upstream) <= 150,
                _("Upstream code repo URL should be less than 150 characters"),
            ),
            (len(website) <= 150, _("Website URL should be less than 150 characters")),
            (
                re.match(r"^[\w\.\-\(\)\ ]+$", name),
                _("App name contains special characters"),
            ),
        ]

        for check, errormsg in checks:
            if not check:
                return render_template(
                    "wishlist_add.html",
                    locale=get_locale(),
                    user=session.get("user", {}),
                    csrf_token=csrf_token,
                    successmsg=None,
                    errormsg=errormsg,
                )

        slug = slugify(name)
        github = Github(config["GITHUB_TOKEN"])
        author = InputGitAuthor(config["GITHUB_LOGIN"], config["GITHUB_EMAIL"])
        repo = github.get_repo("Yunohost/apps")
        current_wishlist_rawtoml = repo.get_contents(
            "wishlist.toml", ref=repo.default_branch
        )
        current_wishlist_sha = current_wishlist_rawtoml.sha
        current_wishlist_rawtoml = current_wishlist_rawtoml.decoded_content.decode()
        new_wishlist = toml.loads(current_wishlist_rawtoml)

        if slug in new_wishlist:
            return render_template(
                "wishlist_add.html",
                locale=get_locale(),
                user=session.get("user", {}),
                csrf_token=csrf_token,
                successmsg=None,
                errormsg=_(
                    "An entry with the name %(slug) already exists in the wishlist",
                    slug=slug,
                ),
            )

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
            commit_sha = repo.get_branch(
                repo.default_branch
            ).commit.sha
            repo.create_git_ref(ref=f"refs/heads/{new_branch}", sha=commit_sha)
        except exception as e:
            print("... Failed to create branch ?")
            print(e)
            errormsg = _(
                "Failed to create the pull request to add the app to the wishlist ... please report the issue to the yunohost team"
            )
            return render_template(
                "wishlist_add.html",
                locale=get_locale(),
                user=session.get("user", {}),
                csrf_token=csrf_token,
                successmsg=None,
                errormsg=errormsg,
            )

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
            title=message,
            body=body,
            head=new_branch,
            base=repo.default_branch,
        )

        url = f"https://github.com/YunoHost/apps/pull/{pr.number}"

        successmsg = _(
            "Your proposed app has succesfully been submitted. It must now be validated by the YunoHost team. You can track progress here: %(url)s",
            url=url,
        )
        return render_template(
            "wishlist_add.html",
            locale=get_locale(),
            user=session.get("user", {}),
            successmsg=successmsg,
        )
    else:
        letters = string.ascii_lowercase + string.digits
        csrf_token = ''.join(random.choice(letters) for i in range(16))
        session["csrf_token"] = csrf_token
        return render_template(
            "wishlist_add.html",
            locale=get_locale(),
            user=session.get("user", {}),
            csrf_token=csrf_token,
            successmsg=None,
            errormsg=None,
        )


###############################################################################
#                        Session / SSO using Discourse                        #
###############################################################################


@app.route("/login_using_discourse")
def login_using_discourse():
    """
    Send auth request to Discourse:
    """

    (
        nonce,
        url,
        uri_to_redirect_to_after_login,
    ) = create_nonce_and_build_url_to_login_on_discourse_sso()

    session.clear()
    session["nonce"] = nonce
    if uri_to_redirect_to_after_login:
        session["uri_to_redirect_to_after_login"] = uri_to_redirect_to_after_login

    return redirect(url)


@app.route("/sso_login_callback")
def sso_login_callback():

    computed_sig = hmac.new(
        config["DISCOURSE_SSO_SECRET"].encode(),
        msg=request.args["sso"].encode(),
        digestmod=hashlib.sha256,
    ).hexdigest()

    if computed_sig != request.args["sig"]:
        return "Invalid signature from discourse!?", 401

    response = base64.b64decode(request.args["sso"].encode()).decode()

    user_data = urllib.parse.parse_qs(response)
    if user_data["nonce"][0] != session.get("nonce"):
        return "Invalid nonce", 401

    uri_to_redirect_to_after_login = session.get("uri_to_redirect_to_after_login")

    session.clear()
    session["user"] = {
        "id": user_data["external_id"][0],
        "username": user_data["username"][0],
        "avatar_url": user_data["avatar_url"][0] if "avatar_url" in user_data else "",
    }

    if uri_to_redirect_to_after_login:
        return redirect("/" + uri_to_redirect_to_after_login)
    else:
        return redirect("/")


@app.route("/logout")
def logout():
    session.clear()

    # Only use the current referer URI if it's on the same domain as the current route
    # to avoid XSS or whatever...
    referer = request.environ.get("HTTP_REFERER")
    if referer:
        if referer.startswith("http://"):
            referer = referer[len("http://") :]
        if referer.startswith("https://"):
            referer = referer[len("https://") :]
        if "/" not in referer:
            referer = referer + "/"

        domain, uri = referer.split("/", 1)
        if domain == request.environ.get("HTTP_HOST"):
            return redirect("/" + uri)

    return redirect("/")


def create_nonce_and_build_url_to_login_on_discourse_sso():
    """
    Redirect the user to DISCOURSE_ROOT_URL/session/sso_provider?sso=URL_ENCODED_PAYLOAD&sig=HEX_SIGNATURE
    """

    nonce = "".join([str(random.randint(0, 9)) for i in range(99)])

    # Only use the current referer URI if it's on the same domain as the current route
    # to avoid XSS or whatever...
    referer = request.environ.get("HTTP_REFERER")
    uri_to_redirect_to_after_login = None
    if referer:
        if referer.startswith("http://"):
            referer = referer[len("http://") :]
        if referer.startswith("https://"):
            referer = referer[len("https://") :]
        if "/" not in referer:
            referer = referer + "/"

        domain, uri = referer.split("/", 1)
        if domain == request.environ.get("HTTP_HOST"):
            uri_to_redirect_to_after_login = uri

    url_data = {
        "nonce": nonce,
        "return_sso_url": config["CALLBACK_URL_AFTER_LOGIN_ON_DISCOURSE"],
    }
    url_encoded = urllib.parse.urlencode(url_data)
    payload = base64.b64encode(url_encoded.encode()).decode()
    sig = hmac.new(
        config["DISCOURSE_SSO_SECRET"].encode(),
        msg=payload.encode(),
        digestmod=hashlib.sha256,
    ).hexdigest()
    data = {"sig": sig, "sso": payload}
    url = f"{config['DISCOURSE_SSO_ENDPOINT']}?{urllib.parse.urlencode(data)}"

    return nonce, url, uri_to_redirect_to_after_login
