# YunoHost application catalog

<img src="https://avatars.githubusercontent.com/u/1519495?s=200&v=4" width=80><img src="https://yunohost.org/user/images/yunohost_package.png" width=80>

Here you will find the repositories and versions of every apps available in YunoHost's default catalog.

It is browsable here: https://yunohost.org/apps

The main file of the catalog is [**apps.json**](./apps.json) which contains
references to the corresponding git repositories for each application, along
with a few metadata about them such as its category or maintenance state. This
file regularly read by `list_builder.py` which publish the results on
https://app.yunohost.org/default/.

### Where can I learn about app packaging in Yunohost ?

- You can browse the contributor documentation : https://yunohost.org/contributordoc
- If you are not familiar with Git/Github, you can have a look at our [homemade guide](https://yunohost.org/#/packaging_apps_git)
- Don't hesitate to reach for help on the dedicated [application packaging chatroom](https://yunohost.org/chat_rooms) ... we can even schedule an audio meeting to help you get started !

### How to add your app to the application catalog

N.B. : the Yunohost project will **NOT** integrate in its catalog applications that are not
based on free-software upstreams.

To add your application to the catalog:
* Fork this repository and edit the [apps.json](https://github.com/YunoHost/apps/tree/master/apps.json) file
* Add your app's ID and git information at the right alphabetical place
* Indicate the app's functioning state: `notworking`, `inprogress`, or `working`
* *Do not* add the level entry by yourself. Our automatic test suite ("the CI") will handle it.
* Create a [Pull Request](https://github.com/YunoHost/apps/pulls/)

App example addition:
```json
    "wallabag": {
        "url": "https://github.com/abeudin/wallabag_ynh",
        "state": "working"
    }
```

N.B. : We strongly encourage you to transfer the ownership of your repository to
the Yunohost-Apps organization on Github, such that the community will help you
with keeping your app working and up to date with packaging evolutions.

N.B.2 : Implicitly, the catalog publishes the `HEAD` of branch `master`
(this can be overwritten by adding keys `branch` and `revision`).
Therefore, **be careful that any commit on the `master` branch will automatically be published**.
**We strongly encourage you to develop in separate branches**, and only
merge changes that were carefully tested. Get in touch with the Apps group to
obtain an access to the developer CI where you'll be able to test your app
easily.

#### Helper script

You can use the <code>add_or_update.py</code> python script to add or update
your app from one of the 2 json files.

Usage:

```bash
./add_or_update.py apps.json [github/gitlab url OR app name [github/gitlab url OR app name [github/gitlab url OR app name ...]]]
```

### How to help translating

Update on Nov. 2020 : this part is broken / not maintained anymore for the
moment...

We invite you to use [translate.yunohost.org](https://translate.yunohost.org/)
instead of doing Pull Request for files in `locales` folder.

### How to make my app flagged as High Quality ?

A High Quality app will be highlighted in the app list and marked as a level 9 app.
To become a High Quality app, a package has to follow the criterias listed [here](hq_validation_template.md).

Once the app is validated is "high quality", the tag `"high_quality": true`
shall be added to the app infos inside the catalog (`apps.json`).

### Apps flagged as not-maintained

Applications with no recent activity and no active sign from maintainer may be flagged in `apps.json` with `"maintained": false` to signify that the app is inactive and may slowly become outdated with respect to the upstream, or with respect to good packaging practices. It does **not** mean that the app is not working anymore.

Feel free to contact the app group if you feel like taking over the maintenance of a currently unmaintained app!
