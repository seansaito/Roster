# -*- coding: utf-8 -*-

### Imports ###
from app import app
from global_vars import *
from flask import render_template, redirect, url_for, request, jsonify
import os, json

import boto
from boto.s3.key import Key

from global_vars import static_store_strategy

@app.route("/", methods=["GET"])
def index():
    # Check static_store_strategy. If local, then no need to connect to S3
    if static_store_strategy == "LOCAL":
        print "GET /   Going local strategy"
        data_store = [[],[],[]]
        file_pairs = [(0, "top10_bandwidth"), (1, "top10_consensus"), (2, "all")]
        for store_index, file_name in file_pairs:
            fp = open(abs_paths[file_name], "r")
            data_store[store_index] = json.load(fp)
            fp.close()

        # Unpack the families into individual relays
        all_relays = []
        for family in data_store[2]:
            all_relays = all_relays + [relay for relay in family["families"]]

        data_store[2] = all_relays

        return render_template("index.html", top10_bandwidth=data_store[0],
            top10_consensus=data_store[1], all_relays=data_store[2])

    # First update the bandwidth and cw rankings using the files from S3
    # Connect and retrieve key from S3 bucket
    c = boto.connect_s3(acc_key, acc_sec)
    b = c.get_bucket(bucket)
    bucket_key = Key(b)

    bucket_key.key = "top10_bandwidth.json"
    top10_bandwidth = []

    with open(abs_paths["top10_bandwidth"], "w+") as fp:
        bucket_key.get_file(fp)
        fp.seek(0)
        top10_bandwidth = json.load(fp)
        fp.close()

    bucket_key.key = "top10_consensus.json"
    top10_consensus = []

    with open(abs_paths["top10_consensus"], "w+") as fp:
        bucket_key.get_file(fp)
        fp.seek(0)
        top10_consensus = json.load(fp)
        fp.close()

    bucket_key.key = "all.json"
    all_families = []

    with open(abs_paths["all"], "w+") as fp:
        bucket_key.get_file(fp)
        fp.seek(0)
        all_families = json.load(fp)
        fp.close()

    all_relays = []
    for family in all_families:
        all_relays = all_relays + [relay for relay in family["families"]]

    # Lastly, reset the files for proper file tracking
    # reset_files()

    return render_template("index.html", top10_bandwidth=top10_bandwidth,
        top10_consensus=top10_consensus, all_relays=all_relays)

def find_family(fingerprint):
    """
    Finds a family from the json files based on fingerprint
    """
    # If static_store_strategy is LOCAL, then just lookup local files
    if static_store_strategy == "LOCAL":
        print "[find_family] Going local strategy"
        theOne = ""
        for key in ["top10_bandwidth.json", "top10_consensus.json", "all.json"]:
            array_store = []

            with open(abs_paths[key[:-5]], "r") as fp:
                array_store = json.load(fp)
                fp.close()

            for family in array_store:
                for relay in family["families"]:
                    if relay["fingerprint"] == fingerprint:
                        theOne = family
                        break

            if theOne != "":
                break

        return theOne

    # Fetch latest json files from S3
    c = boto.connect_s3(acc_key, acc_sec)
    b = c.get_bucket(bucket)
    bucket_key = Key(b)

    theOne = ""
    for key in ["top10_bandwidth.json", "top10_consensus.json", "all.json"]:
        array_store = []
        bucket_key.key = key

        # Load the json to the temporary array store
        with open(abs_paths[key[:-5]], "w+") as fp:
            bucket_key.get_file(fp)
            fp.seek(0)
            array_store = json.load(fp)
            fp.close()

        # Loop through families to search for the family with given fingerprint
        for family in array_store:
            for relay in family["families"]:
                if relay["fingerprint"] == fingerprint:
                    theOne = family
                    break

        if theOne != "":
            break

    return theOne

def reset_files():
    """ Function to make sure local copy of json files are blank """
    for key in ["top10_bandwidth", "top10_consensus", "all"]:
        fp = open(abs_paths[key], "w+")
        fp.close()
    return

