#### Imports
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
from flask_bootstrap import Bootstrap
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

# Markdown to HTML - for debugging purposes
from misaka import Markdown, HtmlRenderer

# Managing zipfiles
import zipfile
from flask_cors import CORS
from urllib import parse
from secrets import token_urlsafe

#### Create FLASK and Jinja Environments
app = Flask(__name__)
Bootstrap(app)
app.config["SECRET_KEY"] = token_urlsafe(16)  # Necessary for the form CORS
cors = CORS(app)

environment = j2.Environment(loader=j2.FileSystemLoader("templates/"))


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


## PHP forms
class Form_PHP(FlaskForm):
    use_php = BooleanField("Nécessite PHP", default=False)
    php_config_file = SelectField(
        "Type de fichier PHP",
        choices=[
            (
                "php-fpm.conf",
                Markup(
                    'Fichier de configuration PHP complet <i class="grayed_hint">(php-fpm.conf)</i>'
                ),
            ),
            (
                "php_extra-fpm.conf",
                Markup(
                    'Fichier de configuration PHP particulier <i class ="grayed_hint">(extra_php-fpm.conf)</i>'
                ),
            ),
        ],
        default="php_extra-fpm.conf",
        validators=[DataRequired()],
    )
    ## TODO : figure out how to include these comments/title values
    # 'title': 'Remplace la configuration générée par défaut par un fichier de configuration complet. À éviter si possible.
    # 'title': "Choisir un fichier permettant un paramétrage d'options complémentaires. C'est généralement recommandé."

    php_config_file_content = TextAreaField(
        "Saisissez le contenu du fichier de configuration PHP",
        validators=[Optional()],
        render_kw={
            "class": "form-control",
            "style": "width: 50%;height:11em;min-height: 5.5em; max-height: 55em;flex-grow: 1;box-sizing: border-box;",
            "title": "TODO",
            "placeholder": "; Additional php.ini defines, specific to this pool of workers. \n\nphp_admin_value[upload_max_filesize] = 100M \nphp_admin_value[post_max_size] = 100M",
        },
    )


## NodeJS forms
class Form_NodeJS(FlaskForm):
    use_nodejs = BooleanField("Nécessite NodeJS", default=False)
    use_nodejs_version = StringField(
        "Version de NodeJS",
        render_kw={
            "placeholder": "20",
            "class": "form-control",
            "title": "Saisissez la version de NodeJS à installer. Cela peut-être une version majeure (ex: 20) ou plus précise (ex: 20.1).",
        },
    )  # TODO : this should be validated using a regex, should be only numbers and any (≥0) number of dots in between
    use_nodejs_needs_yarn = BooleanField(
        "Nécessite Yarn",
        default=False,
        render_kw={
            "title": "Faut-il installer automatiquement Yarn ? Cela configurera les dépôts spécifiques à Yarn."
        },
    )


## Python forms


class Form_Python(FlaskForm):
    use_python = BooleanField(
        "Nécessite Python", default=False
    )  ## TODO -> python3, python3-pip, python3-ven dependencies by default
    python_dependencies_type = SelectField(
        "Configuration des dépendances Python",
        choices=[
            ("requirements.txt", Markup("Fichier <i>requirements.txt</i>")),
            ("manual_list", "Liste manuelle"),
        ],
        default="requirements.txt",
        validators=[DataRequired(), Optional()],
    )
    python_requirements = TextAreaField(
        "La liste de dépendances inclue dans le fichier requirements.txt",
        render_kw={
            "class": "form-control",
            "style": "width: 50%;height:5.5em;min-height: 5.5em; max-height: 55em;flex-grow: 1;box-sizing: border-box;",
            "title": "Lister les dépendances à installer, une par ligne, avec un numéro de version derrière.\nEx: 'dépendance==1.0'.",
            "placeholder": "tensorflow==2.3.1 \nuvicorn==0.12.2 \nfastapi==0.63.0",
        },
    )
    python_dependencies_list = StringField(
        "Liste de dépendances python",
        render_kw={
            "placeholder": "tensorflow uvicorn fastapi",
            "class": "form-control",
            "title": "Lister les dépendances à installer, séparées d'un espace.",
        },
    )

