#!/usr/bin/python

import sys
import logging
import os
logging.basicConfig(stream=sys.stderr)
sys.path.insert(0, "/var/www/Roster/")

# set environ variables
os.environ["AWS_ACCESS_KEY"] = "AKIAJBXFTGPXHAFQBXVA"
os.environ["AWS_SECRET_KEY"] = "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"
os.environ["AWS_BUCKET"] = "roster-tor"

from app import app as application
application.secret_key="Hakuryuu1000"
