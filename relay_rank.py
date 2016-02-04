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

def record_country_stats(relays):
    """
        This function takes an array of relays and records two statistics w.r.t. countries:
        - Distribution of physical relays for each country
        - Distribution of consensus weight for each country
    """
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
    # TODO no need to connect to S3
    # c = boto.connect_s3(acc_key, acc_sec)
    # b = c.get_bucket(bucket)
    # bucket_key = Key(b)
    #
    # bucket_key.key = "country_relay_count.csv"
    # bucket_key.get_contents_to_filename(relay_count_path)
    # b.set_acl("public-read", "country_relay_count.csv")
    #
    # bucket_key.key = "country_cw_fraction.csv"
    # bucket_key.get_contents_to_filename(cw_fraction_path)
    # b.set_acl("public-read", "country_cw_fraction.csv")

    # Write data for each stat
    time = "-".join(datetime.datetime.strftime(datetime.datetime.now(), "%Y, %m, %d, %H, %M, %S").split(", "))
    for path, data in [(relay_count_path, relay_count), (cw_fraction_path, cw_fraction)]:
        with open(path, "a") as f:
            c = csv.writer(f)
            c.writerow([time] + data.values())
            f.close()

    print "[record_country_stats] End record_country_stats"
    return (relay_count, cw_fraction)

def record_country_stats_json(relays):
    """
        Same as record_country_stats, but returns data for storing json rather than
        csv. Is used for getting the country stats for guard and exit relays
    """
    print "[record_country_stats_json] Recording country stats in json form"
    # dicts which store number of relays/cw fraction in each country
    relay_count = {}
    cw_fraction = {}

    # Initialize
    for country in pycountry.countries:
        relay_count[country.alpha2] = 0
        cw_fraction[country.alpha2] = 0

    # First store data in dict
    for relay in relays:
        if "country" in relay:
            relay_count[relay["country"].upper()] += 1
            cw_fraction[relay["country"].upper()] += relay.setdefault("consensus_weight_fraction", 0)

    print "[record_country_stats_json] end function"

    return {
        "relay_count": OrderedDict(sorted(relay_count.items(), key=lambda item: item[1], reverse=True)),
        "cw_fraction": OrderedDict(sorted(cw_fraction.items(), key=lambda item: item[1], reverse=True))
    }

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

def dictify_relays(relays):
    """ Turn a list of relays into a dict for easy retrieval """
    res = {}
    for relay in relays:
        res[relay["fingerprint"]] = relay
    return res

def group_by_AS_without_guard_exit(relays):
    """
    Same as group_by_AS, but only for ASes that have neither guard or exit relays
    All we have to do is prune the list fo relays to include only middle relays
    """
    grouped_AS_stats = group_by_AS(relays)

    # For searching relays
    dict_relays = dictify_relays(relays)

    pruned_group = {}

    for key, value in grouped_AS_stats.items():
        if key != "no_as_number":
            if no_exit_or_guard(value["relays"], dict_relays):
                pruned_group[key] = value

    return pruned_group

def no_exit_or_guard(fingerprints, dict_relays):
    """ Helper function for getting ASes with no guard/exit relays """
    for fingerprint in fingerprints:
        relay = dict_relays[fingerprint]
        if "Guard" in relay["flags"] or "Exit" in relay["flags"]:
            return False
    return True

def group_by_exit_and_guard(relays):
    """
    Creates two files - AS stats aggregated for exit relays and guard relays
    """
    exit_relays = [relay for relay in relays if "Exit" in relay["flags"]]
    guard_relays = [relay for relay in relays if "Guard" in relay["flags"]]
    exit_as_stats = group_by_AS(exit_relays)
    guard_as_stats = group_by_AS(guard_relays)

    exit_json, guard_json = "exit_as_stats.json", "guard_as_stats.json"
    for filename, json_store in [(exit_json, exit_as_stats), (guard_json, guard_as_stats)]:
        fp = open(filename, "w+")
        fp.write(json.dumps(json_store))
        fp.close()

    return

