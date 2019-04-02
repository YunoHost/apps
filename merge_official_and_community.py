import json

community = json.loads(open("community.json").read())
official = json.loads(open("official.json").read())

# Add high quality and set working state for official apps
for app, infos in official.items():
    infos["high_quality"] = True
    infos["state"] = "working"

merged = community
merged.update(official)

open("apps.json", "w").write(json.dumps(merged, sort_keys=True, indent=4, separators=(',', ': ')))