class GeneralInfos(FlaskForm):

    app_id = StringField(
        Markup(
            "Identifiant (id) de l'application"
        ),
        description="En minuscule et sans espace.",
        validators=[DataRequired(), Regexp("[a-z_1-9]+.*(?<!_ynh)$")],
        render_kw={
            "placeholder": "my_super_app",
        },
    )

    app_name = StringField(
        "Nom de l'application",
        description="Il s'agit du nom l'application, affiché dans les interfaces utilisateur·ice·s",
        validators=[DataRequired()],
        render_kw={
            "placeholder": "My super App",
        },
    )

    description_en = TextAreaField(
        "Description courte (en)",
        description="Expliquez en *quelques* (10~15) mots l'utilité de l'app ou ce qu'elle fait (l'objectif est de donner une idée grossière pour des utilisateurs qui naviguent dans un catalogue de 100+ apps)",
        validators=[DataRequired()],
    )
    description_fr = TextAreaField(
        "Description courte (fr)",
        description="Expliquez en *quelques* (10~15) mots l'utilité de l'app ou ce qu'elle fait (l'objectif est de donner une idée grossière pour des utilisateurs qui naviguent dans un catalogue de 100+ apps)",
        validators=[DataRequired()],
    )

class IntegrationInfos(FlaskForm):

    # TODO : people shouldnt have to put the ~ynh1 ? This should be added automatically when rendering the app files ?
    version = StringField(
        "Version",
        validators=[Regexp("\d{1,4}.\d{1,4}(.\d{1,4})?(.\d{1,4})?~ynh\d+")],
        render_kw={"placeholder": "1.0~ynh1"},
    )

    maintainers = StringField(
        "Mainteneur·euse de l'app YunoHost créée",
        description="Généralement vous mettez votre nom ici… Si vous êtes d'accord ;)"
    )

    yunohost_required_version = StringField(
        "Minimum YunoHost version",
        description="Version minimale de Yunohost pour que l'application fonctionne.",
        render_kw={
            "placeholder": "11.1.21",
        },
    )

    architectures = SelectMultipleField(
        "Architectures supportées",
        choices=[
            ("all", "Toutes les architectures"),
            ("amd64", "amd64"),
            ("i386", "i386"),
            ("armhf", "armhf"),
            ("arm64", "arm64"),
        ],
        default=["all"],
        validators=[DataRequired()],
    )

    multi_instance = BooleanField(
        "L'app pourra être installée simultannément plusieurs fois sur la même machine",
        default=True,
    )

    ldap = SelectField(
        "L'app s'intègrera avec le LDAP",
        description="c-à-d pouvoir se connecter en utilisant ses identifiants YunoHost",
        choices=[
            ("false", "No"),
            ("true", "Yes"),
            ("not_relevant", "Not relevant"),
        ],
        default="not_relevant",
        validators=[DataRequired()],
    )
    sso = SelectField(
        "L'app s'intègrera avec le SSO (Single Sign On) de YunoHost",
        description="c-à-d être connecté automatiquement à l'app si connecté au portail YunoHost",
        choices=[
            ("false", "Yes"),
            ("true", "No"),
            ("not_relevant", "Not relevant"),
        ],
        default="not_relevant",
        validators=[DataRequired()],
    )


class UpstreamInfos(FlaskForm):

    license = StringField(
        "Licence",
        description="You should check this on the upstream repository. The expected format is a SPDX id listed in https://spdx.org/licenses/",
        validators=[DataRequired()],
    )

    website = StringField(
        "Site web officiel",
        description="Leave empty if there is no official website",
        validators=[URL(), Optional()],
        render_kw={
            "placeholder": "https://awesome-app-website.com",
        },
    )
    demo = StringField(
        "Démo officielle de l'app",
        description="Leave empty if there is no official demo",
        validators=[URL(), Optional()],
        render_kw={
            "placeholder": "https://awesome-app-website.com/demo",
        },
    )
    admindoc = StringField(
        "Documentation d'aministration",
        description="Leave empty if there is no official admin doc",
        validators=[URL(), Optional()],
        render_kw={
            "placeholder": "https://awesome-app-website.com/doc/admin",
        },
    )
    userdoc = StringField(
        "Documentation d'utilisation",
        description="Leave empty if there is no official user doc",
        validators=[URL(), Optional()],
        render_kw={
            "placeholder": "https://awesome-app-website.com/doc/user",
        },
    )
    code = StringField(
        "Dépôt de code",
        validators=[URL(), DataRequired()],
        render_kw={
            "placeholder": "https://some.git.forge/org/app",
        },
    )

