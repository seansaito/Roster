"""
    A script that takes the aggregated group of relays (families) and converts them into rankings.
    It also stores stats and .json files for countries, ports, etc. It acts as a central controller that
    talks to family_aggregator, relay_stats_aggregator, tshirt_validator. At the end, it uploads all stats
    files to AWS S3.
"""

from app import app
from app.controllers.relay_stats_aggregator import RelayStatsAggregator
from app.models.family_aggregator import FamilyAggregator

import json, os, datetime, csv

import boto
from boto.s3.key import Key

import pycountry
from collections import OrderedDict
import re

from global_vars import *

"""
    This function takes an array of relays and records two statistics w.r.t. countries:
        - Distribution of physical relays for each country
        - Distribution of consensus weight for each country
"""
def record_country_stats(relays):
    print "[record_country_stats] Recording country stats"

    # Paths
    script_dir = "app/static/csv/"
    relay_count_path = os.path.join(script_dir, "country_relay_count.csv")
    cw_fraction_path = os.path.join(script_dir, "country_cw_fraction.csv")

    # dicts which store number of relays/cw fraction in each country
    relay_count = OrderedDict()
    cw_fraction = OrderedDict()

    # Initialize
    for country in pycountry.countries:
        relay_count[country.alpha2] = 0
        cw_fraction[country.alpha2] = 0

    # First store data in dict
    for relay in relays:
        if "country" in relay:
            relay_count[relay["country"].upper()] += 1
            cw_fraction[relay["country"].upper()] += relay.setdefault("consensus_weight_fraction", 0)

    # First overwrite csv file using the one in s3
    c = boto.connect_s3(acc_key, acc_sec)
    b = c.get_bucket(bucket)
    bucket_key = Key(b)

    bucket_key.key = "country_relay_count.csv"
    bucket_key.get_contents_to_filename(relay_count_path)
    b.set_acl("public-read", "country_relay_count.csv")

    bucket_key.key = "country_cw_fraction.csv"
    bucket_key.get_contents_to_filename(cw_fraction_path)
    b.set_acl("public-read", "country_cw_fraction.csv")

    # Write data for each stat
    time = "-".join(datetime.datetime.strftime(datetime.datetime.now(), "%Y, %m, %d, %H, %M, %S").split(", "))
    for path, data in [(relay_count_path, relay_count), (cw_fraction_path, cw_fraction)]:
        with open(path, "a") as f:
            c = csv.writer(f)
            c.writerow([time] + data.values())
            f.close()

    print "[record_country_stats] End record_country_stats"
    return (relay_count, cw_fraction)


# Helper functions for record_port_stats
def parse_between(string):
    if "-" in string:
        res = string.split("-")
        return [int(res[0]), int(res[1])]
    return [int(string)]

def get_opposite_offset(num):
    return (num + (-1)) % 2

def stack_dictionaries(dict1, dict2):
    for key in dict2:
        dict1[key] += dict2[key]
    return

"""
    This function takes an array of relays and records the number of times
    each port is accepted in the exit policy.
"""
def record_port_stats(relays):
    print "[record_port_stats] Recording port stats"
    script_dir = "app/"
    rel_path = "static/json/ports.json"
    abs_file_path = os.path.join(script_dir, rel_path)

    # Initialization
    all_ports = {}
    for i in range(1, 65536):
        all_ports[i] = 0

    # Offset constants for the loop
    init_vals = {"accept": 1, "reject": 0}

    # Loop through each relay
    for relay in relays:
        policy = relay["exit_policy_summary"].keys()[0]
        if relay["exit_policy_summary"][policy][0] == "1-65535":
            continue

        ports, offset_value = relay["exit_policy_summary"][policy], init_vals[policy]
        opposite_offset = get_opposite_offset(offset_value)

        relay_ports = {}
        for i in range(1, 65536):
            relay_ports[i] = opposite_offset

        for interval in relay["exit_policy_summary"][policy]:
            parsed = parse_between(interval)
            if len(parsed) == 1:
                relay_ports[parsed[0]] = offset_value
            else:
                for i in range(parsed[0], parsed[1]+1):
                    relay_ports[i] = offset_value
        stack_dictionaries(all_ports, relay_ports)

    json_file = open(abs_file_path, "w+")
    json_file.write(json.dumps(all_ports))
    json_file.close()

    print "[record_port_stats] End record ports stats"
    return all_ports

