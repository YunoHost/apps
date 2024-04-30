# YunoHost app generator

This is a Flask app generating a draft .zip of a YunoHost application after filling a form

## Developement

```bash
python3 -m venv venv
source venv/bin/activate
pip3 install -r requirements.txt

# you need to manually download the assets to have access to the css and the javascript files
(cd assets && bash fetch_assets)
```

And then start the dev server:

```bash
source venv/bin/activate
FLASK_APP=app.py FLASK_ENV=development flask --debug run
```

## Translation

It's based on Flask-Babel : <https://python-babel.github.io/flask-babel/>

```bash
source venv/bin/activate

# Extract the english sentences from the code, needed if you modified it
pybabel extract --ignore-dirs venv -F babel.cfg -o messages.pot .

# If working on a new locale: initialize it (in this example: fr)
pybabel init -i messages.pot -d translations -l fr
# Otherwise, update the existing .po:
pybabel update -i messages.pot -d translations

# ... translate stuff in translations/<lang>/LC_MESSAGES/messages.po
# re-run the 'update' command to let Babel properly format the text
# then compile:
pybabel compile -d translations
```