class InstallQuestions(FlaskForm):

    domain_and_path = SelectField(
        "Demander l'URL sur laquelle sera installée l'app (variables 'domain' et 'path')",
        default="true",
        choices=[
            ("true", "Demander le domaine+path"),
            ("full_domain", "Demander le domaine uniquement (l'app nécessite d'être installée à la racine d'un domaine dédié à cette app)"),
            ("false", "Ne pas demander (l'app n'est pas une webapp)")
        ],
    )

    init_main_permission = BooleanField(
        "Demander qui pourra accéder à l'app (parmi visitors/all_users/admins)",
        default=True,
    )

    init_admin_permission = BooleanField(
        "Demander qui pourra accéder à l'interface d'admin (ceci suppose que l'app dispose d'une interface d'admin)",
        default=False,
    )

    # admin_password_help_message = BooleanField("TODO ", default=False,
    #                           render_kw={"class": "",
    #                                      "title": "TODO"})

    language = SelectMultipleField(
        "Langues supportées",
        choices=[
            ("_", "None / not relevant"),
            ("en", "English"),
            ("fr", "Français"),
            ("en", "Spanish"),
            ("it", "Italian"),
            ("de", "German"),
            ("zh", "Chinese"),
            ("jp", "Japanese"),
            ("da", "Danish"),
            ("pt", "Portugese"),
            ("nl", "Dutch"),
            ("ru", "Russian"),
        ],
        default=["_"],
        validators=[DataRequired()],
    )



# manifest
class Resources(FlaskForm):


   # Sources
    source_url = StringField(
        "Code source ou exécutable de l'application",
        validators=[DataRequired(), URL()],
        render_kw={
            "placeholder": "https://github.com/foo/bar/archive/refs/tags/v1.2.3.tar.gz",
        },
    )
    sha256sum = StringField(
        "Checksum sha256 des sources",
        validators=[DataRequired(), Length(min=64, max=64)],
        render_kw={
            "placeholder": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
        },
    )

    auto_update = BooleanField(
        "Activer le robot de mise à jour automatique des sources",
        description="Si le logiciel est disponible sur github et publie des releases ou des tags pour ses nouvelles versions, un robot proposera automatiquement des mises à jour de l'url et de la checksum.",
        default=False,
    )

    ## TODO
    # These infos are used by https://github.com/YunoHost/apps/blob/master/tools/autoupdate_app_sources/autoupdate_app_sources.py
    # to auto-update the previous asset urls and sha256sum + manifest version
    # assuming the upstream's code repo is on github and relies on tags or releases
    # See the 'sources' resource documentation for more details

    # autoupdate.strategy = "latest_github_tag"



    apt_dependencies = StringField(
        "Dépendances à installer via apt (séparées par des virgules et/ou espaces)",
        render_kw={
            "placeholder": "foo, bar2.1-ext, libwat",
        },
    )

    database = SelectField(
        "Initialiser une base de données",
        choices=[
            ("false", "Non"),
            ("mysql", "MySQL/MariaDB"),
            ("postgresql", "PostgreSQL"),
        ],
        default="false",
    )

    system_user = BooleanField(
        "Initialiser un utilisateur système pour cet app",
        default=True,
    )

    install_dir = BooleanField(
        "Initialiser un dossier d'installation de l'app (typiquement /var/www/$app)",
        default=True,
    )

    data_dir = BooleanField(
        "Initialiser un dossier pour les données de l'app (typiquement /home/yunohost.app/$app)",
        default=False,
    )

    ports = BooleanField(
        "L'app aura besoin d'un port interne pour le reverse proxy entre nginx et l'app",
        description="(généralement pas nécessaire pour les apps statiques ou php, mais généralement nécessaire pour les apps de type nodejs, python, ruby, ...)",
    )

