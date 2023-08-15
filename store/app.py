from flask import Flask, send_from_directory, render_template, session, redirect, request
import base64
import hashlib
import hmac
import os
import random
import urllib
import json
from settings import DISCOURSE_SSO_SECRET, DISCOURSE_SSO_ENDPOINT, CALLBACK_URL_AFTER_LOGIN_ON_DISCOURSE
app = Flask(__name__)

app.debug = True
app.config["DEBUG"] = True
app.config['TEMPLATES_AUTO_RELOAD'] = True

catalog = json.load(open("apps.json"))
catalog['categories'] = {c['id']:c for c in catalog['categories']}

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

wishlist = json.load(open("wishlist.json"))

# This is the secret key used for session signing
app.secret_key = ''.join([str(random.randint(0, 9)) for i in range(99)])


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
def browse_catalog(category_filter=None):
    return render_template("catalog.html", user=session.get('user', {}), catalog=catalog)


@app.route('/app/<app_id>')
def app_info(app_id):
    infos = catalog["apps"].get(app_id)
    if not infos:
        return f"App {app_id} not found", 404
    return render_template("app.html", user=session.get('user', {}), app_id=app_id, infos=infos)


@app.route('/wishlist')
def browse_wishlist():
    return render_template("wishlist.html", user=session.get('user', {}), wishlist=wishlist)



################################################

def create_nonce_and_build_url_to_login_on_discourse_sso():
    """
    Redirect the user to DISCOURSE_ROOT_URL/session/sso_provider?sso=URL_ENCODED_PAYLOAD&sig=HEX_SIGNATURE
    """

    nonce = ''.join([str(random.randint(0, 9)) for i in range(99)])

    url_data = {"nonce": nonce, "return_sso_url": CALLBACK_URL_AFTER_LOGIN_ON_DISCOURSE}
    url_encoded = urllib.parse.urlencode(url_data)
    payload = base64.b64encode(url_encoded.encode()).decode()
    sig = hmac.new(DISCOURSE_SSO_SECRET.encode(), msg=payload.encode(), digestmod=hashlib.sha256).hexdigest()
    data = {"sig": sig, "sso": payload}
    url = f"{DISCOURSE_SSO_ENDPOINT}?{urllib.parse.urlencode(data)}"

    return nonce, url
