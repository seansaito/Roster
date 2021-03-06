import os

### Global vars ###

# Keys for Amazon S3
acc_key = os.environ["AWS_ACCESS_KEY"]
acc_sec = os.environ["AWS_SECRET_KEY"]
bucket = os.environ["AWS_BUCKET"]

# Switch for storing static files locally or uploading to S3
# The value must be either "LOCAL" or "REMOTE"
static_store_strategy = os.environ["ROSTER_STATIC_STRATEGY"]

# Script directory
script_dir = os.path.dirname(__file__)

# Relative paths
rel_paths = {
    "top10_bandwidth": "app/static/json/top10_bandwidth.json",
    "top10_consensus": "app/static/json/top10_consensus.json",
    "all": "app/static/json/all.json"
}

# Absolute paths
abs_paths = {
    "top10_bandwidth": os.path.join(script_dir, rel_paths["top10_bandwidth"]),
    "top10_consensus": os.path.join(script_dir, rel_paths["top10_consensus"]),
    "all": os.path.join(script_dir, rel_paths["all"])
}

# Database paths
db_paths = {
    "fingerprint_to_uuid": "app/static/json/fingerprint_to_uuid.json",
    "uuid_to_family": "app/static/json/uuid_to_family.json"
}

# Absolute db_paths
db_abs_paths = {
    "fingerprint_to_uuid": os.path.join(script_dir, db_paths["fingerprint_to_uuid"]),
    "uuid_to_family": os.path.join(script_dir, db_paths["uuid_to_family"])
}

# Flags for the relays
flags = ["Authority", "BadExit", "Exit", "Fast", "Guard", "HSDir", "Running", "Stable", "V2Dir", "Valid"]
