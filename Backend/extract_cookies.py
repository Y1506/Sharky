"""
Cookie Extraction Helper — Run on HOST machine (not inside Docker).

Extracts YouTube cookies from Zen Browser or Brave and saves them
to cookies.txt in Netscape format. Mount this file into the container.

Usage:
    python extract_cookies.py
    python extract_cookies.py --browser brave
    python extract_cookies.py --output ./my_cookies.txt
"""

import argparse
import sys
import os

# Add parent directory to path so we can import from the package
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from download_manager.cookies import CookieManager
from download_manager.config import Config


def main():
    parser = argparse.ArgumentParser(description="Extract YouTube cookies from browser for Docker use")
    parser.add_argument("--browser", choices=["zen", "brave"], default=None,
                        help="Force a specific browser (default: try zen, then brave)")
    parser.add_argument("--output", default="./cookies.txt",
                        help="Output cookie file path (default: ./cookies.txt)")
    parser.add_argument("--profile", default=None,
                        help="Manual browser profile directory path")
    args = parser.parse_args()

    config = Config()

    if args.browser:
        config.COOKIE_BROWSER_ORDER = [args.browser]
    if args.profile:
        config.COOKIE_BROWSER_PATH = args.profile

    manager = CookieManager(config)

    print(f"Extracting cookies...")
    print(f"Browser order: {config.COOKIE_BROWSER_ORDER}")
    if args.profile:
        print(f"Profile path: {args.profile}")

    result = manager.get_valid_cookies()

    if result is None:
        print("\nFailed to extract cookies. Make sure:")
        print("  - Zen Browser or Brave is installed")
        print("  - You have visited youtube.com and are logged in")
        print("  - The browser is closed (some browsers lock cookie DBs)")
        sys.exit(1)

    method, value = result

    if method == 'file':
        # Copy the extracted cookie file to the output location
        import shutil
        output_path = os.path.abspath(args.output)
        if os.path.abspath(value) != output_path:
            shutil.copy2(value, output_path)
        print(f"\nCookies saved to: {output_path}")
        print(f"\nTo use with Docker:")
        print(f"  1. Keep this file at: {output_path}")
        print(f"  2. Run: docker compose up")
        print(f"  3. The cookie file is mounted into the container via docker-compose.yml")
        print(f"\nNote: Re-run this script if cookies expire (every 24h)")
    else:
        print(f"\nCookies available via browser spec: {value}")
        print("This method requires browser access and won't work in Docker.")
        print("Try closing your browser and re-running this script.")
        sys.exit(1)


if __name__ == "__main__":
    main()
