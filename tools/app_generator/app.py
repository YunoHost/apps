#### Imports
from io import BytesIO
import re
import os
import jinja2 as j2
from flask import (
    Flask,
    render_template,
    render_template_string,
    request,
    redirect,
    flash,
    send_file,
)
from markupsafe import Markup  # No longer imported from Flask

# Form libraries
from flask_wtf import FlaskForm
from wtforms import (
    StringField,
    RadioField,
    SelectField,
    SubmitField,
    TextAreaField,
    BooleanField,
    SelectMultipleField,
)
from wtforms.validators import (
    DataRequired,
    InputRequired,
    Optional,
    Regexp,
    URL,
    Length,
)

# Translations
from flask_babel import Babel
from flask_babel import lazy_gettext as _

from flask import redirect, request, make_response  # Language swap by redirecting

# Markdown to HTML - for debugging purposes
from misaka import Markdown, HtmlRenderer

# Managing zipfiles
import zipfile
from flask_cors import CORS
from urllib import parse
from secrets import token_urlsafe

#### GLOBAL VARIABLES
YOLOGEN_VERSION = "0.10"
GENERATOR_DICT = {"GENERATOR_VERSION": YOLOGEN_VERSION}

#### Create FLASK and Jinja Environments
app = Flask(__name__)
app.config["SECRET_KEY"] = token_urlsafe(16)  # Necessary for the form CORS
cors = CORS(app)

environment = j2.Environment(loader=j2.FileSystemLoader("templates/"))

# Handle translations
BABEL_TRANSLATION_DIRECTORIES = "translations"

babel = Babel()

LANGUAGES = {"en": _("English"), "fr": _("French")}


@app.context_processor
def inject_conf_var():
    return dict(AVAILABLE_LANGUAGES=LANGUAGES)


def configure(app):
    babel.init_app(app, locale_selector=get_locale)
    app.config["LANGUAGES"] = LANGUAGES


def get_locale():
    print(request.accept_languages.best_match(app.config["LANGUAGES"].keys()))
    print(request.cookies.get("lang", "en"))
    # return 'en' # to test
    # return 'fr'
    if request.args.get("language"):
        print(request.args.get("language"))
        session["language"] = request.args.get("language")
    return request.cookies.get("lang", "en")
    # return request.accept_languages.best_match(app.config['LANGUAGES'].keys()) # The result is based on the Accept-Language header. For testing purposes, you can directly return a language code, for example: return ‘de’


configure(app)

#### Custom functions


# Define custom filter
@app.template_filter("render_markdown")
def render_markdown(text):
    renderer = HtmlRenderer()
    markdown = Markdown(renderer)
    return markdown(text)


# Add custom filter
j2.filters.FILTERS["render_markdown"] = render_markdown


# Converting markdown to html
def markdown_file_to_html_string(file):
    with open(file, "r") as file:
        markdown_content = file.read()
        # Convert content from Markdown to HTML
        html_content = render_markdown(markdown_content)
        # Return Markdown and HTML contents
        return markdown_content, html_content


### Forms


# Language selector. Not used (in GeneratorForm) until it's fixed or superseeded.
# Use it in the HTML with {{ form_field(main_form.generator_language) }}
class Translations(FlaskForm):
    generator_language = SelectField(
        _("Select language"),
        choices=[("none", "")] + [language for language in LANGUAGES.items()],
        default=["en"],
        id="selectLanguage",
    )


class GeneralInfos(FlaskForm):

    app_id = StringField(
        Markup(_("Application identifier (id)")),
        description=_("Small caps and without spaces"),
        validators=[DataRequired(), Regexp("[a-z_1-9]+.*(?<!_ynh)$")],
        render_kw={
            "placeholder": "my_super_app",
        },
    )

    app_name = StringField(
        _("App name"),
        description=_(
            "It's the application name, displayed in the user interface"
        ),
        validators=[DataRequired()],
        render_kw={
            "placeholder": "My super App",
        },
    )

    description_en = StringField(
        _("Short description (en)"),
        description=_(
            "Explain in a few words (10-15) why this app is useful or what it does (the goal is to give a broad idea for the user browsing an hundred apps long catalog"
        ),
        validators=[DataRequired()],
    )
    description_fr = StringField(
        _("Short description (fr)"),
        description=_(
            "Explain in a few words (10-15) why this app is useful or what it does (the goal is to give a broad idea for the user browsing an hundred apps long catalog"
        ),
        validators=[DataRequired()],
    )