## Main form
class GeneratorForm(
    GeneralInfos, IntegrationInfos, UpstreamInfos, InstallQuestions, Resources,
    Form_PHP, Form_NodeJS, Form_Python
):
    generator_mode = SelectField(
        "Mode du générateur",
        description="En mode tutoriel, l'application générée contiendra des commentaires additionnels pour faciliter la compréhension. En version épurée, l'application générée ne contiendra que le minimum nécessaire.",
        choices=[("false", "Version épurée"), ("true", "Version tutoriel")],
        default="true",
        validators=[DataRequired()],
    )



    supports_change_url = BooleanField(
        "L'application autorise le changement d'adresse (changement de domaine ou de chemin)",
        default=True,
        render_kw={
            "title": "Faut-il permettre le changement d'URL pour l'application ? (fichier change_url)"
        },
    )

    use_logrotate = BooleanField(
        "Utiliser logrotate pour gérer les journaux",
        default=True,
        render_kw={
            "title": "Si l'application genère des journaux (log), cette option permet d'en gérer l'archivage. Recommandé."
        },
    )
    # TODO : specify custom log file
    # custom_log_file = "/var/log/$app/$app.log" "/var/log/nginx/${domain}-error.log"
    use_fail2ban = BooleanField(
        "Protéger l'application des attaques par force brute (via fail2ban)",
        default=True,
        render_kw={
            "title": "Si l'application genère des journaux (log) d'erreurs de connexion, cette option permet de bannir automatiquement les IP au bout d'un certain nombre d'essais de mot de passe. Recommandé."
        },
    )
    use_cron = BooleanField(
        "Ajouter une tâche CRON pour cette application",
        default=False,
        render_kw={
            "title": "Créer une tâche cron pour gérer des opérations périodiques de l'application."
        },
    )
    cron_config_file = TextAreaField(
        "Saisissez le contenu du fichier CRON",
        validators=[Optional()],
        render_kw={
            "class": "form-control",
            "style": "width: 50%;height:22em;min-height: 5.5em; max-height: 55em;flex-grow: 1;box-sizing: border-box;",
            "title": "Saisir le contenu du fichier de la tâche CRON.",
        },
    )

    fail2ban_regex = StringField(
        "Expression régulière pour fail2ban",
        # Regex to match into the log for a failed login
        validators=[Optional()],
        render_kw={
            "placeholder": "A regular expression",
            "class": "form-control",
            "title": "Expression régulière à vérifier dans le journal pour que fail2ban s'active (cherchez une ligne qui indique une erreur d'identifiants deconnexion).",
        },
    )

    nginx_config_file = TextAreaField(
        "Saisissez le contenu du fichier de configuration du serveur NGINX",
        validators=[Optional()],
        render_kw={
            "class": "form-control",
            "style": "width: 50%;height:22em;min-height: 5.5em; max-height: 55em;flex-grow: 1;box-sizing: border-box;",
            "title": "Saisir le contenu du fichier de configuration du serveur NGINX.",
            "placeholder": "location __PATH__/ {\n    \n    proxy_pass       http://127.0.0.1:__PORT__;\n    proxy_set_header X-Real-IP $remote_addr;\n    proxy_set_header Host $host;\n    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;\n    \n    # Include SSOWAT user panel.\n    include conf.d/yunohost_panel.conf.inc;\n    }",
        },
    )

    use_systemd_service = BooleanField(
        "Utiliser un service système (via systemd) pour gérer le fonctionnement de l'application ",
        default=False,
        render_kw={
            "title": "Un service systemd s'occupera de démarrer l'application avec le système, et permettra de l'arrêter ou la redémarrer. Recommandé."
        },
    )
    systemd_config_file = TextAreaField(
        "Saisissez le contenu du fichier de configuration du service SystemD",
        validators=[Optional()],
        render_kw={
            "class": "form-control",
            "style": "width: 50%;height:22em;min-height: 5.5em; max-height: 55em;flex-grow: 1;box-sizing: border-box;",
            "title": "Saisir le contenu du fichier de configuration du service systemd.",
        },
    )
    systemd_service_description = StringField(
        "Description du service de l'application",
        validators=[Optional()],
        render_kw={
            "placeholder": "A short description of the app",
            "class": "form-control",
            "style": "width: 30%;",
            "title": "Décrire en une ligne ce que fait ce service. Ceci sera affiché dans l'interface d'administration.",
        },
    )

    use_custom_config_file = BooleanField(
        "Utiliser un fichier de configuration personnalisé ",
        default=False,
        render_kw={
            "title": "Est-ce que l'application nécessite un fichier de configuration personnalisé ? (du type .env, config.json, parameters.yaml, …)"
        },
    )

    custom_config_file = StringField(
        "Nom du fichier à utiliser",
        validators=[Optional()],
        render_kw={
            "placeholder": "config.json",
            "class": "form-control",
            "style": "width: 30%;",
            "title": "Décrire en une ligne ce que fait ce service. Ceci sera affiché dans l'interface d'administration.",
        },
    )

    custom_config_file_content = TextAreaField(
        "Saisissez le contenu du fichier de configuration personnalisé",
        validators=[Optional()],
        render_kw={
            "class": "form-control",
            "style": "width: 50%;height:22em;min-height: 5.5em; max-height: 55em;flex-grow: 1;box-sizing: border-box;",
            "title": "Saisir le contenu du fichier de configuration personnalisé.",
        },
    )

    submit = SubmitField("Soumettre")


