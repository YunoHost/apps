#### Imports
import jinja2 as j2
from flask import Flask, render_template, render_template_string, request, redirect, flash, send_file
from markupsafe import Markup  # No longer imported from Flask
# Form libraries
from flask_wtf import FlaskForm
from wtforms import StringField, RadioField, SelectField, SubmitField, TextAreaField, BooleanField, SelectMultipleField
from wtforms.validators import DataRequired, InputRequired, Optional, Regexp, URL, Length
# Markdown to HTML - for debugging purposes
from misaka import Markdown, HtmlRenderer
# Managing zipfiles
import zipfile
from flask_cors import CORS
from urllib import parse
from secrets import token_urlsafe

#### GLOBAL VARIABLES
YOLOGEN_VERSION = '0.7.5'
GENERATOR_DICT = {'GENERATOR_VERSION': YOLOGEN_VERSION}

#### Create FLASK and Jinja Environments
url_prefix = ''
# url_prefix = '/yunohost-app-generator'

# app = Flask(__name__)
app = Flask(__name__)  # Blueprint('main', __name__, url_prefix=url_prefix)
app.config['SECRET_KEY'] = token_urlsafe(16)  # Necessary for the form CORS
cors = CORS(app)

environment = j2.Environment(loader=j2.FileSystemLoader("templates/"))


#### Custom functions

# Define custom filter
@app.template_filter('render_markdown')
def render_markdown(text):
    renderer = HtmlRenderer()
    markdown = Markdown(renderer)
    return markdown(text)


# Add custom filter
j2.filters.FILTERS['render_markdown'] = render_markdown


# Converting markdown to html
def markdown_file_to_html_string(file):
    with open(file, 'r') as file:
        markdown_content = file.read()
        # Convert content from Markdown to HTML
        html_content = render_markdown(markdown_content)
        # Return Markdown and HTML contents
        return markdown_content, html_content


### Forms

## PHP forms
class Form_PHP_Config(FlaskForm):
    php_config_file = SelectField('Type de fichier PHP :', choices=[
            ('php-fpm.conf', Markup('Fichier de configuration PHP complet <i class="grayed_hint">(php-fpm.conf)</i>')),
            ('php_extra-fpm.conf',
             Markup('Fichier de configuration PHP particulier <i class ="grayed_hint">(extra_php-fpm.conf)</i>'))],
                                  default='php_extra-fpm.conf', validators=[DataRequired()])
    ## TODO : figure out how to include these comments/title values
    # 'title': 'Remplace la configuration générée par défaut par un fichier de configuration complet. À éviter si possible.
    # 'title': "Choisir un fichier permettant un paramétrage d'options complémentaires. C'est généralement recommandé."

    php_config_file_content = TextAreaField("Saisissez le contenu du fichier de configuration PHP :",
                                            validators=[Optional()],
                                            render_kw={"class": "form-control",
                                                       "style": "width: 50%;height:11em;min-height: 5.5em; max-height: 55em;flex-grow: 1;box-sizing: border-box;",
                                                       "title": "TODO",
                                                       "placeholder": "; Additional php.ini defines, specific to this pool of workers. \n\nphp_admin_value[upload_max_filesize] = 100M \nphp_admin_value[post_max_size] = 100M"})


class Form_PHP(Form_PHP_Config):
    use_php = BooleanField('Nécessite PHP', default=False)


## NodeJS forms
class Form_NodeJS(FlaskForm):
    use_nodejs = BooleanField('Nécessite NodeJS', default=False)
    use_nodejs_version = StringField("Version de NodeJS :",
                                     render_kw={"placeholder": "20", "class": "form-control",
                                                "title": "Saisissez la version de NodeJS à installer. Cela peut-être une version majeure (ex: 20) ou plus précise (ex: 20.1)."})  # TODO : this should be validated using a regex, should be only numbers and any (≥0) number of dots in between
    use_nodejs_needs_yarn = BooleanField('Nécessite Yarn', default=False, render_kw={
            "title": "Faut-il installer automatiquement Yarn ? Cela configurera les dépôts spécifiques à Yarn."})


## Python forms