def get_AS_cardinality(grouped_AS_stats):
    """
    A function that takes a dictionary of grouped_AS_stats and sorts based
    on number of relays in each AS.

    It excludes no_as_number

    Parameters:
        grouped_AS_stats (dict)     : Dictionary which keys are the AS numbers
    Returns:
        An OrderedDict of the as_numbers, the values of each key being the cardinality
        of relays
    """
    temp = {}
    for key, value in grouped_AS_stats.items():
        if key != "no_as_number":
            temp[key] = len(value["relays"])

    as_cardinalities = OrderedDict(sorted(temp.items(), key=lambda t: t[1], reverse=True))

    return as_cardinalities

def get_AS_cw_aggregate(grouped_AS_stats):
    """
    Same as above, but sort by total cw weight
    """
    temp = {}
    for key, value in grouped_AS_stats.items():
        if key != "no_as_number":
            temp[key] = value["cw_fraction"]

    as_cw_aggregate = OrderedDict(sorted(temp.items(), key=lambda t: t[1], reverse=True))

    return as_cw_aggregate

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
    ipv6_store = []
    for relay in relays:
        if "or_addresses" in relay: # has or_addresses field
            for address in relay["or_addresses"]:
                res = get_ipv6_regex(address)
                if res is not None:
                    ipv6, str_len = res.group(0), len(res.group(0))
                    ipv6 = ipv6[1:str_len-1]
                    info = {
                        "ipv6_address": ipv6,
                        "fingerprint": relay["fingerprint"],
                        "bandwidth": relay["observed_bandwidth"],
                        "cw_fraction": relay["consensus_weight_fraction"],
                        "as_number": relay.setdefault("as_number", ""),
                        "country": relay.setdefault("country", "")
                    }
                    ipv6_store.append(info)

    return ipv6_store

def group_by_ipv4(relays):
    """
    Same as group_by_ipv6, but with ipv4 for each dictionary entry
    """
    ipv4_store = []
    for relay in relays:
        if "or_addresses" in relay:
            """ First entry is the ipv4 address """
            ipv4 = relay["or_addresses"][0][:relay["or_addresses"][0].index(":")] # remove port number
            info = {
                "ipv4_address": ipv4,
                "fingerprint": relay["fingerprint"],
                "bandwidth": relay["observed_bandwidth"],
                "cw_fraction": relay["consensus_weight_fraction"],
                "as_number": relay.setdefault("as_number", ""),
                "country": relay.setdefault("country", "")
            }
            ipv4_store.append(info)

    return ipv4_store

def get_ipv6_regex(address):
    """
    Finds the ipv6 (ignoring the port)
    from the relay's or_address field
    """
    res = re.search(r'\[.*\]', address, re.IGNORECASE)
    return res

