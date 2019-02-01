# YunoHost apps directory

<img src="https://yunohost.org/logo.png" width=80>

![roundcube](https://yunohost.org/images/roundcube.png)
![ttrss](https://yunohost.org/images/ttrss.png)
![wordpress](https://yunohost.org/images/wordpress.png)
![transmission](https://yunohost.org/images/transmission.png)
![jappix](https://yunohost.org/images/jappix.png)
<img src="https://yunohost.org/images/freshrss_logo.png" width=60>
<img src="https://yunohost.org/images/Icons_mumble.svg" width=60>
<img src="https://yunohost.org/images/Lutim_small.png" width=50>
<img src="https://yunohost.org/images/PluXml-logo_transparent.png" width=80>
<img src="https://yunohost.org/images/rainloop_logo.png" width=60>
<img src="https://yunohost.org/images/Etherpad.svg" width=60>

Here you will find the repositories and versions of every apps integrated in YunoHost.

https://yunohost.org/apps


## Lists

 - **official.json** contains the repository information of validated apps.
 - **community.json** contains all references to known YunoHost packages. If you want to add your app to the list, please [send a Pull Request](#contributing)


## Usage

The official package list is automatically fetched. If you want to **enable the community package list** on your YunoHost instance:
```
sudo yunohost app fetchlist -n community -u https://yunohost.org/community.json
```


## Contributing

### How to add your app to the community list

* Fork and edit the [community list](https://github.com/YunoHost/apps/tree/master/community.json)
* Add your app's ID and git information at the right alphabetical place
* Indicate the app's functioning state: `notworking`, `inprogress`, or `working`
* Do not add the level yourself. The CI will do it.
* Send a [Pull Request](https://github.com/YunoHost/apps/pulls/)

App example addition:
```json
    "wallabag": {
        "branch": "master",
        "revision": "c2fc62438ac5c9503e3f4ebfdc425ec03a0ec0c0",
        "url": "https://github.com/abeudin/wallabag_ynh.git",
        "state": "working"
    }
```

N.B. : You can now put `HEAD` as `revision`. This way, you won't have to come and update this file each time you change things in your app. *But* this also means that any change to your `master` branch will be made available to everybody. Hence, when developing things which are not production-ready, if you use `HEAD` we strongly recommend that you develop in a `testing` branch (for instance) until you consider things stable enough to be merged in `master`.

### How to help translating

We invite you to use [translate.yunohost.org](https://translate.yunohost.org/) instead of doing Pull Request for files in `locales` folder.

### Helper script

You can use the <code>add_or_update.py</code> python script to add or update
your app from one of the 2 json files.

Usage:

```bash
./add_or_update.py [community.json OR official.json] [github/gitlab url OR app name [github/gitlab url OR app name [github/gitlab url OR app name ...]]]
```

### How to make my app a Featured app

A featured app will be highlighted in the community list as a high quality app.  
To become a Featured app, a package have to follow the following rules:

* The app should already be in the community list for 2 months.
* The app should be keep up to date, regarding the upstream source. (If it’s possible with our current YunoHost version)
* The package itself should be up to date regarding the packaging recommendations and helpers.
* The package should be level 7, at least.
* The repository should have testing and master branches, at least. The list should point to HEAD, so the list stays up to date.
* Any modification should be done to the testing branch, and wait at least for one approval for one member of the Apps group. So that we can ensure that there’s nothing in opposition to those criteria. Nor any changes that would harm servers.

If the app is already tag as Featured and one of those criteria isn't respected anymore. After a warning, the tag will be removed until the criteria are again validated.

To make an app a Featured app, technically, you have to add the tag ```"featured": true```.
```json
    "wallabag": {
        "branch": "master",
        "featured": true,
        "revision": "c2fc62438ac5c9503e3f4ebfdc425ec03a0ec0c0",
        "url": "https://github.com/abeudin/wallabag_ynh.git",
        "state": "working"
    }
```

#### More information
See [yunohost.org/packaging_apps](https://yunohost.org/packaging_apps)