class Form_Python(FlaskForm):
    use_python = BooleanField('Nécessite Python',
                              default=False)  ## TODO -> python3, python3-pip, python3-ven dependencies by default
    python_dependencies_type = SelectField('Configuration des dépendances Python :', choices=[
            ('requirements.txt', Markup('Fichier <i>requirements.txt</i>')),
            ('manual_list', 'Liste manuelle')],
                                           default='requirements.txt', validators=[DataRequired(), Optional()])
    python_requirements = TextAreaField("La liste de dépendances inclue dans le fichier requirements.txt :",
                                        render_kw={"class": "form-control",
                                                   "style": "width: 50%;height:5.5em;min-height: 5.5em; max-height: 55em;flex-grow: 1;box-sizing: border-box;",
                                                   "title": "Lister les dépendances à installer, une par ligne, avec un numéro de version derrière.\nEx: 'dépendance==1.0'.",
                                                   "placeholder": "tensorflow==2.3.1 \nuvicorn==0.12.2 \nfastapi==0.63.0"})
    python_dependencies_list = StringField("Liste de dépendances python :",
                                           render_kw={"placeholder": "tensorflow uvicorn fastapi",
                                                      "class": "form-control",
                                                      "title": "Lister les dépendances à installer, séparées d'un espace."})


## Manifest form
# Dependencies form
class DependenciesForm(FlaskForm):
    auto_update = BooleanField("Activer le robot de mise à jour automatiques  :", default=False,
                               render_kw={
                                       "title": "Si le logiciel est disponible sur github et publie des releases ou des tags pour ses nouvelles versions, un robot proposera automatiquement des mises à jours."})

    ## TODO
    # These infos are used by https://github.com/YunoHost/apps/blob/master/tools/autoupdate_app_sources/autoupdate_app_sources.py
    # to auto-update the previous asset urls and sha256sum + manifest version
    # assuming the upstream's code repo is on github and relies on tags or releases
    # See the 'sources' resource documentation for more details

    # autoupdate.strategy = "latest_github_tag"

    dependencies = StringField("Dépendances de l'application (liste des paquets apt) à installer :",
                               render_kw={"placeholder": "foo foo2.1-ext somerandomdep", "class": "form-control",
                                          "title": "Lister les paquets dont dépend l'application, séparés par un espace."})

    use_db = SelectField("Configurer une base de données :", choices=[
            ('false', "Non"),
            ('mysql', "MySQL/MariaDB"),
            ('postgresql', "PostgreSQL")],
                         default='false',
                         render_kw={"title": "L'application nécessite-t-elle une base de données ?"})


