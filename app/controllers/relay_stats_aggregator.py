"""
    RelayStatsAggregator aggregates and stores numerous stats from all running
    relays. It is mainly used by the relay_rank script to get data about the whole
    Tor network. It accepts the groups of relays and families as inputs for its constructor
"""

# Imports
from app import app
from global_vars import *

class RelayStatsAggregator(object):

    def __init__(self, grouped_relays):
        self.families = grouped_relays["families"]
        self.relays = grouped_relays["relays"]
        self.num_families = len(self.families)
        self.num_relays = len(self.relays)
        self.bandwidth_rankings = grouped_relays["bandwidth_rankings"]
        self.consensus_weight_rankings = grouped_relays["consensus_rankings"]
        self.exit_bandwidth_rankings = grouped_relays["exit_bandwidth_rankings"]
        self.country_count_rankings = grouped_relays["country_count_rankings"]
        self.country_cw_rankings = grouped_relays["country_cw_rankings"]
        self.port_rankings = grouped_relays["port_rankings"]

    def find_by_fingerprint(self, fingerprint, families):
        counter = 1
        for family in families:
            for relay in family["families"]:
                if relay["fingerprint"] == fingerprint:
                    return (family, counter)
            counter += 1
        return ""

    def get_badge(self, counter):
        percentile = float(self.num_relays - counter) / float(self.num_relays)
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
        return self.get_badge(counter)

    def get_exit_bandwidth_percentile(self, fingerprint):
        family, counter = self.find_by_fingerprint(fingerprint, self.exit_bandwidth_rankings)
        return self.get_badge(counter)

    def get_cw_percentile(self, fingerprint):
        family, counter = self.find_by_fingerprint(fingerprint, self.consensus_weight_rankings)
        return self.get_badge(counter)

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

    def is_self_referencing(self, fingerprint):
        family, counter = self.find_by_fingerprint(fingerprint, self.families)
        for relay in family["families"]:
            if "family" in relay and "$" + relay["fingerprint"] in relay["family"]:
                return True
        return False

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

    def analyze_family(self, family):
        badges = {}
        fingerprint = family["families"][0]["fingerprint"]
        badges["bandwidth"] = self.get_bandwidth_percentile(fingerprint)
        badges["consensus_weight"] = self.get_cw_percentile(fingerprint)
        badges["exit_bandwidth"] = self.get_exit_bandwidth_percentile(fingerprint)
        badges["num_countries"] = self.get_num_countries_badge(fingerprint)
        badges["num_relays"] = self.get_num_relays_badge(fingerprint)
        badges["has_contact_for_half"] = self.get_contact_badge(fingerprint)
        badges["has_guard_for_half"] = self.get_guard_badge(fingerprint)
        badges["self_referencing"] = self.is_self_referencing(fingerprint)
        badges["geo_diversity"] = self.has_geo_diversity(fingerprint)
        badges["rare_countries"] = self.get_rare_countries_badge(fingerprint)
        badges["liberal_exit"] = self.get_liberal_exit_badge(fingerprint)
        badges["runs_recommended_tor"] = self.get_tor_version_badge(fingerprint)
        return badges
