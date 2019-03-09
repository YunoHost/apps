# Validation template for High Quality tag request

This template is designed to be used as it is by Apps group to validate requests from packagers for the tag High Quality.

Mandatory check boxes:
- [ ] The package is level 7.
- [ ] The package has been level 7 for at least 2 months.
- [ ] The package is in the list since at least 2 months.
- [ ] The package is up to date regarding the packaging recommendations and helpers.
- [ ] The repository has a testing branch.
- [ ] All commits are made in testing branch before being merged into master.
- [ ] The list point to HEAD, not a specific commit.
- [ ] The repository has a [`pull_request_template.md`](https://github.com/YunoHost/apps/blob/master/pull_request_template-HQ-apps.md)
- [ ] The package shows the YunoHost tile `yunohost_panel.conf.inc`

Optional check boxes:
- [ ] The package is level 7 for ARM as well.
*If the app is really important for the community, we can accept it with a broken ARM support. But this should be clearly explained and managed.*
- [ ] The app is up to date with the upstream version.  
*If this is possible with the last YunoHost version.*
- [ ] The package supports LDAP  
*If the app upstream supports it*
- [ ] The package supports HTTP authentication  
*If the app upstream supports it*
