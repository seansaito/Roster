# -*- coding: utf-8 -*-

# Imports
from app import app
from global_vars import *
from flask import render_template, redirect, url_for, request
import os, json

import boto
from boto.s3.key import Key

@app.route("/", methods=["GET"])
def index():
    # First update the bandwidth and cw rankings using the files from S3

    # Connect and retrieve key from S3 bucket
    c = boto.connect_s3(acc_key, acc_sec)
    b = c.get_bucket(bucket)
    bucket_key = Key(b)

    # Arrays that will store json data of top 10 families for each categories
    top10_bandwidth, top10_consensus = [], []

    # Write the json files from S3 to local, then load them into the array stores
    for key, array_store in [("bandwidth.json", top10_bandwidth), ("consensus.json", top10_consensus)]:
        bucket_key.key = key
        with open(abs_paths[key[:-5]], "w+") as fp:
            bucket_key.get_file(fp)
            fp.seek(0)
            array_store = json.load(fp)
            fp.close()

    return render_template("index.html", top10_bandwidth=top10_bandwidth, top10_consensus=top10_consensus)

"""
Route for family dashboard page. Searches the json files for the given
fingerprint. Search for relays are redirected here.
"""
@app.route("/family_detail/<fingerprint>", methods=["GET", "POST"])
def family_detail(fingerprint):
    # Again, connect to S3 to get fetch latest json files
    c = boto.connect_s3(acc_key, acc_sec)
    b = c.get_bucket(bucket)
    bucket_key = Key(b)

    theOne = ""
    for key in ["bandwidth.json", "consensus.json", "all.json"]:
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
                if relay["families"] == fingerprint:
                    theOne = family
                    break

        if theOne != "":
            break

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