class IntegrationInfos(FlaskForm):

    # TODO : people shouldnt have to put the ~ynh1 ? This should be added automatically when rendering the app files ?
    version = StringField(
        _("Version"),
        validators=[Regexp("\d{1,4}.\d{1,4}(.\d{1,4})?(.\d{1,4})?~ynh\d+")],
        render_kw={"placeholder": "1.0~ynh1"},
    )

    maintainers = StringField(
        _("Maintainer of the generated app"),
        description=_(
            "Usually you put your name here... If you're okay with it ;)"
        ),
    )

    yunohost_required_version = StringField(
        _("Minimal YunoHost version"),
        description=_(
            "Minimal YunoHost version for the application to work"
        ),
        render_kw={
            "placeholder": "11.1.21",
        },
    )

    architectures = SelectMultipleField(
        _("Supported architectures"),
        choices=[
            ("all", _("All architectures")),
            ("amd64", "amd64"),
            ("i386", "i386"),
            ("armhf", "armhf"),
            ("arm64", "arm64"),
        ],
        default=["all"],
        validators=[DataRequired()],
    )

    multi_instance = BooleanField(
        _(
            "The app can be installed multiple times at the same time on the same server"
        ),
        default=True,
    )

    ldap = SelectField(
        _("The app will be integrating LDAP"),
        description=_(
            "Which means it's possible to use Yunohost credentials to log into this app. 'LDAP' corresponds to the technology used by Yunohost to handle a centralised user base. Bridging the app and Yunohost's LDAP often requires to add the proper technical details in the app's configuration file"
        ),
        choices=[
            ("false", _("No")),
            ("true", _("Yes")),
            ("not_relevant", _("Not relevant")),
        ],
        default="not_relevant",
        validators=[DataRequired()],
    )
    sso = SelectField(
        _("The app will be integrated in Yunohost SSO (Single Sign On)"),
        description=_(
            "Which means that people will be logged in the app after logging in YunoHost's portal, without having to sign on specifically into this app."
        ),
        choices=[
            ("false", _("Yes")),
            ("true", _("No")),
            ("not_relevant", _("Not relevant")),
        ],
        default="not_relevant",
        validators=[DataRequired()],
    )


class UpstreamInfos(FlaskForm):

    license = StringField(
        _("Licence"),
        description=_(
            "You should check this on the upstream repository. The expected format is a SPDX id listed in https://spdx.org/licenses/"
        ),
        validators=[DataRequired()],
    )

    website = StringField(
        _("Official website"),
        description=_("Leave empty if there is no official website"),
        validators=[URL(), Optional()],
        render_kw={
            "placeholder": "https://awesome-app-website.com",
        },
    )
    demo = StringField(
        _("Official app demo"),
        description=_("Leave empty if there is no official demo"),
        validators=[URL(), Optional()],
        render_kw={
            "placeholder": "https://awesome-app-website.com/demo",
        },
    )
    admindoc = StringField(
        _("Admin documentation"),
        description=_("Leave empty if there is no official admin doc"),
        validators=[URL(), Optional()],
        render_kw={
            "placeholder": "https://awesome-app-website.com/doc/admin",
        },
    )
    userdoc = StringField(
        _("Usage documentation"),
        description=_("Leave empty if there is no official user doc"),
        validators=[URL(), Optional()],
        render_kw={
            "placeholder": "https://awesome-app-website.com/doc/user",
        },
    )
    code = StringField(
        _("Code repository"),
        validators=[URL(), DataRequired()],
        render_kw={
            "placeholder": "https://some.git.forge/org/app",
        },
    )


class InstallQuestions(FlaskForm):

    domain_and_path = SelectField(
        _(
            "Ask the URL where the app will be installed ('domain' and 'path' variables)"
        ),
        default="true",
        choices=[
            ("true", _("Ask domain+path")),
            (
                "full_domain",
                _(
                    "Ask only the domain (the app requires to be installed at the root of a dedicated domain)"
                ),
            ),
            ("false", _("Do not ask (it isn't a webapp)")),
        ],
    )

    init_main_permission = BooleanField(
        _("Ask who can access to the app"),
        description=_(
            "In the users groups : by default at least 'visitors', 'all_users' et 'admins' exists. (It was previously the private/public app concept)"
        ),
        default=True,
    )

    init_admin_permission = BooleanField(
        _("Ask who can access to the admin interface"),
        description=_("In the case where the app has an admin interface"),
        default=False,
    )

    language = SelectMultipleField(
        _("Supported languages"),
        choices=[
            ("_", _("None / not relevant")),
            ("en", _("English")),
            ("fr", _("French")),
            ("en", _("Spanish")),
            ("it", _("Italian")),
            ("de", _("German")),
            ("zh", _("Chinese")),
            ("jp", _("Japanese")),
            ("da", _("Danish")),
            ("pt", _("Portugese")),
            ("nl", _("Dutch")),
            ("ru", _("Russian")),
        ],
        default=["_"],
        validators=[DataRequired()],
    )


