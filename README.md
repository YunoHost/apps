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

![screenshot](https://raw.githubusercontent.com/YunoHost/apps/master/screenshot.jpg)

#### How to add your app to the community list

* Fork and edit the [community list](https://github.com/YunoHost/apps/tree/master/community.json)
* Add your app's ID and git information at the right alphabetical place
* Indicate the app's functioning state: `notworking`, `inprogress`, or `working`
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

#### How to propose your app to be integrated in the official applications list

Here is the procedure to request that your app will be part of the list of official applications of YunoHost:

* before everything, having you application joining the list of official applications will make you a maintainer of it and will requires you to ensure this position or to find someone else to do it in the future
* your app must be tested on several architectures (32/64 bits, ARM) or depends on cross-platform systems
* you must be subscribed to the [apps official mailing list](https://list.yunohost.org/cgi-bin/mailman/listinfo/apps) since this is the way that we communicate to apps maintainers
* your application must have the following scripts:
 * a install script, obviously
 * a remove script
 * an upgrade script if needed
 * a backup/restore script if your application stores data
* your application must be installable on a custom path (`domain.tld/custom_path/`) in addition to the root path
* if relevant, your application must be integrated with YunoHost SSO
* your application you have packaged must be free software
* once all those requirements are fulfilled, fork this repository, add your application to the official.json list with the status "validated" following the documentation above, then open a pull request
* we will then start a reviewing process and we will work together to bring your application to a state where we can hopefully include it to the official applications list :)

#### Helper script

You can use the <code>add_or_update.py</code> python script to add or update
your app from one of the 2 json files.

Usage:

```bash
./add_or_update.py [community.json OR official.json] [github url [github url [github url ...]]]
```

#### More information on [yunohost.org/packaging_apps](https://yunohost.org/packaging_apps)
