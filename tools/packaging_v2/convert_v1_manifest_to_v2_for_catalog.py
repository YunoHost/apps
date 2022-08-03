import copy


def convert_v1_manifest_to_v2_for_catalog(manifest):

    manifest = copy.deepcopy(manifest)

    if "upstream" not in manifest:
        manifest["upstream"] = {}

    if "license" in manifest and "license" not in manifest["upstream"]:
        manifest["upstream"]["license"] = manifest["license"]

    if "url" in manifest and "website" not in manifest["upstream"]:
        manifest["upstream"]["website"] = manifest["url"]

    manifest["integration"] = {
        "yunohost": manifest.get("requirements", {}).get("yunohost", "").replace(">", "").replace("=", "").replace(" ", ""),
        "architectures": "all",
        "multi_instance": manifest.get("multi_instance", False),
        "ldap": "?",
        "sso": "?",
        "disk": "50M",
        "ram": {"build": "50M", "runtime": "10M"}
    }

    maintainer = manifest.get("maintainer", {}).get("name")
    manifest["maintainers"] = [maintainer] if maintainer else []

    install_questions = manifest["arguments"]["install"]

    manifest["install"] = {}
    for question in install_questions:
        name = question.pop("name")
        if "ask" in question and name in ["domain", "path", "admin", "is_public", "password"]:
            question.pop("ask")
        if question.get("example") and question.get("type") in ["domain", "path", "user", "boolean", "password"]:
            question.pop("example")

        manifest["install"][name] = question

    manifest["resources"] = {
        "system_user": {},
        "install_dir": {
            "alias": "final_path"
        }
    }

    keys_to_keep = ["packaging_format", "id", "name", "description", "version", "maintainers", "upstream", "integration", "install", "resources"]

    keys_to_del = [key for key in manifest.keys() if key not in keys_to_keep]
    for key in keys_to_del:
        del manifest[key]

    return manifest
