# YunoHost apps directory

<img src="https://yunohost.org/logo.png" width=80>

Here you will find the repositories and versions of every apps integrated in YunoHost.

https://yunohost.org/apps


## Lists
**Situation will change soon regarding lists. Consider this info as obsolete**
 - **official.json** contains the repository information of validated apps.
 - **community.json** contains all references to known "free-software" YunoHost packages. If you want to add your app to the list, please [send a Pull Request](#contributing)


## Usage

The official package list is automatically fetched. If you want to **enable the community package list** on your YunoHost instance:
```
sudo yunohost app fetchlist -n community -u https://yunohost.org/community.json
```


## Contributing

### How to add your app to the community list
**If** your app is under a free-software licence : 
* Fork and edit the [community list](https://github.com/YunoHost/apps/tree/master/community.json)
* Add your app's ID and git information at the right alphabetical place
* Indicate the app's functioning state: `notworking`, `inprogress`, or `working`
* Send a [Pull Request](https://github.com/YunoHost/apps/pulls/)

App example addition:
```json
    "wallabag": {
        "branch": "master",
        "revision": "c2fc62438ac5c9503e3f4ebfdc425ec03a0ec0c0",
        "url": "https://github.com/abeudin/wallabag_ynh",
        "state": "working"
    }
```

N.B. : You can now put `HEAD` as `revision`. This way, you won't have to come and update this file each time you change things in your app. *But* this also means that any change to your `master` branch will be made available to everybody. Hence, when developing things which are not production-ready, if you use `HEAD` we strongly recommend that you develop in a `testing` branch (for instance) until you consider things stable enough to be merged in `master`.

N.B. 2 : Organization is still debating about what to do with non-free apps listing (cf. [this thread](https://forum.yunohost.org/t/about-community-and-official-apps/6372/25). Such a list is unlikely to be maintained by the YunoHost project officially. However, it could be created and maintained by member of the community. Check out [the forum](https://forum.yunohost.org) about this.

### How to help translating

We invite you to use [translate.yunohost.org](https://translate.yunohost.org/) instead of doing Pull Request for files in `locales` folder.

### Helper script

You can use the <code>add_or_update.py</code> python script to add or update
your app from one of the 2 json files.

Usage:

```bash
./add_or_update.py [community.json OR official.json] [github/gitlab url OR app name [github/gitlab url OR app name [github/gitlab url OR app name ...]]]
```

#### More information
See [yunohost.org/packaging_apps](https://yunohost.org/packaging_apps)
