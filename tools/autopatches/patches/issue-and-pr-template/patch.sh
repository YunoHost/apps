
[ ! -e issue_template.md ] || git rm issue_template.md
[ ! -e pull_request_template.md ] || git rm pull_request_template.md

[ ! -e .github ] || git rm -rf .github
mkdir -p .github

# Sleep 1 to avoid too many requests on github (there's a rate limit anyway)
sleep 1

wget -O .github/ISSUE_TEMPLATE.md https://raw.githubusercontent.com/YunoHost/example_ynh/master/.github/ISSUE_TEMPLATE.md
wget -O .github/PULL_REQUEST_TEMPLATE.md https://raw.githubusercontent.com/YunoHost/example_ynh/master/.github/PULL_REQUEST_TEMPLATE.md

git add .github