# manifest
class manifestForm(DependenciesForm):
    version = StringField('Version', validators=[Regexp('\d{1,4}.\d{1,4}(.\d{1,4})?(.\d{1,4})?~ynh\d+')],
                          render_kw={"class": "form-control",
                                     "placeholder": "1.0~ynh1"})
    description_en = TextAreaField("Description en quelques lignes de l'application, en anglais :",
                                   validators=[DataRequired()],
                                   render_kw={"class": "form-control", "style": "resize: none;",
                                              "title": "Explain in *a few (10~15) words* the purpose of the app \\"
                                                       "or what it actually does (it is meant to give a rough idea to users browsing a catalog of 100+ apps)"})
    description_fr = TextAreaField("Description en quelques lignes de l'application :", validators=[DataRequired()],
                                   render_kw={"class": "form-control", "style": "resize: none;",
                                              "title": "Expliquez en *quelques* (10~15) mots l'utilité de l'app \\"
                                                       "ou ce qu'elle fait (l'objectif est de donner une idée grossière pour des utilisateurs qui naviguent dans un catalogue de 100+ apps)"})

    # TODO : handle multiple names separated by commas (.split(',') ?
    maintainers = StringField('Mainteneurs et mainteneuses', render_kw={"class": "form-control",
                                                                        "placeholder": "Généralement vous mettez votre nom ici… Si vous êtes d'accord ;)"})  # TODO : Usually you put your name here… if you like ;)
    architectures = SelectMultipleField('Architectures supportées :', choices=[
            ('all', 'Toutes les architectures'),
            ('amd64', 'amd64'),
            ('arm64', 'arm64'),
            ('i386', 'i386'),
            ('todo', 'TODO : list more architectures')],
                                        default=['all'], validators=[DataRequired()])
    yunohost_required_version = StringField('Mainteneurs et mainteneuses', render_kw={"class": "form-control",
                                                                                      "placeholder": "11.1.21",
                                                                                      "title": "Version minimale de Yunohost pour que l'application fonctionne."})

    multi_instance = BooleanField("Application multi-instance", default=False,
                                  render_kw={"class": "",
                                             "title": "Peux-t-on installer simultannément plusieurs fois l'application sur un même serveur ?"})

    ldap = SelectField('Integrate with LDAP (user can login using Yunohost credentials :', choices=[
            ('false', 'False'),
            ('true', 'True'),
            ('not_relevant', 'Not relevant')], default='not_relevant', validators=[DataRequired()], render_kw={
            "title": """Not to confuse with the "sso" key: the "ldap" key corresponds to wether or not a user *can* login on the app using its YunoHost credentials."""})
    sso = SelectField('Integrate with Yunohost SingleSignOn (SSO) :', choices=[
            ('false', 'False'),
            ('true', 'True'),
            ('not_relevant', 'Not relevant')], default='not_relevant', validators=[DataRequired()], render_kw={
            "title": """Not to confuse with the "ldap" key: the "sso" key corresponds to wether or not a user is *automatically logged-in* on the app when logged-in on the YunoHost portal."""})

    license = StringField('Licence', validators=[DataRequired()], render_kw={"class": "form-control",
                                                                             "placeholder": "GPL"})

    website = StringField('Site web', validators=[URL(), Optional()], render_kw={"class": "form-control",
                                                                                 "placeholder": "https://awesome-app-website.com"})
    demo = StringField('Site de démonstration', validators=[URL(), Optional()], render_kw={"class": "form-control",
                                                                                           "placeholder": "https://awesome-app-website.com/demo"})
    admindoc = StringField("Documentation d'aministration", validators=[URL(), Optional()],
                           render_kw={"class": "form-control",
                                      "placeholder": "https://awesome-app-website.com/doc/admin"})
    userdoc = StringField("Documentation d'utilisation", validators=[URL(), Optional()],
                          render_kw={"class": "form-control",
                                     "placeholder": "https://awesome-app-website.com/doc/user"})
    code = StringField('Dépôt de code', validators=[URL(), Optional()], render_kw={"class": "form-control",
                                                                                   "placeholder": "https://awesome-app-website.com/get-the-code"})

    data_dir = BooleanField("L'application nécessite un répertoire dédié pour ses données", default=False,
                            render_kw={"title": "Faut-il créer un répertoire /home/yunohost.app/votreApplication ?"})
    data_subdirs = StringField('Si nécessaire, lister les sous-répertoires à configurer :',
                               validators=[Optional()], render_kw={"class": "form-control",
                                                                   "placeholder": "data, uploads, themes"})
    use_whole_domain = BooleanField("L'application nécessite d'utiliser tout un domaine (installation à la racine) :",
                                    default=False,
                                    render_kw={
                                            "title": "Doit-on installer l'application à la racine du domaine ? Sinon, on pourra l'installer dans un sous-dossier, par exemple /mon_app."})
    supports_change_url = BooleanField(
            "L'application autorise le changement d'adresse (changement de domaine ou de chemin)", default=True,
            render_kw={"title": "Faut-il permettre le changement d'URL pour l'application ? (fichier change_url)"})

    needs_admin = BooleanField("L'application nécessite de configurer un compte d'administration :", default=False,
                               render_kw={"class": "",
                                          "title": "Faut-il configurer un compte admin à l'installation ?"})

    # admin_password_help_message = BooleanField("TODO  :", default=False,
    #                           render_kw={"class": "",
    #                                      "title": "TODO"})

    language = SelectMultipleField('Langues supportées :', choices=[
            ('en', 'English'),
            ('fr', 'Français'),
            ('en', 'Spanish'),
            ('it', 'Italian'),
            ('de', 'German'),
            ('zh', 'Chinese'),
            ('jp', 'Japanese'),
            ('da', 'Danish'),
            ('pt', 'Portugese'),
            ('nl', 'Dutch'),
            ('ru', 'Russian')],
                                   default=['en'], validators=[DataRequired()])

    default_language = SelectField('Langues par défaut :', choices=[
            ('en', 'English'),
            ('fr', 'Français'),
            ('en', 'Spanish'),
            ('it', 'Italian'),
            ('zh', 'Chinese'),
            ('jp', 'Japanese'),
            ('da', 'Danish'),
            ('pt', 'Portugese'),
            ('nl', 'Dutch'),
            ('ru', 'Russian')],
                                   default=['en'])

    visibility = RadioField("Visibilité de l'application :", choices=[
            ('admin', "Administrateur/administratrice uniquement"),
            ('all_users', "Personnes connectées"),
            ('visitors', "Publique")],
                            default='all_users', validators=[DataRequired()])

    source_url = StringField("Code source ou exécutable de l'application", validators=[DataRequired(), URL()],
                             render_kw={"class": "form-control",
                                        "placeholder": "https://github.com/foo/bar/archive/refs/tags/v1.2.3.tar.gz"})  # Application source code URL
    sha256sum = StringField('Empreinte du code source (format sha256sum)',
                            validators=[DataRequired(), Length(min=64, max=64)],
                            render_kw={"class": "form-control",
                                       "placeholder": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
                                       "title": "Sha256sum of the archive. Should be 64 characters-long."})  # Source code hash (sha256sum format)


