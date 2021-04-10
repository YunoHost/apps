
NB. : this is an ***automated*** attempt to migrate the app to the new permission system

You should ***not*** blindly trust the proposed changes. In particular, the auto-patch will not handle:
- situations which are more complex than "if is_public is true, allow visitors"
- situations where the app needs to be temporarily public (then possible private) during initial configuration
- apps that need to define extra permission for specific section of the app (such as admin interface)
- apps using non-standard syntax
- other specific use cases

***PLEASE*** carefully review, test and amend the proposed changes if you find that the autopatch did not do a proper job.
