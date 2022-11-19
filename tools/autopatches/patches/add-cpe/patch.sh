#!/usr/bin/python3

import json
import csv

def find_cpe(app_id):
    with open("../../patches/add-cpe/cpe.csv", newline='') as f:
        cpe_list = csv.reader(f)
        for row in cpe_list:
            if row[0] == app_id:
                return row[1]
        return False

manifest = json.load(open("manifest.json"))
app_id = manifest['id']
cpe = find_cpe(app_id)
if cpe:
    manifest['upstream']['cpe'] = cpe
    json.dump(manifest, open("manifest.json", "w"), indent=4, ensure_ascii=False)
