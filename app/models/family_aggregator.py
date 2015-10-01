from app import app
from app.models.onionoo_connector import OnionooConnector
from app.controllers.tshirt_validator import check_tshirt
from difflib import SequenceMatcher

# Implementation of the Singleton class
class Singleton(type):
    _instances = {}
    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            print "[Singleton] First instance"
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]

"""
    This class gets relay data from Onionoo using an OnionooConnector instance
    and groups them together into relays
"""
class FamilyAggregator(object):
    # FamilyAggregator should be a singleton
    __metaclass__ = Singleton

    def __init__(self):
        self.c = OnionooConnector("details")
        self.relays = self.c.details_relays
        self.families = self.group_by_family()

    # Getters
    def get_relays(self):
        return self.relays

    def get_num_relays(self):
        return len(self.relays)

    def get_families(self):
        return self.families

    def get_num_families(self):
        return len(self.families)

    # Helper functions for sieve algorithm
    def fill_in(self, relay, details, family):
        for detail in details:
            family[detail] += relay.setdefault(detail, 0)

    def parse_bitcoin(self, contact):
        if contact == "":
            return ("", "")
        words = contact.split()
        address = ""
        for word in words:
            if word[0] == "1" or word[0] == "3" and len(word) > 25 and len(word) < 36:
                address = word
                words.remove(word)
        if "bitcoin" in words:
            words.remove("bitcoin")
        return (address, " ".join(words))

    def filter_fingerprints(self, relay, family):
        temp = relay
        new_fam = []
        if "extended_family" in temp:
            for fingerprint in temp["extended_family"]:
                if "$" + temp["fingerprint"] == fingerprint:
                    if family != "":
                        # family["badges"]["self_referencing"] += 1
                        continue
                elif len(fingerprint) < 41:
                    continue
                elif len(fingerprint) > 41:
                    new_fam.append(fingerprint[:41])
                    continue
                else:
                    for char in fingerprint[1:].upper():
                        if not ("0" <= char <= "9" or "A" <= char <= "F"):
                            continue
                new_fam.append(fingerprint)
        else:
            return temp
        temp["extended_family"] = new_fam
        return temp

    def has_duplicate_contacts(self, relay, family):
        for contact in family["contact"]:
            if SequenceMatcher(None, contact, relay["contact"]).ratio() > 0.8:
                return True
        return False

    # Sieve algorithm
    def group_by_family(self):
        # For storing the families
        families = []

        relays = self.relays

        # This number will be used for the sieve algorithm later
        num_relays = len(relays)

        # Initialization - set all flags to false
        all_relays = [[relay, False] for relay in relays]

        badges = {
            "bandwidth": 0,
            "exit_bandwidth": 0,
            "consensus_weight": 0,
            "num_countries": 0,
            "num_relays": 0,
            "has_contact_for_half": 0,
            "has_guard_for_half": 0,
            "rank": 0,
            "runs_recommended_tor": 0,
            "liberal_exit:": 0,
            "rare_countries": 0,
            "geo_diversity": 0,
            "self_referencing": 0
        }

        print "[group_by_family] Begin sieve"

        for i in range(num_relays):
            # bef_relay is the relay before its fingerprints in the family
            # field are filtered
            bef_relay, visited = all_relays[i]

            if visited:
                continue
            else:
                # Mark as visited
                all_relays[i][1] = True

                # Init of family dictionary
                family = {"observed_bandwidth": 0,
                          "exit_bandwidth": 0,
                          "consensus_weight_fraction": 0,
                          "consensus_weight": 0,
                          "families": [], "contact": [],
                          "middle_probability": 0,
                          "exit_probability": 0, "bitcoin_addr": "None",
                          "bandwidth_points": 0, "consensus_points": 0,
                          "countries": [], "exit": 0, "guard": 0,
                          "t_shirts": [],
                          "eligible_for_tshirt": False}

                relay = self.filter_fingerprints(bef_relay, family)
                family["families"].append(relay)

                if "Exit" in relay:
                    family["exit"] += 1
                    family["exit_bandwidth"] += relay["observed_bandwidth"] * relay["exit_probability"]

                if "Guard" in relay:
                    family["guard"] += 1

                if "country" in relay:
                    family["countries"].append(relay["country"])

                if check_tshirt(relay["fingerprint"]):
                    family["t_shirts"].append(relay["fingerprint"])
                    family["eligible_for_tshirt"] = True

                # Used for checking if relay is related to other relays
                fingerprint = "$" + relay["fingerprint"]

                self.fill_in(relay, ["middle_probability", "exit_probability", "observed_bandwidth", "consensus_weight", "consensus_weight_fraction"], family)

                bitcoin_addr, contact = self.parse_bitcoin(relay.setdefault("contact", ""))
                if bitcoin_addr != "":
                    family["bitcoin_addr"] = bitcoin_addr
                family["contact"].append(contact)

                relay["extended_family"] = relay.setdefault("effective_family", []) + relay.setdefault("indirect_family", [])

                if "extended_family" in relay:
                    for j in range(num_relays):
                        other_relay, other_visited = all_relays[j]
                        other_relay["extended_family"] = other_relay.setdefault("effective_family", []) + other_relay.setdefault("indirect_family", [])
                        if other_visited:
                            continue
                        else:
                            if "extended_family" in other_relay and fingerprint in other_relay["extended_family"] or "$" + other_relay["fingerprint"] in relay["extended_family"]:
                                family["families"].append(other_relay)
                                self.fill_in(other_relay, ["middle_probability", "exit_probability", "observed_bandwidth", "consensus_weight", "consensus_weight_fraction"], family)
                                if "country" in other_relay and other_relay["country"] not in family["countries"]:
                                    family["countries"].append(other_relay["country"])
                                if check_tshirt(other_relay["fingerprint"]):
                                    family["t_shirts"].append(other_relay["fingerprint"])
                                    family["eligible_for_tshirt"] = True
                                if "Exit" in other_relay["flags"]:
                                    family["exit"] += 1
                                    family["exit_bandwidth"] += other_relay["exit_probability"] * other_relay["observed_bandwidth"]
                                if "Guard" in other_relay["flags"]:
                                    family["guard"] += 1
                                if "contact" in other_relay and not self.has_duplicate_contacts(other_relay, family):
                                    family["contact"].append(other_relay["contact"])
                                all_relays[j][1] = True

                family["families"] = sorted(family["families"], key=lambda relay: relay["observed_bandwidth"], reverse=True)
                family["bandwidth_points"] = family["observed_bandwidth"] + family["observed_bandwidth"] * family["exit_probability"]
                family["consensus_points"] = family["consensus_weight"] * family["exit_probability"]
                family["contact"] = sorted(family["contact"])

                families.append(family)

            # End sieve
            print "[group_by_family] End sieve"

            return families