def group_by_AS_org_id(relays):
    """
    This function takes the json file "as2orgname.json" and computes
    a histogram for each AS organization id/name

    The resulting dictionary would be used to award points and badges to relays
    which point to rare AS organizations.
    """
    print "[group_by_AS_org_id] Grouping by AS org_id"
    result_file = "app/static/json/as_2_org_histogram.json"

    result_store = {
        "as_2_org": {},
        "org_2_hist": {}
    }

    as2org_store = {}
    with open("as2orgname.json", "r") as fp:
        as2org_store = json.load(fp)
        fp.close()

    # now populate the result_store with the org_ids
    result_store["as_2_org"] = as2org_store

    # Initialize the org_2_hist with each org_id mapped to zero
    org_ids = [item[1][0] for item in as2org_store.items()]

    for org_id in org_ids:
        if org_id not in result_store["org_2_hist"]:
            result_store["org_2_hist"][org_id] = 0

    # Now loop through relays and create histogram
    for relay in relays:
        if "as_number" in relay:
            as_number = relay["as_number"][2:]
            if as_number in result_store["as_2_org"]:
                org_id = result_store["as_2_org"][as_number][0]
                result_store["org_2_hist"][org_id] += 1
            else:
                org_id = "Unknown/AS" + str(as_number)
                result_store["as_2_org"][as_number] = (org_id, org_id)
                result_store["org_2_hist"][org_id] = 1

    with open(result_file, "w+") as fp:
        fp.write(json.dumps(result_store))
        fp.close()

    print "[group_by_AS_org_id] End function"

    return result_store

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
              "exit_relays": [],
              "guard_relays": [],
              "bandwidth_rankings": [],
              "bandwidth_top10": [],
              "consensus_rankings": [],
              "consensus_top10": [],
              "exit_bandwidth_rankings": [],
              "exit_bandwidth_top10": [],
              "country_count_rankings": [],
              "country_cw_rankings": [],
              "country_exit_rankings": {},
              "country_guard_rankings": {},
              "port_rankings": [],
              "org_histogram": {}
             }

    aggregator = FamilyAggregator()
    families = aggregator.families
    relays = aggregator.relays
    exit_relays = [relay for relay in relays if "Exit" in relay["flags"]]
    guard_relays = [relay for relay in relays if "Guard" in relay["flags"]]

    groups["families"] = families
    groups["relays"] = relays
    groups["exit_relays"] = exit_relays
    groups["guard_relays"] = guard_relays

    # Get rankings and stats of entire network
    groups["bandwidth_rankings"] = sorted(families, key=lambda family: family["observed_bandwidth"], reverse=True)
    groups["consensus_rankings"] = sorted(families, key=lambda family: family["consensus_weight_fraction"], reverse=True)
    groups["exit_bandwidth_rankings"] = sorted(families, key=lambda family: family["exit_bandwidth"], reverse=True)
    groups["country_count_rankings"], groups["country_cw_rankings"] = record_country_stats(relays)
    groups["country_exit_rankings"] = record_country_stats_json(exit_relays)
    groups["country_exit_ordered_by_relay_count"] = sorted([ (country, count) for country, count in groups["country_exit_rankings"].items() if count != 0 ], key=lambda item: item[1])
    groups["country_guard_rankings"] = record_country_stats_json(guard_relays)
    groups["country_guard_ordered_by_relay_count"] = sorted([ (country, count) for country, count in groups["country_guard_rankings"].items() if count != 0 ], key=lambda item: item[1])
    groups["port_rankings"] = record_port_stats(relays)
    groups["org_exit_histogram"] = group_by_AS_org_id(exit_relays)
    groups["org_exit_ordered"] = sorted( [(org_id, count) for org_id, count in groups["org_exit_histogram"]["org_2_hist"].items() if count != 0], key=lambda item: item[1])
    groups["org_guard_histogram"] = group_by_AS_org_id(guard_relays)
    groups["org_guard_ordered"] = sorted( [(org_id, count) for org_id, count in groups["org_guard_histogram"]["org_2_hist"].items() if count != 0], key=lambda item: item[1])

    stats_aggregator = RelayStatsAggregator(groups)

    # Assign badges to each family
    print "[relay_rank] Assigning badges to each family"
    for family in families:
        temp = family
        family["badges"] = stats_aggregator.analyze_family(temp)
    print "[relay_rank] End assigning badges to each family"

    # Reassign the groups with updated badges.
    groups["families"] = families
    groups["relays"] = relays

    groups["bandwidth_rankings"] = sorted(families, key=lambda family: family["observed_bandwidth"], reverse=True)
    groups["consensus_rankings"] = sorted(families, key=lambda family: family["consensus_weight_fraction"], reverse=True)
    groups["exit_bandwidth_rankings"] = sorted(families, key=lambda family: family["exit_bandwidth"], reverse=True)

    # These are used for the index page
    # Number of relays to show on the front page
    roster_cut = 320

    groups["bandwidth_top10"] = groups["bandwidth_rankings"][:roster_cut]
    groups["consensus_top10"] = groups["consensus_rankings"][:roster_cut]
    groups["exit_bandwidth_top10"] = groups["exit_bandwidth_rankings"][:roster_cut]

    # Stores bandwidth rankings, consensus_weight rankings, all.json
    print "[relay_rank] Storing rankings"
    store_rankings(groups)
    print "[relay_rank] End storing rankings"

    if static_store_strategy == "REMOTE":
        # Uploads the data and stats to AWS S3
        print "[relay_rank] Uploading to S3"
        from upload import *
        map(upload, assets)
