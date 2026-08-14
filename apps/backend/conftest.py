import sys
import os

# Ensure app/ is importable
sys.path.insert(0, os.path.dirname(__file__))

# Prevent pytest from collecting source files whose names start with test_
collect_ignore_glob = ["app/**"]
