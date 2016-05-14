"""
    RelayStatsAggregator aggregates and stores numerous stats from all running
    relays. It is mainly used by the relay_rank script to get data about the whole
    Tor network. It accepts the groups of relays and families as inputs for its constructor
"""

# Imports
from app import app
import os, json, re
from global_vars import *

### Global vars ###
coefficient_file = "app/static/json/rank_coefficients.json"

class RelayStatsAggregator(object):

    def __init__(self, grouped_relays):
        self.families = grouped_relays["families"]
        self.relays = grouped_relays["relays"]
        self.num_families = len(self.families)
        self.num_relays = len(self.relays)
        self.bandwidth_rankings = grouped_relays["bandwidth_rankings"]
        self.consensus_weight_rankings = grouped_relays["consensus_rankings"]
        self.exit_bandwidth_rankings = grouped_relays["exit_bandwidth_rankings"]
        self.age_rank = grouped_relays["age_rank"]
        self.uptime_rank = grouped_relays["uptime_rank"]
        self.country_count_rankings = grouped_relays["country_count_rankings"]
        self.country_cw_rankings = grouped_relays["country_cw_rankings"]
        self.country_exit_rankings = grouped_relays["country_exit_rankings"]
        self.country_exit_ordered_by_relay_count = grouped_relays["country_exit_ordered_by_relay_count"]
        self.country_guard_rankings = grouped_relays["country_guard_rankings"]
        self.country_guard_ordered_by_relay_count = grouped_relays["country_guard_ordered_by_relay_count"]
        self.port_rankings = grouped_relays["port_rankings"]
        self.org_exit_histogram = grouped_relays["org_exit_histogram"]
        self.org_exit_ordered = grouped_relays["org_exit_ordered"]
        self.org_guard_histogram = grouped_relays["org_guard_histogram"]
        self.org_guard_ordered = grouped_relays["org_guard_ordered"]

    def find_by_fingerprint(self, fingerprint, families):
        counter = 1
        for family in families:
            for relay in family["families"]:
                if relay["fingerprint"] == fingerprint:
                    return (family, counter)
            counter += 1
        return ""

    def get_badge(self, counter, denom):
        percentile = float(denom - counter) / float(denom)
        if percentile < 0.2:
            return (percentile, "None")
        elif percentile < 0.4:
            return (percentile, "bronze")
        elif percentile < 0.6:
            return (percentile, "silver")
        elif percentile < 0.8:
            return (percentile, "gold")
        else:
            return (percentile, "platinum")

    def get_bandwidth_percentile(self, fingerprint):
        family, counter = self.find_by_fingerprint(fingerprint, self.bandwidth_rankings)
        return self.get_badge(counter, self.num_families)

    def get_exit_bandwidth_percentile(self, fingerprint):
        family, counter = self.find_by_fingerprint(fingerprint, self.exit_bandwidth_rankings)
        percentile = float(self.num_relays - counter) / float(self.num_relays)
        if percentile < 0.94:
            return (percentile, "None")
        elif percentile < 0.95:
            return (percentile, "bronze")
        elif percentile < 0.97:
            return (percentile, "gold")
        else:
            return (percentile, "platinum")

    def get_cw_percentile(self, fingerprint):
        family, counter = self.find_by_fingerprint(fingerprint, self.consensus_weight_rankings)
        return self.get_badge(counter, self.num_families)

    def get_num_countries_badge(self, fingerprint):
        family, counter = self.find_by_fingerprint(fingerprint, self.families)
        numCountries = len(family["countries"])
        if numCountries >= 20:
            return (numCountries, "platinum")
        elif numCountries >= 10:
            return (numCountries, "gold")
        elif numCountries >= 3:
            return (numCountries, "silver")
        else:
            return (numCountries, "bronze")

    def get_num_relays_badge(self, fingerprint):
        family, counter = self.find_by_fingerprint(fingerprint, self.families)
        numRelays = len(family["families"])
        if numRelays >= 20:
            return (numRelays, "platinum")
        elif numRelays >= 10:
            return (numRelays, "gold")
        elif numRelays >= 5:
            return (numRelays, "silver")
        elif numRelays >= 2:
            return (numRelays, "bronze")
        else:
            return (numRelays, "None")

    def get_contact_badge(self, fingerprint):
        family, counter = self.find_by_fingerprint(fingerprint, self.families)
        numRelays = len(family["families"])
        numContact = sum([1 for relay in family["families"] if "contact" in relay])
        return float(numContact)/float(numRelays) >= 0.5

    def get_guard_badge(self, fingerprint):
        family, counter = self.find_by_fingerprint(fingerprint, self.families)
        numRelays = len(family["families"])
        numGuard = sum([1 for relay in family["families"] if "Guard" in relay["flags"]])
        return float(numGuard)/float(numRelays) >= 0.5

    def has_geo_diversity(self, fingerprint):
        family, counter = self.find_by_fingerprint(fingerprint, self.families)
        return len(family["families"]) >= 5 and float(len(family["countries"])) / float(len(family["families"])) >= 0.5

    def get_rare_countries_badge(self, fingerprint):
        family, counter = self.find_by_fingerprint(fingerprint, self.families)
        lone_relay_in_country = False
        rare_countries = []
        for relay in family["families"]:
            if "country" in relay:
                if self.country_count_rankings[relay["country"].upper()] == 1:
                    lone_relay_in_country = True
                    rare_countries.append(relay["country"].upper())
                elif self.country_count_rankings[relay["country"].upper()] <= 10:
                    rare_countries.append(relay["country"].upper())
        return (lone_relay_in_country, rare_countries)

    # Helper function for get_liberal_exit_badge
    def parse_between(self, string):
        if "-" in string:
            res = string.split("-")
            return [int(res[0]), int(res[1])]
        return [int(string)]

    def get_liberal_exit_badge(self, fingerprint):
        family, counter = self.find_by_fingerprint(fingerprint, self.families)
        liberal_exits = []
        init_vals = {"accept": 1, "reject": 0}

        for relay in family["families"]:
            policy = relay["exit_policy_summary"].keys()[0]
            if relay["exit_policy_summary"][policy][0] == "1-65535":
                continue

            ports, offset_value = relay["exit_policy_summary"][policy], init_vals[policy]
            opposite_offset = (offset_value + (-1)) % 2

            # Initialization
            relay_ports = {}
            for i in range(1, 65536):
                relay_ports[i] = opposite_offset

            for interval in ports:
                parsed = self.parse_between(interval)
                if len(parsed) == 1:
                    relay_ports[parsed[0]] = offset_value
                else:
                    for i in range(parsed[0], parsed[1]+1):
                        relay_ports[i] = offset_value

            # See if each port that the relay allows is a rare port
            for port in relay_ports.keys():
                if self.port_rankings[port] <= 500:
                    liberal_exits.append(port)

        totalLiberal = len(liberal_exits)
        if totalLiberal >= 50:
            return (totalLiberal, "platinum")
        elif totalLiberal >= 30:
            return (totalLiberal, "gold")
        elif totalLiberal >= 10:
            return (totalLiberal, "silver")
        elif totalLiberal >= 5:
            return (totalLiberal, "bronze")
        else:
            return (totalLiberal, "None")
        return

    def get_tor_version_badge(self, fingerprint):
        family, counter = self.find_by_fingerprint(fingerprint, self.families)
        for relay in family["families"]:
            if not relay.setdefault("runs_recommended_tor", False):
                return False
        return True

    def get_country_diversity_badge(self, fingerprint, flag):
        # print "[get_country_diversity_badge] Called"
        family, c = self.find_by_fingerprint(fingerprint, self.families)

        rankings = {}
        countries_ordered_by_relay_count = []

        if flag == "Guard":
            # Will be using relay_count => can switch to cw_fraction if necessary
            rankings = self.country_guard_rankings["relay_count"]
            countries_ordered_by_relay_count = self.country_guard_ordered_by_relay_count
        else:
            rankings = self.country_exit_rankings["relay_count"]
            countries_ordered_by_relay_count = self.country_exit_ordered_by_relay_count

        # This excludes any country without any relay
        # countries_ordered_by_relay_count = sorted([ (country, count) for country, count in rankings.items() if count != 0 ], key=lambda item: item[1])

        num_countries = len(countries_ordered_by_relay_count)
        smallest_percentile = 1.0

        for relay in family["families"]:
            # We only care about relays with either the Guard or Exit flag
            if flag in relay["flags"]:
                counter = 0
                for country, count in countries_ordered_by_relay_count:
                    if relay["country"].upper() == country:
                        # print "[get_country_diversity_badge] Hit with counter: %d" % counter
                        break
                    else:
                        counter += 1
                percentile = float(counter) / float(num_countries)
                # print percentile
                if percentile < smallest_percentile:
                    smallest_percentile = percentile
            else:
                continue

        # print smallest_percentile

        # print "[get_country_diversity_badge] Percentage is %.2f" % (1.0 - float(smallest_percentile))

        if smallest_percentile > 0.8:
            return (1.0 - smallest_percentile, "None")
        elif smallest_percentile > 0.6:
            return (1.0 - smallest_percentile, "bronze")
        elif smallest_percentile > 0.4:
            return (1.0 - smallest_percentile, "silver")
        elif smallest_percentile > 0.2:
            return (1.0 - smallest_percentile, "gold")
        else:
            return (1.0 - smallest_percentile, "platinum")

    def get_org_id_diversity_badge(self, fingerprint, flag):
        """
            Same deal with get_country_diversity_badge.
            For each family, award badge based on how rare the org_ids are.
        """
        family, counter = self.find_by_fingerprint(fingerprint, self.families)

        histogram = {}

        if flag == "Guard":
            histogram = self.org_guard_histogram
            histogram["ordered_histogram"] = self.org_guard_ordered
        else:
            histogram = self.org_exit_histogram
            histogram["ordered_histogram"] = self.org_exit_ordered

        # Very bad time performance
        # histogram["ordered_histogram"] = sorted( [(org_id, count) for org_id, count in histogram["org_2_hist"].items() if count != 0], key=lambda item: item[1])

        num_org_ids = len(histogram["ordered_histogram"])
        smallest_percentile = 1.0

        for relay in family["families"]:
            if flag in relay["flags"] and "as_number" in relay:
                relay_org_id = histogram["as_2_org"][relay["as_number"][2:]][0]
                counter = 0
                for org_id, count in histogram["ordered_histogram"]:
                    if relay_org_id == org_id:
                        break
                    else:
                        counter += 1
                percentile = float(counter) / float(num_org_ids)
                if percentile < smallest_percentile:
                    smallest_percentile = percentile

        if smallest_percentile > 0.8:
            return (1.0 - smallest_percentile, "None")
        elif smallest_percentile > 0.6:
            return (1.0 - smallest_percentile, "bronze")
        elif smallest_percentile > 0.4:
            return (1.0 - smallest_percentile, "silver")
        elif smallest_percentile > 0.2:
            return (1.0 - smallest_percentile, "gold")
        else:
            return (1.0 - smallest_percentile, "platinum")

    def get_ipv6_regex(self, address):
        """
        Helper function

        Finds the ipv6 (ignoring the port)
        from the relay's or_address field
        """
        res = re.search(r'\[.*\]', address, re.IGNORECASE)
        return res

    def get_ipv6_badge(self, fingerprint, for_exit):
        """
        If a family has an ipv6, then return True
        """
        family, counter = self.find_by_fingerprint(fingerprint, self.families)

        for relay in family["families"]:
            if for_exit and "Exit" not in relay["flags"]:
                continue
            else:
                if "or_addresses" in relay:
                    for address in relay["or_addresses"]:
                        res = self.get_ipv6_regex(address)
                        if res is not None:
                            return True

        return False

    def get_age_of_family_badge(self, fingerprint, curr_time):
        family, counter = self.find_by_fingerprint(fingerprint, self.age_rank)
        return self.get_badge(counter, self.num_families)

    def get_maximum_uptime_badge(self, fingerprint, curr_time):
        family, counter = self.find_by_fingerprint(fingerprint, self.uptime_rank)
        return self.get_badge(counter, self.num_families)

    ### For total overall rank ###

    def load_json(self, filename):
        store = {}
        try:
            with open(filename, "r+") as fp:
                store = json.load(fp)
                fp.close()
                return store
        except:
            return store

    def get_overall_rank(self, badges):
        """
        This function takes a processed dictionary of badges and points
        and computes a total linear combination using the values of each
        category and coefficients defined in the json file rank_coefficients.json
        """
        overall_rank = 0
        coefficients = self.load_json(coefficient_file)

        if len(coefficients) == 0:
            print "[RelayStatsAggregator::get_overall_rank] Error loading coefficients"
            return 0

        for key, value in badges.items():
            coefficient = coefficients[key]
            if type(value) is tuple:
                overall_rank += coefficient * value[0]
            elif type(value) is bool:
                overall_rank += coefficient * int(value)
            else:
                print "[RelayStatsAggregator::get_overall_rank] Error type in ranking (%s)" % type(value)
                return 0

        return overall_rank

    def analyze_family(self, family, curr_time):
        badges = {}
        fingerprint = family["families"][0]["fingerprint"]
        badges["bandwidth"] = self.get_bandwidth_percentile(fingerprint)
        badges["consensus_weight"] = self.get_cw_percentile(fingerprint)
        badges["exit_bandwidth"] = self.get_exit_bandwidth_percentile(fingerprint)
        badges["num_countries"] = self.get_num_countries_badge(fingerprint)
        badges["num_relays"] = self.get_num_relays_badge(fingerprint)
        badges["age_of_family"] = self.get_age_of_family_badge(fingerprint, curr_time)
        badges["maximum_uptime"] = self.get_maximum_uptime_badge(fingerprint, curr_time)
        badges["has_contact_for_half"] = self.get_contact_badge(fingerprint)
        badges["has_guard_for_half"] = self.get_guard_badge(fingerprint)
        badges["geo_diversity"] = self.has_geo_diversity(fingerprint)
        badges["rare_countries"] = self.get_rare_countries_badge(fingerprint)
        badges["liberal_exit"] = self.get_liberal_exit_badge(fingerprint)
        badges["runs_recommended_tor"] = self.get_tor_version_badge(fingerprint)
        badges["country_exit_diversity"] = self.get_country_diversity_badge(fingerprint, "Exit")
        badges["country_guard_diversity"] = self.get_country_diversity_badge(fingerprint, "Guard")
        badges["org_exit_diversity"] = self.get_org_id_diversity_badge(fingerprint, "Exit")
        badges["org_guard_diversity"] = self.get_org_id_diversity_badge(fingerprint, "Guard")
        badges["has_ipv6"] = self.get_ipv6_badge(fingerprint, False)
        badges["has_ipv6_for_exit"] = self.get_ipv6_badge(fingerprint, True)
        badges["overall_rank"] = self.get_overall_rank(badges)
        return badges
