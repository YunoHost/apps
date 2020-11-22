# Validation template for High Quality tag request

Package URL:

This template is designed to be used by the Apps group to validate requests from packagers for the tag High Quality.

- [ ] The package is level 8.
- [ ] The app is reasonably up to date with the upstream version.
- [ ] The maintainers intend to maintain the app, and will communicate with the Apps group if they intend to stop maintaining the app.
- [ ] The package **supports all recommended integrations with Yunohost**, in particular:
    - [ ] Architectures: The package has been tested and validated for other architectures it's supposed to work on (in particular ARM or 32bit), or properly handles the detection of unsupported architectures at the beginning of the install script.
    - [ ] Yunohost tile integration: The package integrates the YunoHost tile `yunohost_panel.conf.inc` in its nginx configuration.
    - [ ] LDAP/SSO integration *(if relevant)*: The package supports LDAP authentication **and** automatic login through Yunohost's SSO.
    - [ ] Fail2ban integration *(if relevant)*: The package provides rules to block brute force attempts on the app
- [ ] The package has been **reviewed by members of the Apps group** to validate that:
   - [ ] It is up to date with the recommended packaging practices.
   - [ ] There are no obvious security issues or borderline practices.
- [ ] The maintainers agree to follow the **recommended development workflow**:
   - [ ] The `revision` field in the app catalog (`apps.json`) points to `HEAD`
   - [ ] All pull requests should target the `testing` branch before being merged into `master`.
   - [ ] All pull requests should be reviewed and validated by another member of the app group before merging.
   - [ ] The repository has a [`pull_request_template.md`](https://github.com/YunoHost/apps/blob/master/pull_request_template-HQ-apps.md).
