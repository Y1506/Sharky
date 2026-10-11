#!/usr/bin/env python3
"""
Sharky - Root Launcher
Forwards commands to the Backend service runner.
"""
import os
import sys
from pathlib import Path

# Add Backend to Python path
backend_dir = Path(__file__).resolve().parent / "Backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

if __name__ == "__main__":
    from download_manager.main import main
    main()
