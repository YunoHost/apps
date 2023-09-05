# YunoHost app store

This is a Flask app interfacing with YunoHost's app catalog for a cool browsing of YunoHost's apps catalog, wishlist and being able to vote/star for apps

## Developement

```
python3 -m venv venv
source venv/bin/activate
pip3 install -r requirements.txt
cp config.toml.example config.toml

# Tweak config.toml with appropriate values... (not everyting is needed for the base features to work)
nano config.toml

# You'll need to have a built version of the catalog
mkdir -p ../builds/default/v3/
curl https://app.yunohost.org/default/v3/apps.json > ../builds/default/v3/apps.json

# You will also want to run list_builder.py to initialize the .apps_cache (at least for a few apps, you can Ctrl+C after a while)
pushd ..
    python3 list_builder.py
popd
```

And then start the dev server:

```
source venv/bin/activate
FLASK_APP=app.py FLASK_ENV=development flask run
```

## Translation

It's based on Flask-Babel : https://python-babel.github.io/

```
source venv/bin/activate
pybabel extract --ignore-dirs venv -F babel.cfg -o messages.pot .

# If working on a new locale : initialize it (in this example: fr)
pybabel init -i messages.pot -d translations -l fr
# Otherwise, update the existing .po:
pybabel update -i messages.pot -d translations

# ... translate stuff in translations/<lang>/LC_MESSAGES/messages.po
# then compile:
pybabel compile -d translations
```
