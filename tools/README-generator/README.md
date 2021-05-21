# Auto-README generation

### Initial install

```
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Use on a single app

```
source venv/bin/activate
./make_readme.py /path/to/app
```

Then the README.md in the app folder will be updated

### Launch webhook service for auto update

Configure the webhook on github

Also need to allow the bot to push on all repos

Configure nginx to reverse proxy on port 80123 (or whichever port you set in the systemd config)

```bash
echo "github_webhook_secret" > github_webhook_secret
echo "the_bot_login" > login
echo "the_bot_token" > token
```

Add the webhook.service to systemd config, then start it:

```bash
systemctl start the_webhook_service 
```
