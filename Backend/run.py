"""
Root-level IDE Runner

Allows running the download manager directly from an IDE "Run" button
without using command line package switches (-m).
"""

import sys
import os

# Add the project directory to python's import path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import the main entrypoint from the download_manager package
from download_manager.main import main

if __name__ == "__main__":
    main()
