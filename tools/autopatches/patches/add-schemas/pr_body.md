
This is an ***automated*** patch to add the TOML schemas URLs to manifest.toml and tests.toml.

This allows to check for the validity of your TOML files.

Multiple tools can be used to validate files against their schema:

* `taplo`, a command line tool: `taplo lint manifest.toml`
* IDEs like VScode have plugins to automagically validate files
