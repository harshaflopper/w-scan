"""
pytest conftest — adds backend root to sys.path so all
`from cv.x import ...` and `from scoring.x import ...` imports
resolve correctly when running `pytest` from d:\hackthon\w-scan\backend\
"""
import sys
import os

# Insert backend root so package imports work without installing the project
sys.path.insert(0, os.path.dirname(__file__))