#### Web pages
@app.route("/", methods=["GET", "POST"])
def main_form_route():

    parameters = {}
    main_form = GeneratorForm()

    if request.method == "POST":
        result = request.form
        results = dict(result)
        # print("[DEBUG] This is a POST request")
        # print(results)
        for key, value in results.items():
            parameters[key] = value
        parameters["preview"] = True
        if main_form.validate_on_submit():
            parameters["invalid_form"] = False
            print()
            print("formulaire valide")
            # print(main_form.data.items())

            for key, value in main_form.data.items():
                parameters[key] = value  # TODO change the name

            templates = (
                "templates/manifest.j2",
                "templates/install.j2",
                "templates/remove.j2",
                "templates/backup.j2",
                "templates/restore.j2",
                "templates/upgrade.j2",
                "templates/config.j2",
                "templates/change_url.j2",
                "templates/_common.sh.j2",
            )
            markdown_to_html = dict()
            for template in templates:
                markdown_content, html_content = markdown_file_to_html_string(template)
                template_key = template.split("templates/")[1].split(".j2")[
                    0
                ]  # Let's retrieve what's the exact template used
                markdown_to_html[template_key] = {
                    "markdown_content": markdown_content,
                    "html_content": html_content,
                }
                # print(markdown_to_html["markdown_content"])
                # print(markdown_to_html["html_content"])

            ## Prepare the file contents for the download button
            # print(markdown_to_html['manifest']['markdown_content'])

            # Workaround so /download_zip can access the content - FIXME ?
            global template_manifest_content
            global template_install_content
            global template_remove_content
            global template_backup_content
            global template_restore_content
            global template_upgrade_content
            global template_config_content
            global template_change_url_content
            global template_common_sh_content
            global custom_config_file
            global nginx_config_file
            global systemd_config_file
            global cron_config_file

            template_manifest_content = render_template_string(
                markdown_to_html["manifest"]["markdown_content"],
                parameters=parameters,
                main_form=main_form,
            )

            template_install_content = render_template_string(
                markdown_to_html["install"]["markdown_content"],
                parameters=parameters,
                main_form=main_form,
                markdown_to_html=markdown_to_html["install"],
            )

            template_remove_content = render_template_string(
                markdown_to_html["remove"]["markdown_content"],
                parameters=parameters,
                main_form=main_form,
                markdown_to_html=markdown_to_html["remove"],
            )

            template_backup_content = render_template_string(
                markdown_to_html["backup"]["markdown_content"],
                parameters=parameters,
                main_form=main_form,
                markdown_to_html=markdown_to_html["backup"],
            )

            template_restore_content = render_template_string(
                markdown_to_html["restore"]["markdown_content"],
                parameters=parameters,
                main_form=main_form,
                markdown_to_html=markdown_to_html["restore"],
            )

            template_upgrade_content = render_template_string(
                markdown_to_html["upgrade"]["markdown_content"],
                parameters=parameters,
                main_form=main_form,
                markdown_to_html=markdown_to_html["upgrade"],
            )

            template_config_content = render_template_string(
                markdown_to_html["config"]["markdown_content"],
                parameters=parameters,
                main_form=main_form,
                markdown_to_html=markdown_to_html["config"],
            )

            template_common_sh_content = render_template_string(
                markdown_to_html["_common.sh"]["markdown_content"],
                parameters=parameters,
                main_form=main_form,
                markdown_to_html=markdown_to_html["_common.sh"],
            )

            if parameters["supports_change_url"]:
                template_change_url_content = render_template_string(
                    markdown_to_html["change_url"]["markdown_content"],
                    parameters=parameters,
                    main_form=main_form,
                    markdown_to_html=markdown_to_html["change_url"],
                )
            else:
                template_change_url_content = False

            print(parameters["custom_config_file"])
            print(parameters["use_custom_config_file"])
            return render_template(
                "index.html",
                parameters=parameters,
                main_form=main_form,
                markdown_to_html=markdown_to_html,
                template_manifest_content=template_manifest_content,
                template_install_content=template_install_content,
                template_remove_content=template_remove_content,
                template_backup_content=template_backup_content,
                template_restore_content=template_restore_content,
                template_upgrade_content=template_upgrade_content,
                template_config_content=template_config_content,
                template_change_url_content=template_change_url_content,
                template_common_sh_content=template_common_sh_content,
                nginx_config_file=parameters["nginx_config_file"],
                systemd_config_file=parameters["systemd_config_file"],
                custom_config_file=parameters["custom_config_file"],
                cron_config_file=parameters["cron_config_file"],
            )
        else:
            print("[DEBUG] Formulaire invalide: ", main_form.errors)
            parameters["preview"] = False
            parameters["invalid_form"] = True

    elif request.method == "GET":
        parameters["preview"] = False

    return render_template(
        "index.html", parameters=parameters, main_form=main_form
    )