def group_by_AS(relays):
    """
    A function that separates the relays based on AS number.
    For each AS number, the function stores the following in JSON format:
        - Relay fingerprints in that AS
        - OR Address of each relay
        - Aggregate Bandwidth
        - Aggregate Consensus Weight Fraction
        - Country code (in ISO2)
    Relays that don't list their AS number will be grouped in no_as_number
    """
    grouped_AS_stats = {}

    for relay in relays:
        as_number = relay.setdefault("as_number", "no_as_number")
        if as_number in grouped_AS_stats:
            grouped_AS_stats[as_number]["relays"].append(relay["fingerprint"])
            grouped_AS_stats[as_number]["or_addresses"].append(relay["or_addresses"])
            grouped_AS_stats[as_number]["bandwidth"] += relay["observed_bandwidth"]
            grouped_AS_stats[as_number]["cw_fraction"] += relay.setdefault("consensus_weight_fraction", 0)
            if relay.setdefault("country", "") not in grouped_AS_stats[as_number]["country"]:
                grouped_AS_stats[as_number]["country"].append(relay.setdefault("country", ""))
        else:
            grouped_AS_stats[as_number] = {
                "relays": [relay["fingerprint"]],
                "bandwidth": relay["observed_bandwidth"],
                "cw_fraction": relay.setdefault("consensus_weight_fraction", 0),
                "country": [relay.setdefault("country", "")],
                "or_addresses": [relay["or_addresses"]]
            }

    return grouped_AS_stats

def group_by_ipv6(relays):
    """
        A function that separates the relays based on IPv6 address.
        For each AS number, the function stores the following in JSON format:
            - Relay fingerprints in that AS
            - OR Address of each relay
            - Aggregate Bandwidth
            - Aggregate Consensus Weight Fraction
            - Country code (in ISO2)
        Relays that don't list their AS number will be grouped in no_as_number
    """
    ipv6_store = {}
    for relay in relays:
        if "or_addresses" in relay: # has or_addresses field
            for address in relay["or_addresses"]:
                res = get_ipv6_regex(address)
                if res is not None:
                    ipv6 = res.group(0)
                    if ipv6 in ipv6_store:
                        ipv6_store[ipv6]["relays"].append(relay["fingerprint"])
                        ipv6_store[ipv6]["or_addresses"].append(relay["or_addresses"])
                        ipv6_store[ipv6]["bandwidth"] += relay["observed_bandwidth"]
                        ipv6_store[ipv6]["cw_fraction"] += relay["consensus_weight_fraction"]
                        if relay.setdefault("country", "") not in ipv6_store[ipv6]["country"]:
                            ipv6_store[ipv6]["country"].append(relay.setdefault("country", ""))
                    else:
                        ipv6_store[ipv6] = {
                            "relays": [relay["fingerprint"]],
                            "bandwidth": relay["observed_bandwidth"],
                            "cw_fraction": relay.setdefault("consensus_weight_fraction", 0),
                            "country": [relay.setdefault("country", "")],
                            "or_addresses": [relay["or_addresses"]]
                        }

    return ipv6_store


def get_ipv6_regex(address):
    res = re.search(r'\[.*\]', address, re.IGNORECASE)
    return res


def store_rankings(groups):
    rankings = {"top10_bandwidth": groups["bandwidth_top10"],
                "top10_consensus": groups["consensus_top10"],
                "all": groups["families"]}

    # Using abs_paths dictionary from global_vars.py
    for key, path in abs_paths.items():
        json_file = open(path, "w+")
        json_file.write(json.dumps(rankings[key]))
        json_file.close()

    return

if __name__ == "__main__":
    groups = {"families": [],
              "relays": [],
              "bandwidth_rankings": [],
              "bandwidth_top10": [],
              "consensus_rankings": [],
              "consensus_top10": [],
              "exit_bandwidth_rankings": [],
              "exit_bandwidth_top10": [],
              "country_count_rankings": [],
              "country_cw_rankings": [],
              "port_rankings": []
             }

    aggregator = FamilyAggregator()
    families = aggregator.families
    relays = aggregator.relays

    groups["families"] = families
    groups["relays"] = relays

    # Get rankings and stats
    groups["bandwidth_rankings"] = sorted(families, key=lambda family: family["observed_bandwidth"], reverse=True)
    groups["consensus_rankings"] = sorted(families, key=lambda family: family["consensus_weight_fraction"], reverse=True)
    groups["exit_bandwidth_rankings"] = sorted(families, key=lambda family: family["exit_bandwidth"], reverse=True)
    groups["country_count_rankings"], groups["country_cw_rankings"] = record_country_stats(relays)
    groups["port_rankings"] = record_port_stats(relays)

    stats_aggregator = RelayStatsAggregator(groups)

    # Assign badges to each family
    for family in families:
        temp = family
        family["badges"] = stats_aggregator.analyze_family(temp)

    # Reassign the groups with updated badges.
    groups["families"] = families
    groups["relays"] = relays

    groups["bandwidth_rankings"] = sorted(families, key=lambda family: family["observed_bandwidth"], reverse=True)
    groups["consensus_rankings"] = sorted(families, key=lambda family: family["consensus_weight_fraction"], reverse=True)
    groups["exit_bandwidth_rankings"] = sorted(families, key=lambda family: family["exit_bandwidth"], reverse=True)

    # These are used for the index page
    groups["bandwidth_top10"] = groups["bandwidth_rankings"][:10]
    groups["consensus_top10"] = groups["consensus_rankings"][:10]
    groups["exit_bandwidth_top10"] = groups["exit_bandwidth_rankings"][:10]

    # Stores bandwidth rankings, consensus_weight rankings, all.json
    store_rankings(groups)

    # Uploads the data and stats to AWS S3
    from upload import *
    map(upload, assets)
