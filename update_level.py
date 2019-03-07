#!/usr/bin/env python

import json

import urllib
from bs4 import BeautifulSoup

# =============================================================================
def get_level(app_id):
    "return level from https://dash.yunohost.org/"

    url_dash = "https://dash.yunohost.org/appci/app/" + app_id
    
    try :
        html = urllib.request.urlopen(url_dash)
        soup = BeautifulSoup(html, "lxml", from_encoding='utf-8')
        level = int(soup.find("tr",{"branch":"stable"}).find("div",{"title":"Level"}).text)
    except:
        print(">>Can not get level for", app_id)
        level = None
        
    return level

# =============================================================================
def update_app_list(app_list_name):
    "compare app level from app list and dash, then correct the app list"

    app_list = json.load(open(app_list_name))
    
    for app_id in app_list.keys():
        # if level is not set, assumed to be 0
        try:
            app_list[app_id]["level"]
        except :
            app_list[app_id]["level"] = 0
        # if maintained is not set, assumed to be true
        try:
            app_list[app_id]["maintained"]
        except :
            app_list[app_id]["maintained"] = True
        
        # display app information
    #    print("Name :", app_id)
    #    print("Branch :", app_list[app_id]["branch"])
    #    print("Revision :", app_list[app_id]["revision"])
    #    print("State :", app_list[app_id]["state"])
    #    print("URL :", app_list[app_id]["url"])
    #    print("Level :", app_list[app_id]["level"])
    #    print("Maintained :", app_list[app_id]["maintained"])
    
        # only working app are checked
        if app_list[app_id]["state"] == "working":
            app_list_level = app_list[app_id]["level"]
            dash_level = get_level(app_id)
            #print(app_list_level, dash_level)
            if (app_list_level != dash_level) and (dash_level is not None):
                print("")
                print(app_id, "should be update")
                print(app_list_name, "level :", app_list_level)
                print("Dash level:", dash_level)
                app_list[app_id]["state"] = dash_level 
     
    # uncomment to automatically update file
    #open(app_list_name, "w").write("\n".join(json.dumps(app_list, indent=4, sort_keys=True).split(" \n")) + "\n")

# =============================================================================

if __name__ == '__main__':

    lists= ["official.json","community.json"]
    
    for app_list_name in lists :
        print("===", app_list_name,"===")
        update_app_list(app_list_name)
