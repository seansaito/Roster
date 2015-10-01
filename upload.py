import boto, os
from boto.s3.key import Key
from global_vars import *

assets = [  ("app/static/json/top10_bandwidth.json", "bandwidth.json"),
            ("app/static/json/top10_consensus.json", "consensus.json"),
            ("app/static/json/all.json", "all.json"),
            ("app/static/json/ports.json", "ports.json"),
            ("app/static/csv/country_relay_count.csv", "country_relay_count.csv"),
            ("app/static/csv/country_cw_fraction.csv", "country_cw_fraction.csv")]

def upload(pair):
    filename, key = pair
    print "[upload] Uploading " + filename
    c = boto.connect_s3(acc_key, acc_sec)
    b = c.get_bucket(bucket)
    bucket_key = Key(b)
    bucket_key.key = key
    bucket_key.set_contents_from_filename(filename)
    b.set_acl("public-read", key)
    print "[upload] Uploaded"