@app.route("/download_zip", methods=("GET", "POST"))
def telecharger_zip():
    # Retrieve arguments
    print("Génération du .zip")
    app_id = request.args.get("app_id")
    print("Génération du .zip pour " + app_id)

    custom_config_file = parse.unquote(request.args.get("custom_config_file"))
    custom_config_file_content = parse.unquote(
        request.args.get("custom_config_file_content")
    )
    systemd_config_file = parse.unquote(request.args.get("systemd_config_file"))
    nginx_config_file = parse.unquote(request.args.get("nginx_config_file"))
    cron_config_file = parse.unquote(request.args.get("cron_config_file"))

    global template_manifest_content
    global template_install_content
    global template_remove_content
    global template_backup_content
    global template_restore_content
    global template_upgrade_content
    global template_config_content
    global template_change_url_content
    global template_common_sh_content

    # global custom_config_file

    use_php = request.args.get("use_php")
    print("PHP")
    print(use_php)
    php_config_file = parse.unquote(request.args.get("php_config_file"))
    php_config_file_content = parse.unquote(request.args.get("php_config_file_content"))

    archive_name = (
        app_id + ".zip"
    )  # Actually it's the javascript that decide of the filename… this is only an internal name

    # Generate the zip file (will be stored in the working directory)
    with zipfile.ZipFile(archive_name, "w") as zf:
        # Add text in directly in the ZIP, as a file
        zf.writestr("manifest.toml", template_manifest_content)
        zf.writestr("scripts/install", template_install_content)
        zf.writestr("scripts/remove", template_remove_content)
        zf.writestr("scripts/backup", template_backup_content)
        zf.writestr("scripts/restore", template_restore_content)
        zf.writestr("scripts/upgrade", template_upgrade_content)
        zf.writestr("scripts/_common_sh", template_common_sh_content)

        if template_config_content:
            zf.writestr("scripts/config", template_config_content)
        if template_change_url_content:
            zf.writestr("scripts/change_url", template_change_url_content)
        if custom_config_file:
            zf.writestr("conf/" + custom_config_file, custom_config_file_content)
        if systemd_config_file:
            zf.writestr("conf/systemd.service", systemd_config_file)
        if nginx_config_file:
            zf.writestr("conf/nginx.conf", nginx_config_file)
        if cron_config_file:
            zf.writestr("conf/task.conf", cron_config_file)
        if use_php == "True":
            zf.writestr("conf/" + php_config_file, php_config_file_content)

    # Send the zip file to the user
    return send_file(archive_name, as_attachment=True)


#### Running the web server
if __name__ == "__main__":
    app.run(debug=True)
