<!--
Nota bene: ce README est automatiquement généré par https://github.com/YunoHost/apps/tree/master/tools/readme_generator
Il ne doit pas être modifié à la main.
-->

# GoToSocial pour YunoHost

[![Niveau d'intégration ](https://dash.yunohost.org/integration/gotosocial.svg)](https://dash.yunohost.org/appci/app/gotosocial) ![Status du fonctionnement](https://ci-apps.yunohost.org/ci/badges/gotosocial.status.svg) ![Statut demaintenance](https://ci-apps.yunohost.org/ci/badges/gotosocial.maintain.svg)

[![Installer GoToSocial avec YunoHost](https://install-app.yunohost.org/install-with-yunohost.svg)](https://install-app.yunohost.org/?app=gotosocial)

*[Lire le README dans d'autres langues.](./ALL_README.md)*

> *Ce package vous permet d’installer GoToSocial rapidement et simplement sur un serveur YunoHost.
Si vous n’avez pas YunoHost, regardez [ici](https://yunohost.org/#/install) pour savoir comment l’installer et en profiter.*

## Vue d'ensemble

GoToSocial is a fast [ActivityPub](https://activitypub.rocks/) social network server, written in Golang.

With GoToSocial, you can keep in touch with your friends, post, read, and share images and articles. All without being tracked or advertised to!

The official documentation is at [docs.gotosocial.org](https://docs.gotosocial.org).  
The documentation for this YunoHost package [can be read here](./doc/DOCS.md) and the admin is **strongly encouraged to read it**!

Please note that this package uses the ["i'm so tired" software license 1.0](https://github.com/YunoHost-Apps/gotosocial_ynh/blob/master/LICENSE), please read it and accept it before proceeding with installation.

**Version incluse :** 0.13.3~ynh1

## Captures d'écran

![Capture d'écran de GoToSocial](./doc/screenshots/screenshot.png)

## :red_circle: Anti-fonctionnalités

- **Alpha software**: Early development stage. May contain changing or unstable features, bugs, and security vulnerability.
- **Not totally free package**: The YunoHost package of this app is under an overall free licence, but with clauses that restrict its use.

## Documentations et ressources

- Site officiel de l’app : <https://gotosocial.org/>
- Documentation officielle utilisateur : <https://docs.gotosocial.org/en/latest/>
- Documentation officielle de l'admin <https://docs.gotosocial.org/en/latest/>
- Dépôt de code officiel de l’app : <https://github.com/superseriousbusiness/gotosocial>
- YunoHost Store : <https://apps.yunohost.org/app/gotosocial>
- Signaler un bug : <https://github.com/YunoHost-Apps/gotosocial_ynh/issues>

## Informations pour les développeurs

Merci de faire vos pull request sur la [branche branch](https://github.com/YunoHost-Apps/gotosocial_ynh/tree/testing),


Pour essayer la branche testing, procédez comme suit.

```bash
sudo yunohost app install https://github.com/YunoHost-Apps/gotosocial_ynh/tree/testing --debug
or
sudo yunohost app upgrade gotosocial -u https://github.com/YunoHost-Apps/gotosocial_ynh/tree/testing --debug
```

**Plus d'infos sur le packaging d'applications :** <https://yunohost.org/packaging_apps>