## Main form

class appGeneratorForm(manifestForm, DependenciesForm, Form_PHP, Form_NodeJS, Form_Python):
    app_name = StringField("Nom de l'application :", validators=[DataRequired()],
                           render_kw={"placeholder": "My Great App", "class": "form-control",
                                      "title": "Définir le nom de l'application, affiché dans l'interface"})
    app_id = StringField(
            Markup(
                    """Identifiant (id) de l'application <i class="grayed_hint">(en minuscule et sans espaces)</i> :"""),
            validators=[DataRequired(), Regexp("[a-z_1-9]+.*(?<!_ynh)$")],
            render_kw={"placeholder": "yunohost_awesome_app", "class": "form-control",
                       "title": "Définir l'identifiant de l'application, utilisé pour le nom du dépôt Github"})

    tutorial = SelectField("Type d'application :", choices=[
            ('false', "Version épurée"),
            ('true', "Version tutoriel")],
                           default='true', validators=[DataRequired()])

    use_logrotate = BooleanField("Utiliser logrotate pour gérer les journaux :", default=True,
                                 render_kw={
                                         "title": "Si l'application genère des journaux (log), cette option permet d'en gérer l'archivage. Recommandé."})
    # TODO : specify custom log file
    # custom_log_file = "/var/log/$app/$app.log" "/var/log/nginx/${domain}-error.log"
    use_fail2ban = BooleanField("Protéger l'application des attaques par force brute (via fail2ban) :", default=True,
                                render_kw={
                                        "title": "Si l'application genère des journaux (log) d'erreurs de connexion, cette option permet de bannir automatiquement les IP au bout d'un certain nombre d'essais de mot de passe. Recommandé."})
    use_cron = BooleanField("Ajouter une tâche CRON pour cette application :", default=False,
                            render_kw={
                                    "title": "Créer une tâche cron pour gérer des opérations périodiques de l'application."})
    cron_config_file = TextAreaField("Saisissez le contenu du fichier CRON :",
                                     validators=[Optional()],
                                     render_kw={"class": "form-control",
                                                "style": "width: 50%;height:22em;min-height: 5.5em; max-height: 55em;flex-grow: 1;box-sizing: border-box;",
                                                "title": "Saisir le contenu du fichier de la tâche CRON."})

    fail2ban_regex = StringField("Expression régulière pour fail2ban :",
                                 # Regex to match into the log for a failed login
                                 validators=[Optional()],
                                 render_kw={"placeholder": "A regular expression",
                                            "class": "form-control",
                                            "title": "Expression régulière à vérifier dans le journal pour que fail2ban s'active (cherchez une ligne qui indique une erreur d'identifiants deconnexion)."})

    nginx_config_file = TextAreaField("Saisissez le contenu du fichier de configuration du serveur NGINX :",
                                      validators=[Optional()],
                                      render_kw={"class": "form-control",
                                                 "style": "width: 50%;height:22em;min-height: 5.5em; max-height: 55em;flex-grow: 1;box-sizing: border-box;",
                                                 "title": "Saisir le contenu du fichier de configuration du serveur NGINX.",
                                                 "placeholder": "location __PATH__/ {\n    \n    proxy_pass       http://127.0.0.1:__PORT__;\n    proxy_set_header X-Real-IP $remote_addr;\n    proxy_set_header Host $host;\n    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;\n    \n    # Include SSOWAT user panel.\n    include conf.d/yunohost_panel.conf.inc;\n    }"})

    use_systemd_service = BooleanField(
            "Utiliser un service système (via systemd) pour gérer le fonctionnement de l'application  :", default=False,
            render_kw={
                    "title": "Un service systemd s'occupera de démarrer l'application avec le système, et permettra de l'arrêter ou la redémarrer. Recommandé."})
    systemd_config_file = TextAreaField("Saisissez le contenu du fichier de configuration du service SystemD :",
                                        validators=[Optional()],
                                        render_kw={"class": "form-control",
                                                   "style": "width: 50%;height:22em;min-height: 5.5em; max-height: 55em;flex-grow: 1;box-sizing: border-box;",
                                                   "title": "Saisir le contenu du fichier de configuration du service systemd."})
    systemd_service_description = StringField("Description du service de l'application :",
                                              validators=[Optional()],
                                              render_kw={"placeholder": "A short description of the app",
                                                         "class": "form-control",
                                                         "style": "width: 30%;",
                                                         "title": "Décrire en une ligne ce que fait ce service. Ceci sera affiché dans l'interface d'administration."})

    use_custom_config_file = BooleanField(
            "Utiliser un fichier de configuration personnalisé  :", default=False,
            render_kw={
                    "title": "Est-ce que l'application nécessite un fichier de configuration personnalisé ? (du type .env, config.json, parameters.yaml, …)"})
    custom_config_file = StringField("Nom du fichier à utiliser :",
                                     validators=[Optional()],
                                     render_kw={"placeholder": "config.json",
                                                "class": "form-control",
                                                "style": "width: 30%;",
                                                "title": "Décrire en une ligne ce que fait ce service. Ceci sera affiché dans l'interface d'administration."})

    custom_config_file_content = TextAreaField("Saisissez le contenu du fichier de configuration personnalisé :",
                                               validators=[Optional()],
                                               render_kw={"class": "form-control",
                                                          "style": "width: 50%;height:22em;min-height: 5.5em; max-height: 55em;flex-grow: 1;box-sizing: border-box;",
                                                          "title": "Saisir le contenu du fichier de configuration personnalisé."})

    needs_exposed_ports = StringField("Nom de l'application :", validators=[Optional(), Regexp('([0-9]+,)+([0-9]+)?')],
                                      # TODO : add this in the HTML
                                      render_kw={"placeholder": "5000, ", "class": "form-control",
                                                 "title": "Liste de ports à ouvrir publiquement, séparés par des virgules. NE PAS ACTIVER si le port est uniquement utilisé en interne ou disponible via le reverse-proxy de Nginx."})

    submit = SubmitField('Soumettre')


