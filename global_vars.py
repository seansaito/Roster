import os

### Global vars ###

# Keys for Amazon S3
acc_key = os.environ["AWS_ACCESS_KEY"]
acc_sec = os.environ["AWS_SECRET_KEY"]
bucket = os.environ["AWS_BUCKET"]

# Script directory
script_dir = os.path.dirname(__file__)

# Relative paths
rel_paths = {
    "bandwidth": "app/static/json/top10_bandwidth.json",
    "consensus": "app/static/json/top10_consensus.json",
    "all_families": "app/static/json/all.json"
}

# Absolute paths
abs_paths = {
    "bandwidth": os.path.join(script_dir, rel_paths["bandwidth"]),
    "consensus": os.path.join(script_dir, rel_paths["consensus"]),
    "all_families": os.path.join(script_dir, rel_paths["all_families"])
}

# Flags for the relays
flags = ["Authority", "BadExit", "Exit", "Fast", "Guard", "HSDir", "Running", "Stable", "V2Dir", "Valid"]
