# Auto-README generation

Browses all repositories in YunoHost-Apps organization, and updates `updater.yml` with latest actions versions.

### Initial install

```
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

This script requires a `.github_token` file with a token with public.repo permission.