#### Retriving templates

parameters = dict(GENERATOR_DICT)

template_manifest = environment.get_template("manifest.j2")
manifest = dict(GENERATOR_DICT)

template_install = environment.get_template("install.j2")
install = dict(GENERATOR_DICT)


#### Initialising variables


#### Web pages

@app.route(url_prefix + "/", methods=['GET', 'POST'])
def main_form():
    if not 'appGeneratorForm' in locals():
        main_form = appGeneratorForm()

    if request.method == "POST":
        result = request.form
        results = dict(result)
        # print("[DEBUG] This is a POST request")
        # print(results)
        for key, value in results.items():
            parameters[key] = value
        parameters["preview"] = True
        # print(install)
        if main_form.validate_on_submit():
            parameters["invalid_form"] = False
            print()
            print('formulaire valide')
            # print(main_form.data.items())

            for key, value in main_form.data.items():
                parameters[key] = value  # TODO change the name

            templates = (
                    'templates/manifest.j2', 'templates/install.j2', 'templates/remove.j2', 'templates/backup.j2',
                    'templates/restore.j2', 'templates/upgrade.j2', 'templates/config.j2', 'templates/change_url.j2',
                    'templates/_common.sh.j2')
            markdown_to_html = dict()
            for template in templates:
                markdown_content, html_content = markdown_file_to_html_string(template)
                template_key = template.split('templates/')[1].split('.j2')[
                    0]  # Let's retrieve what's the exact template used
                markdown_to_html[template_key] = {"markdown_content": markdown_content,
                                                  "html_content": html_content}
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

            template_manifest_content = render_template_string(markdown_to_html['manifest']['markdown_content'],
                                                               parameters=parameters,
                                                               main_form=main_form)

            template_install_content = render_template_string(markdown_to_html['install']['markdown_content'],
                                                              parameters=parameters, main_form=main_form,
                                                              markdown_to_html=markdown_to_html['install'])

            template_remove_content = render_template_string(markdown_to_html['remove']['markdown_content'],
                                                             parameters=parameters, main_form=main_form,
                                                             markdown_to_html=markdown_to_html['remove'])

            template_backup_content = render_template_string(markdown_to_html['backup']['markdown_content'],
                                                             parameters=parameters, main_form=main_form,
                                                             markdown_to_html=markdown_to_html['backup'])

            template_restore_content = render_template_string(markdown_to_html['restore']['markdown_content'],
                                                              parameters=parameters, main_form=main_form,
                                                              markdown_to_html=markdown_to_html['restore'])

            template_upgrade_content = render_template_string(markdown_to_html['upgrade']['markdown_content'],
                                                              parameters=parameters, main_form=main_form,
                                                              markdown_to_html=markdown_to_html['upgrade'])

            template_config_content = render_template_string(markdown_to_html['config']['markdown_content'],
                                                             parameters=parameters, main_form=main_form,
                                                             markdown_to_html=markdown_to_html['config'])

            template_common_sh_content = render_template_string(markdown_to_html['_common.sh']['markdown_content'],
                                                                parameters=parameters, main_form=main_form,
                                                                markdown_to_html=markdown_to_html['_common.sh'])

            if parameters['supports_change_url']:
                template_change_url_content = render_template_string(markdown_to_html['change_url']['markdown_content'],
                                                                     parameters=parameters, main_form=main_form,
                                                                     markdown_to_html=markdown_to_html['change_url'])
            else:
                template_change_url_content = False

            print(parameters['custom_config_file'])
            print(parameters['use_custom_config_file'])
            return render_template('index.html', parameters=parameters, main_form=main_form,
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
                                   nginx_config_file=parameters['nginx_config_file'],
                                   systemd_config_file=parameters['systemd_config_file'],
                                   custom_config_file=parameters['custom_config_file'],
                                   cron_config_file=parameters['cron_config_file'], url_prefix=url_prefix)
        else:
            print("[DEBUG] Formulaire invalide: ", main_form.errors)
            parameters["preview"] = False
            parameters["invalid_form"] = True

    elif request.method == "GET":
        parameters["preview"] = False

    return render_template('index.html', parameters=install, main_form=main_form, url_prefix=url_prefix)


