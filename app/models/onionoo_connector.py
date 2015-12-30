"""
    OnionooConnector connects to onionoo and retrieves relay data, mainly
    the bandwidth, details, and uptime documents.
    The constructor can be passed with arguments that indicates which documents
    it should fetch.
"""

from app import app
import httplib2, json

class OnionooConnector(object):

    """
        Initializes OnionooConnector with Onionoo documents specified in arguments.
        For example, calling
            c = OnionooConnector("details")
        will only initialize the instance with the details document.
    """
    def __init__(self, *documents):
        self.details_relays, self.uptime_relays, self.bandwidth_relays = "", "", ""
        if "details" in documents:
            self.details_relays = self.fetch_data("details")
        if "uptime" in documents:
            self.uptime_relays = self.fetch_data("uptime")
        if "bandwidth" in documents:
            self.bandwidth_relays = self.fetch_data("bandwidth")

    """
        Makes GET request to the Onionoo API and returns the response's content.
    """
    def fetch_data(self, data):
        h = httplib2.Http(".cache")

        print "[fetch_data] Getting json data via onionoo"
        url = "https://onionoo.torproject.org/{type}?running=true".format(type=data)
        print "[fetch_data] Making request to %s" % url
        resp, content = h.request(url, "GET")

        return self.convert_from_raw(content)

    """
        Converts content from fetch_data to json
    """
    def convert_from_raw(self, content):
        json_data = json.loads(content)
        return json_data["relays"]

    def find_by_fingerprint(self, relays, fingerprint):
        for relay in relays:
            if relay["fingerprint"] == fingerprint:
                return relay

    def dictify_relays(self, relays):
        """ Turn a list of relays into a dict for easy retrieval """
        res = {}
        for relay in relays:
            res[relay["fingerprint"]] = relay
        return res
