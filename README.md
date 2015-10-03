# YunoHost apps directory

<img src="https://yunohost.org/logo.png" width=80>
![roundcube](https://yunohost.org/images/roundcube.png)
![ttrss](https://yunohost.org/images/ttrss.png)
![wordpress](https://yunohost.org/images/wordpress.png)
![transmission](https://yunohost.org/images/transmission.png)
![jappix](https://yunohost.org/images/jappix.png)

Here you will find the repositories and versions of every apps integrated in YunoHost.

https://yunohost.org/apps


## Lists

 - **official.json** contains the links and manifests of validated and maintained apps
 - **community.json** contains all references to known YunoHost packages. If you want to add your app to the list, please [send a Pull Request](#contributing)


## Usage

The official package list is automatically fetched. If you want to **enable the community package list** on your YunoHost instance:
```
sudo yunohost app fetchlist -n community -u https://yunohost.org/community.json
```


## Contributing

![screenshot](https://raw.githubusercontent.com/YunoHost/apps/master/screenshot.jpg)

#### How to add your app to community list

* Fork and edit the [community list](https://github.com/YunoHost/apps/tree/master/community.json)
* Add your app's ID and information to the right alphabetical place
* Include the git repository URL, branch and commit
* Include a timestamp of the last update time
* Include the full `manifest.json` file of your app
* Include the state of functioning of your app: `not working`, `in progress` or `ready`

Here is an example app addition:
```json
    "wallabag": {
        "git": {
            "branch": "master",
            "revision": "c2fc62438ac5c9503e3f4ebfdc425ec03a0ec0c0",
            "url": "https://github.com/abeudin/wallabag_ynh.git"
        },
        "lastUpdate": 1424424628,
        "manifest": {
            "arguments": {
                "install": [
                    {
                        "ask": {
                            "en": "Choose a domain for Wallabag",
                            "fr": "Choisissez un domaine pour Wallabag"
                        },
                        "example": "domain.org",
                        "name": "domain",
                        "type": "domain"
                    },
                    {
                        "ask": {
                            "en": "Choose a path for Wallabag",
                            "fr": "Choisissez un chemin pour Wallabag"
                        },
                        "default": "/wallabag",
                        "example": "/wallabag",
                        "name": "path",
                        "type": "path"
                    }
                ]
            },
            "description": {
                "en": "A self hostable read-it-later app",
                "fr": "Une application de lecture-plus-tard auto-hébergeable"
            },
            "id": "wallabag",
            "maintainer": {
                "email": "beudbeud@beudibox.fr",
                "name": "beudbeud"
            },
            "multi_instance": "true",
            "name": "Wallabag",
            "url": "http://www.wallabag.org"
        },
        "state": "ready"
    }
```

Then, just send a [Pull Request](https://github.com/YunoHost/apps/pulls/).


#### How to add an app to official list

Same steps than above, but on the `official.json` list.
**Important**: You have to find a maintainer willing to take care of the package while published.

---

#### More information on [yunohost.org/packaging_apps](https://yunohost.org/packaging_apps)