# manifest
class Ressources(FlaskForm):

    # Sources
    source_url = StringField(
        _("Application source code or executable"),
        validators=[DataRequired(), URL()],
        render_kw={
            "placeholder": "https://github.com/foo/bar/archive/refs/tags/v1.2.3.tar.gz",
        },
    )
    sha256sum = StringField(
        _("Sources sha256 checksum"),
        validators=[DataRequired(), Length(min=64, max=64)],
        render_kw={
            "placeholder": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
        },
    )

    auto_update = SelectField(
        _("Enable automatic update of sources (using a bot running every night)"),
        description=_(
            "If the upstream software is hosted in one of the handled sources and publishes proper releases or tags, the bot will create a pull request to update the sources URL and checksum"
        ),
        default="none",
        choices=[
            ("none", "Non"),
            ("latest_github_tag", "Github (tag)"),
            ("latest_github_release", "Github (release)"),
            ("latest_github_commit", "Github (commit)"),
            ("latest_gitlab_tag", "Gitlab (tag)"),
            ("latest_gitlab_release", "Gitlab (release)"),
            ("latest_gitlab_commit", "Gitlab (commit)"),
            ("latest_gitea_tag", "Gitea (tag)"),
            ("latest_gitea_release", "Gitea (release)"),
            ("latest_gitea_commit", "Gitea (commit)"),
            ("latest_forgejo_tag", "Forgejo (tag)"),
            ("latest_forgejo_release", "Forgejo (release)"),
            ("latest_forgejo_commit", "Forgejo (commit)"),
        ],
    )

    apt_dependencies = StringField(
        _(
            "Dependencies to be installed via apt (separated by comma and/or spaces)"
        ),
        render_kw={
            "placeholder": "foo, bar2.1-ext, libwat",
        },
    )

    database = SelectField(
        _("Initialize an SQL database"),
        choices=[
            ("false", "Non"),
            ("mysql", "MySQL/MariaDB"),
            ("postgresql", "PostgreSQL"),
        ],
        default="false",
    )

    system_user = BooleanField(
        _("Initialize a system user for this app"),
        default=True,
    )

    install_dir = BooleanField(
        _("Initialize an installation folder for this app"),
        description=_("By default it's /var/www/$app"),
        default=True,
    )

    data_dir = BooleanField(
        _("Initialize a folder to store the app data"),
        description=_("By default it's /var/yunohost.app/$app"),
        default=False,
    )


class SpecificTechnology(FlaskForm):

    main_technology = SelectField(
        _("App main technology"),
        choices=[
            ("none", _("None / Static application")),
            ("php", "PHP"),
            ("nodejs", "NodeJS"),
            ("python", "Python"),
            ("ruby", "Ruby"),
            ("other", _("Other")),
        ],
        default="none",
        validators=[DataRequired()],
    )

    install_snippet = TextAreaField(
        _("Installation specific commands"),
        description=_(
            "These commands are executed from the app installation folder (by default, /var/www/$app) after the sources have been deployed. This field uses by default a classic example based on the selected technology. You should probably compare and adapt it according to the app installation documentation"
        ),
        validators=[Optional()],
        render_kw={"spellcheck": "false"},
    )

    #
    # PHP
    #

    use_composer = BooleanField(
        _("Use composer"),
        description=_(
            "Composer is a PHP dependencies manager used by some apps"
        ),
        default=False,
    )

    #
    # NodeJS
    #

    nodejs_version = StringField(
        _("NodeJS version"),
        description=_("For example: 16.4, 18, 18.2, 20, 20.1, ..."),
        render_kw={
            "placeholder": "20",
        },
    )

    use_yarn = BooleanField(
        _("Install and use Yarn"),
        default=False,
    )

    # NodeJS / Python / Ruby / ...

    systemd_execstart = StringField(
        _("Command to start the app daemon (from systemd service)"),
        description=_(
            "Corresponds to 'ExecStart' statement in systemd. You can use '__INSTALL_DIR__' to refer to the install directory, or '__APP__' to refer to the app id"
        ),
        render_kw={
            "placeholder": "__INSTALL_DIR__/bin/app --some-option",
        },
    )


