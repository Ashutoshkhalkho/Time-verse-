import sys
import os

# Add site-packages and backend to sys.path
base_dir = os.path.dirname(os.path.abspath(__file__))
site_packages = os.path.join(base_dir, ".venv", "Lib", "site-packages")

sys.path.insert(0, site_packages)
sys.path.insert(0, base_dir)

import pytest

exit_code = pytest.main(["-v", os.path.join(base_dir, "tests")])
sys.exit(exit_code)