@app.route("/family_detail/<fingerprint>", methods=["GET", "POST"])
def family_detail(fingerprint):
    """
    Route for family dashboard page. Searches the json files for the given
    fingerprint. Search for relays are redirected here.
    """
    theOne = find_family(fingerprint)

    # Family is not found, so return 404 page
    if theOne == "":
        return render_template("404.html")

    # Preprocess the flags for each relay in the family
    for relay in theOne["families"]:
        parse_flags(relay)

    # Set markers for each relay to put on the Google map
    # Some relays have the same exact locations. Hence each coordinate
    # stores an array of associated fingerprints
    markers = {}
    for relay in theOne["families"]:
        if "latitude" in relay and "longitude" in relay:
            if (relay["latitude"], relay["longitude"]) in markers.keys():
                markers[(relay["latitude"], relay["longitude"])].append(relay["fingerprint"])
            else:
                markers[(relay["latitude"], relay["longitude"])] = [relay["fingerprint"]]

    # Reset the json files
    # reset_files()

    return render_template("family_detail.html", family=theOne, markers=markers)

# Parse the flags key of a relay and assign either a 0 or 1 for each flag
# This will be used to determine which icon to use in the dashboard
def parse_flags(relay):
    res = []
    for flag in flags:
        if flag in relay["flags"]:
            res.append((flag, 1))
    for flag in flags:
        if (flag, 1) not in res:
            res.append((flag, 0))
    relay["flags"] = res
    return

@app.route("/search", methods=["POST"])
def search():
    fingerprint = request.form["fingerprint"]
    return redirect(url_for("family_detail", fingerprint=fingerprint))

# For generating list of badges in /badges
badges_list = [
    {
        "name": "Bandwidth",
        "icon": "rocket",
        "tiers": 4,
        "percentiles": ["80th percentile", "60th percentile", "40th percentile", "20th percentile"]
    },
    {
        "name": "Exit Bandwidth",
        "icon": "exit",
        "tiers": 4,
        "percentiles": ["80th percentile", "60th percentile", "40th percentile", "20th percentile"]
    },
    {
        "name": "Consensus Weight",
        "icon": "library",
        "tiers": 4,
        "percentiles": ["80th percentile", "60th percentile", "40th percentile", "20th percentile"]
    },
    {
        "name": "Exit Diversity by Country",
        "icon": "podcast",
        "tiers": 4,
        "percentiles": ["80th percentile", "60th percentile", "40th percentile", "20th percentile"]
    },
    {
        "name": "Guard Diversity by Country",
        "icon": "marvin",
        "tiers": 4,
        "percentiles": ["80th percentile", "60th percentile", "40th percentile", "20th percentile"]
    },
    {
        "name": "Exit Diversity by AS Org",
        "icon": "organization",
        "tiers": 4,
        "percentiles": ["80th percentile", "60th percentile", "40th percentile", "20th percentile"]
    },
    {
        "name": "Guard Diversity by AS Org",
        "icon": "spaceinvaders",
        "tiers": 4,
        "percentiles": ["80th percentile", "60th percentile", "40th percentile", "20th percentile"]
    },
    {
        "name": "Number of Countries",
        "icon": "earth",
        "tiers": 4,
        "percentiles": ["Above 20 countries", "10 - 20 countries", "3 - 10 countries", "Below 3 countries"]
    },
    {
        "name": "Number of Relays",
        "icon": "airplane",
        "tiers": 4,
        "percentiles": ["Above 20 relays", "10 - 20 relays", "5 - 10 relays", "2 - 5 relays"]
    },
    {
        "name": "Has Contact for At Least Half of Relays",
        "icon": "book2",
        "tiers": 2
    },
    {
        "name": "At Least Half of Relays are Guards",
        "icon": "cone",
        "tiers": 2
    },
    {
        "name": "Country Diversity",
        "icon": "globe",
        "tiers": 2
    },
    {
        "name": "Runs Recommended Tor Version",
        "icon": "mortar-board",
        "tiers": 2
    },
    {
        "name": "Has an IPv6 Relay",
        "icon": "paperplane",
        "tiers": 2
    },
    {
        "name": "Has an IPv6 Exit Relay",
        "icon": "rocket2",
        "tiers": 2
    },
    {
        "name": "Age of Family",
        "icon": "hipster2",
        "tiers": 4,
        "percentiles": ["80th percentile", "60th percentile", "40th percentile", "20th percentile"]
    },
    {
        "name": "Maximum Uptime",
        "icon": "clock2",
        "tiers": 4,
        "percentiles": ["80th percentile", "60th percentile", "40th percentile", "20th percentile"]
    }
]

@app.route("/badges")
def badges():
    return render_template("badges.html", badges_list=badges_list)

@app.route("/faqs")
def faqs():
    return render_template("faq.html")
