# Auto-README generation

## Initial install

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Use on a single app

```bash
source venv/bin/activate
./make_readme.py /path/to/app
```

Then the README.md in the app folder will be updated

## Run tests

```bash
source venv/bin/activate
pip install pytest
pytest tests
```

## Launch webhook service for auto update

Configure the webhook on github

Also need to allow the bot to push on all repos

Configure nginx to reverse proxy on port 8123 (or whichever port you set in the systemd config)

```bash
echo "github_webhook_secret" > github_webhook_secret
echo "the_bot_login" > login
echo "the_bot_token" > token
```

Add the webhook.service to systemd config, then start it:

```bash
systemctl start the_webhook_service 
```

## Translation

It's based on Babel integrated into jinja2 : <https://babel.pocoo.org/en/latest/>

```bash
source venv/bin/activate

# Extract the english sentences from the code, needed if you modified it
pybabel extract --ignore-dirs venv -F babel.cfg -o messages.pot .

# If working on a new locale: initialize it: (in this example: fr)
pybabel init -i messages.pot -d translations -l fr
# Otherwise, update the existing .po:
pybabel update -i messages.pot -d translations
# To update only a specific language: (in this example: fr)
pybabel update -i messages.pot -d translations -l fr

# ... translate stuff in translations/<lang>/LC_MESSAGES/messages.po
# re-run the 'update' command to let Babel properly format the text
# then compile:
pybabel compile -d translations
```
