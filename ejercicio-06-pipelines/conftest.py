import sys
import os

# Dynamically add the directory of this exercise to the beginning of sys.path
# so that pytest can discover and import all local modules cleanly.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
