import re, uuid, time, datetime
from global_vars import *

def add_uuid(flag, data_store):
    """
    Function that adds uuid to every relay. The uuids are taken
    from static/json/fingerprint_to_uuid.json and static/json/uuid_to_family.json. The uuids
    help keep persistent data about each family by tagging every relay within the family

    Args:
        flag (str)          :  Indicates type of data_store ("relays" or "families")
        data_store (list)   :  List of objects. Should correspond to flag. So if flag is "relays",
                               data_store should be a list of relays
    """

    ### Load the json files from db_abs_paths
    f = open(db_abs_paths["fingerprint_to_uuid"], "r+")
    fingerprint_to_uuid = json.load(f)
    f.close()

    f = open(db_abs_paths["uuid_to_family"], "r+")
    uuid_to_family = json.load(f)
    f.close()

    # fingerprint_to_uuid, uuid_to_family = {}, {}
    #
    # for filename, store in [("fingerprint_to_uuid", fingerprint_to_uuid), ("uuid_to_family", uuid_to_family)]:
    #     f = open(db_abs_paths[filename], "r+")
    #     store = json.load(f)
    #     f.close()

    ### Now loop through stores
    if flag == "relays":
        for relay in data_store:
            if relay["fingerprint"] in fingerprint_to_uuid:
                ### We've seen this relay before
                relay["uuid"] = fingerprint_to_uuid[relay["fingerprint"]]
            else:
                ### New relay, see if any family members have a uuid
                ### Create extended_family field
                if "extended_family" not in relay:
                    relay["extended_family"] = relay.setdefault("effective_family",[]) + relay.setdefault("indirect_family", [])
                for fingerprint in relay["extended_family"]:
                    ### make sure to take out initial $ sign
                    if fingerprint[1:] in fingerprint_to_uuid:
                        relay["uuid"] = fingerprint_to_uuid[fingerprint[1:]]
                        ### Update the store
                        fingerprint_to_uuid[relay["fingerprint"]] = relay["uuid"]
                ### At this point, if relay has no uuid field, then its family members also did not uuids.
                ### Hence we create a new uuid
                new_uuid = str(uuid.uuid4())
                relay["uuid"] = new_uuid
                ### Update the store
                fingerprint_to_uuid[relay["fingerprint"]] = relay["uuid"]
        ### Now we update the store on disk
        f = open(db_abs_paths["fingerprint_to_uuid"], "w+")
        f.write(json.dumps(fingerprint_to_uuid))
        f.close()
        return data_store
    else:
        ### flag is families
        ### Since add_uuid should be called for relays first, we just pull each uuid from
        ### fingerprint_to_uuid.json. Then we add new families to uuid_to_family.json
        for family in data_store:
            for relay in family["families"]:
                try:
                    relay["uuid"] = fingerprint_to_uuid[relay["fingerprint"]]
                except:
                    print "[add_uuid] Relay not tagged in fingerprint_to_uuid.json"
            ### Now see if fingerprint is found in uuid_to_family. If not, then create a new entry
            fam_uuid = family["families"][0]["uuid"]
            ### Update to latest family data
            uuid_to_family[fam_uuid] = family
        ### Now update the store
        f = open(db_abs_paths["uuid_to_family"], "w+")
        f.write(json.dumps(uuid_to_family))
        f.close()
        return data_store
