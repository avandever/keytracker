"""The DATABASE_URL with the database name swapped for the scratch one."""
import os
import re

print(re.sub(r"/[^/?]+(\?|$)", "/keytracker_playoff_scratch\\1", os.environ["DATABASE_URL"]))
