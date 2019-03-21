import json

community = json.loads(open("community.json").read())
official = json.loads(open("official.json").read())

merged = community
merged.update(official)

open("apps.json", "w").write(json.dumps(merged, sort_keys=True, indent=4, separators=(',', ': ')))