@app.route("/install")
def install_page():
    return render_template(template_install, parameters=install)


@app.route('/generator', methods=('GET', 'POST'))
def create():
    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']

        if not title:
            flash('Title is required!')
        elif not content:
            flash('Content is required!')
        else:
            install.append({'title': title, 'content': content})
            return redirect('/')
    return render_template('form.html')


@app.route('/download_zip', methods=('GET', 'POST'))
def telecharger_zip():
    # Retrieve arguments
    print("Génération du .zip")
    app_id = request.args.get('app_id')
    print("Génération du .zip pour " + app_id)

    custom_config_file = parse.unquote(request.args.get('custom_config_file'))
    custom_config_file_content = parse.unquote(request.args.get('custom_config_file_content'))
    systemd_config_file = parse.unquote(request.args.get('systemd_config_file'))
    nginx_config_file = parse.unquote(request.args.get('nginx_config_file'))
    cron_config_file = parse.unquote(request.args.get('cron_config_file'))

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

    use_php = request.args.get('use_php')
    print("PHP")
    print(use_php)
    php_config_file = parse.unquote(request.args.get('php_config_file'))
    php_config_file_content = parse.unquote(request.args.get('php_config_file_content'))

    archive_name = app_id + '.zip'  # Actually it's the javascript that decide of the filename… this is only an internal name

    # Generate the zip file (will be stored in the working directory)
    with zipfile.ZipFile(archive_name, 'w') as zf:
        # Add text in directly in the ZIP, as a file
        zf.writestr('manifest.toml', template_manifest_content)
        zf.writestr('scripts/install', template_install_content)
        zf.writestr('scripts/remove', template_remove_content)
        zf.writestr('scripts/backup', template_backup_content)
        zf.writestr('scripts/restore', template_restore_content)
        zf.writestr('scripts/upgrade', template_upgrade_content)
        zf.writestr('scripts/_common_sh', template_common_sh_content)

        if template_config_content:
            zf.writestr('scripts/config', template_config_content)
        if template_change_url_content:
            zf.writestr('scripts/change_url', template_change_url_content)
        if custom_config_file:
            zf.writestr('conf/' + custom_config_file, custom_config_file_content)
        if systemd_config_file:
            zf.writestr('conf/systemd.service', systemd_config_file)
        if nginx_config_file:
            zf.writestr('conf/nginx.conf', nginx_config_file)
        if cron_config_file:
            zf.writestr('conf/task.conf', cron_config_file)
        if use_php == "True":
            zf.writestr('conf/' + php_config_file, php_config_file_content)

    # Send the zip file to the user
    return send_file(archive_name, as_attachment=True)


#### Running the web server
if __name__ == "__main__":
    app.run(debug=True)
