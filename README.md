# YunoHost application catalog

<img alt="YunoHost logo" src="https://avatars.githubusercontent.com/u/1519495?s=200&v=4" width=80><img alt="Package logo" src="https://yunohost.org/user/images/yunohost_package.png" width=80>

This repository contains the default YunoHost app catalog.
It is browsable at [apps.yunohost.org](https://apps.yunohost.org).

## Where can I learn about app packaging in YunoHost?

- You can browse [the contributor documentation](https://yunohost.org/contributordoc)
- If you are not familiar with Git/GitHub, you can have a look at our [homemade guide](https://yunohost.org/packaging_apps_git)
- Don't hesitate to reach for help on the dedicated [application packaging chatroom](https://yunohost.org/chat_rooms)... we can even schedule an audio meeting to help you get started!

## Content of this repository

### `apps.toml`

This is the main catalog file, containing references to the apps' repositories,
along with a few metadata about them such as their category or maintenance state.

It is regularly read by the [catalog builder](https://github.com/YunoHost/apps-tools)
which publishes the results on <https://app.yunohost.org/default>.

### `categories.toml` and `antifeatures.toml`

Those files contain infos about apps metadatas.

### `graveyard.toml`

This file is for apps that are long-term not-working and unlikely to be ever revived.

### `wishlist.toml`

This file contains apps that users wish to be packaged. If you want to help YunoHost, check it out!

It is [browsable online](https://apps.yunohost.org/wishlist).

### `rejectedlist.toml`

This file contains apps that will not be packaged, because of incompatibilities with the YunoHost project.
It is used to prevent apps to be added to the wishlist.


## How to add your app to the application catalog

> **Note**
> The YunoHost project will **NOT** integrate in its catalog applications that are not
> based on free-software upstreams.

> **Note**
> We strongly encourage you to transfer the ownership of your repository to
> the YunoHost-Apps organization on GitHub, such that the community will help you
> with keeping your app working and up to date with packaging evolutions on the long run.

To add your application to the catalog:

- Fork [this repository](https://github.com/YunoHost/apps)
- Edit the [`apps.toml`](/apps.toml) file
  - Add your app's ID and git information at the right alphabetical place
  - Indicate the app's functioning state: `notworking`, `inprogress`, or `working`
  - Indicate the app category, which you can pick from `categories.toml`
  - Indicate any anti-feature that your app may be subject to, see `antifeatures.toml` (or remove the `antifeatures` key if there's none)
  - Indicate if your app can be thought of as an alternative to popular proprietary services (or remove the `potential_alternative_to` key if there's none)
  - *Do not* add the `level` entry by yourself. Our automatic test suite ("the CI") will handle it.
- Add the app's logo inside the `logos` folder. Please keep this logo as small as possible. It also must be square (or almost square). The filename must be the name of the app in lower case.
- Commit and push your modifications to your repository
- Create a [Pull Request](https://github.com/YunoHost/apps/pulls/)

App example addition:

```toml
[your_app]
antifeatures = [ "deprecated-software" ]   # Replace with the appropriate category id found in antifeatures.toml, remove if no relevant antifeature applies
potential_alternative_to = [ "YouTube" ]   # Indicate if your app can be thought of as an alternative to popular proprietary services (or remove if none applies)
category = "foobar"                        # Replace with the appropriate category id found in categories.toml, don't invent a category
state = "working"
url = "https://github.com/YunoHost-Apps/your_app_ynh"
```

> **Warning**
> Implicitly, the catalog publishes the `HEAD` of branch `master`
> (this can be overwritten by adding keys `branch` and `revision`).
> Therefore, **be careful that any commit on the `master` branch will automatically be published**.
> **We strongly encourage you to develop in separate branches**, and only
> merge changes that were carefully tested. Get in touch with the Apps group to
> obtain an access to the developer CI where you'll be able to test your app
> easily.

## Updating apps levels in the catalog

App packagers should *not* manually set their apps' level. The levels of all
the apps are automatically updated once a week on Friday, according to the
results from the official app CI.

## Apps flagged as not-maintained

Applications with no recent activity and no active sign from maintainer may be
flagged in `apps.toml` with the `package-not-maintained` antifeature tag to
signify that the app is inactive and may slowly become outdated with respect to
the upstream, or with respect to good packaging practices. It does **not** mean
that the app is not working anymore.

Feel free to contact the app group if you feel like taking over the maintenance
of a currently unmaintained app!
