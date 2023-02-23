# Auto-README generation

Browses all repositories in YunoHost-Apps organization, and updates `updater.yml` with latest actions versions.

### Initial install

```
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

This script requires the following files:
- `.github_token` containing a token with `public.repo` and `workflow` permission
- `.github_login` containing the author's username
- `.github_email` containing the author's email address