class AppConfig(FlaskForm):

    use_custom_config_file = BooleanField(
        _("The app uses a specific configuration file"),
        description=_(
            "Usually : .env, config.json, conf.ini, params.yml, ..."
        ),
        default=False,
    )

    custom_config_file = StringField(
        _("Name or file path to use"),
        validators=[Optional()],
        render_kw={
            "placeholder": "config.json",
        },
    )

    custom_config_file_content = TextAreaField(
        _("App configuration file pattern"),
        description=_(
            "In this pattern, you can use the syntax __FOO_BAR__ which will automatically replaced by the value of the variable $foo_bar"
        ),
        validators=[Optional()],
        render_kw={"spellcheck": "false"},
    )


class Documentation(FlaskForm):
    # TODO :    # screenshot
    description = TextAreaField(
        Markup(
            _(
                """doc/DESCRIPTION.md: A comprehensive presentation of the app, possibly listing the main features, possible warnings and specific details on its functioning in Yunohost (e.g. warning about integration issues)."""
            )
        ),
        validators=[Optional()],
        render_kw={
            "spellcheck": "false",
        },
    )
    pre_install = TextAreaField(
        _("doc/PRE_INSTALL.md: important info to be shown to the admin before installing the app"),
        description=_("Leave empty if not relevant"),
        validators=[Optional()],
        render_kw={
            "spellcheck": "false",
        },
    )
    post_install = TextAreaField(
        _("doc/POST_INSTALL.md: important info to be shown to the admin after installing the app"),
        description=_("Leave empty if not relevant"),
        validators=[Optional()],
        render_kw={
            "spellcheck": "false",
        },
    )
    pre_upgrade = TextAreaField(
        _("doc/PRE_UPGRADE.md: important info to be shown to the admin before upgrading the app"),
        description=_("Leave empty if not relevant"),
        validators=[Optional()],
        render_kw={
            "spellcheck": "false",
        },
    )
    post_upgrade = TextAreaField(
        _("doc/POST_UPGRADE.md: important info to be shown to the admin after upgrading the app"),
        description=_("Leave empty if not relevant"),
        validators=[Optional()],
        render_kw={
            "spellcheck": "false",
        },
    )
    admin = TextAreaField(
        _("doc/ADMIN.md: general tips on how to administrate this app"),
        description=_("Leave empty if not relevant"),
        validators=[Optional()],
        render_kw={
            "spellcheck": "false",
        },
    )


class MoreAdvanced(FlaskForm):

    enable_change_url = BooleanField(
        _("Handle app install URL change (change_url script)"),
        default=True,
        render_kw={
            "title": _(
                "Should changing the app URL be allowed ? (change_url change)"
            )
        },
    )

    use_logrotate = BooleanField(
        _("Use logrotate for the app logs"),
        default=True,
        render_kw={
            "title": _(
                "If the app generates logs, this option permit to handle their archival. Recommended."
            )
        },
    )
    # TODO : specify custom log file
    # custom_log_file = "/var/log/$app/$app.log" "/var/log/nginx/${domain}-error.log"
    use_fail2ban = BooleanField(
        _(
            "Protect the application against brute force attacks (via fail2ban)"
        ),
        default=False,
        render_kw={
            "title": _(
                "If the app generates failed connexions logs, this option allows to automatically banish the related IP after a certain number of failed password tries. Recommended."
            )
        },
    )
    use_cron = BooleanField(
        _("Add a CRON task for this application"),
        description=_("Corresponds to some app periodic operations"),
        default=False,
    )
    cron_config_file = TextAreaField(
        _("Type the CRON file content"),
        validators=[Optional()],
        render_kw={
            "class": "form-control",
            "spellcheck": "false",
        },
    )

    fail2ban_regex = StringField(
        _("Regular expression for fail2ban"),
        # Regex to match into the log for a failed login
        validators=[Optional()],
        render_kw={
            "placeholder": _("A regular expression"),
            "class": "form-control",
            "title": _(
                "Regular expression to check in the log file to activate failban (search for a line that indicates a credentials error)."
            ),
        },
    )


## Main form
class GeneratorForm(
    GeneralInfos,
    IntegrationInfos,
    UpstreamInfos,
    InstallQuestions,
    Ressources,
    SpecificTechnology,
    AppConfig,
    Documentation,
    MoreAdvanced,
):

    class Meta:
        csrf = False

    generator_mode = SelectField(
        _("Generator mode"),
        description=_(
            "In tutorial version, the generated app will contain additionnal comments to ease the understanding. In steamlined version, the generated app will only contain the necessary minimum."
        ),
        choices=[
            ("simple", _("Streamlined version")),
            ("tutorial", _("Tutorial version")),
        ],
        default="true",
        validators=[DataRequired()],
    )

    submit_preview = SubmitField(_("Previsualise"))
    submit_download = SubmitField(_("Download the .zip"))
    submit_demo = SubmitField(
        _("Fill with demo values"),
        render_kw={
            "onclick": "fillFormWithDefaultValues()",
            "title": _(
                "Generate a complete and functionnal minimalistic app that you can iterate from"
            ),
        },
    )


#### Web pages
@app.route("/", methods=["GET", "POST"])
def main_form_route():

    main_form = GeneratorForm()
    app_files = []

    if request.method == "POST":

        if not main_form.validate_on_submit():
            print("Form not validated?")
            print(main_form.errors)

            return render_template(
                "index.html",
                main_form=main_form,
                generator_info=GENERATOR_DICT,
                generated_files={},
            )

        if main_form.submit_preview.data:
            submit_mode = "preview"
        elif main_form.submit_demo.data:
            submit_mode = "demo"  # TODO : for now this always trigger a preview. Not sure if that's an issue
        else:
            submit_mode = "download"

        class AppFile:
            def __init__(self, id_, destination_path=None):
                self.id = id_
                self.destination_path = destination_path
                self.content = None

        app_files = [
            AppFile("manifest", "manifest.toml"),
            AppFile("tests", "tests.toml"),  # TODO test this
            AppFile("_common.sh", "scripts/_common.sh"),
            AppFile("install", "scripts/install"),
            AppFile("remove", "scripts/remove"),
            AppFile("backup", "scripts/backup"),
            AppFile("restore", "scripts/restore"),
            AppFile("upgrade", "scripts/upgrade"),
            AppFile("nginx", "conf/nginx.conf"),
        ]

        if main_form.enable_change_url.data:
            app_files.append(AppFile("change_url", "scripts/change_url"))

        if main_form.main_technology.data not in ["none", "php"]:
            app_files.append(AppFile("systemd", "conf/systemd.service"))

        # TODO : buggy, tries to open php.j2
        # if main_form.main_technology.data == "php":
        # app_files.append(AppFile("php", "conf/extra_php-fpm.conf"))

        if main_form.description.data:
            app_files.append(AppFile("DESCRIPTION", "doc/DESCRIPTION.md"))

        if main_form.pre_install.data:
            app_files.append(AppFile("PRE_INSTALL", "doc/PRE_INSTALL.md"))

        if main_form.post_install.data:
            app_files.append(AppFile("POST_INSTALL", "doc/POST_INSTALL.md"))

        if main_form.pre_upgrade.data:
            app_files.append(AppFile("PRE_UPGRADE", "doc/PRE_UPGRADE.md"))

        if main_form.post_upgrade.data:
            app_files.append(AppFile("POST_UPGRADE", "doc/POST_UPGRADE.md"))

        if main_form.admin.data:
            app_files.append(AppFile("ADMIN", "doc/ADMIN.md"))

        template_dir = os.path.dirname(__file__) + "/templates/"
        for app_file in app_files:
            template = open(template_dir + app_file.id + ".j2").read()
            app_file.content = render_template_string(
                template, data=dict(request.form | GENERATOR_DICT)
            )
            app_file.content = re.sub(r"\n\s+$", "\n", app_file.content, flags=re.M)
            app_file.content = re.sub(r"\n{3,}", "\n\n", app_file.content, flags=re.M)

        print(main_form.use_custom_config_file.data)
        if main_form.use_custom_config_file.data:
            app_files.append(
                AppFile("appconf", "conf/" + main_form.custom_config_file.data)
            )
            app_files[-1].content = main_form.custom_config_file_content.data
            print(main_form.custom_config_file.data)
            print(main_form.custom_config_file_content.data)

        # TODO : same for cron job
        if submit_mode == "download":
            # Generate the zip file
            f = BytesIO()
            with zipfile.ZipFile(f, "w") as zf:
                print("Exporting zip archive for app: " + request.form["app_id"])
                for app_file in app_files:
                    print(app_file.id)
                    zf.writestr(app_file.destination_path, app_file.content)
            f.seek(0)
            # Send the zip file to the user
            return send_file(
                f, as_attachment=True, download_name=request.form["app_id"] + ".zip"
            )

    return render_template(
        "index.html",
        main_form=main_form,
        generator_info=GENERATOR_DICT,
        generated_files=app_files,
    )


# Localisation
@app.route("/language/<language>")
def set_language(language=None):
    response = make_response(redirect(request.referrer or "/"))
    response.set_cookie("lang", language)
    return response


#### Running the web server
if __name__ == "__main__":
    app.run(debug=True)
