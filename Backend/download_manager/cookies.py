"""
Cookie Auto-Extraction Module

Handles automatic browser cookie extraction for YouTube downloads.
Supports Zen Browser (Firefox-based) and Brave (Chromium-based).
Uses yt-dlp's built-in --cookies-from-browser for extraction.
"""

import os
import sys
import time
import glob
import shutil
import sqlite3
import subprocess
import tempfile
from pathlib import Path
from typing import Optional, Tuple, List
from rich.console import Console

console = Console()


class CookieManager:
    """Manages browser cookie extraction and caching for YouTube downloads."""

    def __init__(self, config):
        self.config = config
        self._cookie_dir = config.BASEDIR / '.cookies'
        self._cookie_file = self._cookie_dir / 'cookies.txt'
        self._cookie_dir.mkdir(parents=True, exist_ok=True)

    def get_valid_cookies(self) -> Optional[Tuple[str, str]]:
        """
        Get valid cookies for YouTube downloads.

        Returns:
            Tuple of (method, value) where:
                method='file' and value=path to cookie file, OR
                method='browser' and value=browser spec string for yt-dlp
            Returns None if no valid cookies can be obtained.
        """
        # Check manual cookie path first
        manual_path = getattr(self.config, 'COOKIE_MANUAL_PATH', None)
        if manual_path:
            manual_path = Path(manual_path)
            if manual_path.exists() and self._is_cookie_fresh(manual_path):
                console.print(f"[green]* Using manual cookie file: {manual_path}[/green]")
                return ('file', str(manual_path))
            elif manual_path.exists():
                console.print(f"[yellow]! Manual cookie file is stale (>24h): {manual_path}[/yellow]")
            else:
                console.print(f"[yellow]! Manual cookie file not found: {manual_path}[/yellow]")

        # Check Docker-mounted cookie file (for container environments without browsers)
        docker_cookie_paths = [
            Path('/app/cookies.txt'),       # Docker mount point
            Path('cookies.txt'),            # Current directory fallback
        ]
        for docker_path in docker_cookie_paths:
            if docker_path.exists() and self._validate_cookie_file(docker_path):
                if self._is_cookie_fresh(docker_path):
                    console.print(f"[green]* Using mounted cookie file: {docker_path}[/green]")
                    return ('file', str(docker_path))
                else:
                    console.print(f"[yellow]! Mounted cookie file is stale (>24h): {docker_path}[/yellow]")
                    console.print("[yellow]  Re-run extract_cookies.py on the host to refresh.[/yellow]")

        # Check cached cookie file
        if self._cookie_file.exists() and self._is_cookie_fresh(self._cookie_file):
            if self._validate_cookie_file(self._cookie_file):
                console.print("[green]* Using cached cookies (fresh)[/green]")
                return ('file', str(self._cookie_file))
            else:
                console.print("[yellow]! Cached cookies invalid, re-extracting...[/yellow]")

        # Try auto-extraction from browsers
        return self._extract_from_browsers()

    def _extract_from_browsers(self) -> Optional[Tuple[str, str]]:
        """
        Try extracting cookies from browsers in configured order.
        Tries Zen Browser first, then Brave.

        Returns:
            Tuple of (method, value) or None.
        """
        browser_order = getattr(self.config, 'COOKIE_BROWSER_ORDER', ['zen', 'brave'])

        for browser in browser_order:
            result = self._try_browser(browser)
            if result:
                return result

        console.print("[red]X Failed to extract cookies from any browser[/red]")
        return None

    def _try_browser(self, browser: str) -> Optional[Tuple[str, str]]:
        """
        Attempt cookie extraction from a specific browser.

        Args:
            browser: 'zen' or 'brave'

        Returns:
            Tuple of (method, value) or None.
        """
        console.print(f"[blue]Trying cookie extraction from {browser.capitalize()}...[/blue]")

        browser_spec = self._get_browser_spec(browser)
        if browser_spec is None:
            console.print(f"[yellow]! {browser.capitalize()} browser not found[/yellow]")
            return None

        # Try using yt-dlp's --cookies-from-browser to extract and cache
        success = self._extract_with_ytdlp(browser_spec)
        if success and self._cookie_file.exists():
            if self._validate_cookie_file(self._cookie_file):
                console.print(f"[green]* Successfully extracted cookies from {browser.capitalize()}[/green]")
                return ('file', str(self._cookie_file))
            else:
                console.print(f"[yellow]! Cookies from {browser.capitalize()} failed validation[/yellow]")

        # Fallback: return browser spec for yt-dlp to use directly
        # This lets yt-dlp handle extraction on-the-fly per download
        if self._test_browser_spec(browser_spec):
            console.print(f"[green]* Will use {browser.capitalize()} cookies directly via yt-dlp[/green]")
            return ('browser', browser_spec)

        return None

    def _get_browser_spec(self, browser: str) -> Optional[str]:
        """
        Get yt-dlp browser spec string for the given browser.
        For Zen (Firefox-based), we need to find its profile and use firefox:profile_path.
        For Brave, yt-dlp supports it natively.

        Returns:
            yt-dlp browser spec string, e.g. 'brave', 'firefox:/path/to/zen/profile'
        """
        manual_path = getattr(self.config, 'COOKIE_BROWSER_PATH', None)

        if browser == 'zen':
            return self._get_zen_spec(manual_path)
        elif browser == 'brave':
            return self._get_brave_spec(manual_path)
        return None

    def _get_zen_spec(self, manual_path: Optional[str] = None) -> Optional[str]:
        """
        Build yt-dlp browser spec for Zen Browser.
        Zen is Firefox-based, so we use 'firefox' with the Zen profile path.
        """
        if manual_path:
            profile_path = Path(manual_path)
            if profile_path.exists():
                return f"firefox:{profile_path}"
            return None

        # Auto-detect Zen Browser profile
        profile_dir = self._find_zen_profile_dir()
        if profile_dir is None:
            return None

        # Find the default profile (look for *.default-release or first profile)
        default_profile = self._find_default_profile(profile_dir)
        if default_profile is None:
            return None

        # Verify cookies.sqlite exists
        cookies_db = default_profile / 'cookies.sqlite'
        if not cookies_db.exists():
            console.print(f"[yellow]! Zen profile found but no cookies.sqlite at {default_profile}[/yellow]")
            return None

        return f"firefox:{default_profile}"

    def _find_zen_profile_dir(self) -> Optional[Path]:
        """Find Zen Browser's profiles directory."""
        if sys.platform == 'win32':
            candidates = [
                Path(os.environ.get('APPDATA', '')) / 'zen' / 'Profiles',
                Path(os.environ.get('APPDATA', '')) / 'Zen Browser' / 'Profiles',
                Path(os.environ.get('APPDATA', '')) / '.zen' / 'Profiles',
            ]
        else:
            home = Path.home()
            candidates = [
                home / '.zen' / 'Profiles',
                home / '.zen',
                home / '.config' / 'zen' / 'Profiles',
                home / '.config' / 'zen',  # Zen on Linux direct config profile dir
            ]

        for candidate in candidates:
            if candidate.exists() and candidate.is_dir():
                return candidate

        return None

    def _find_default_profile(self, profile_dir: Path) -> Optional[Path]:
        """Find the default profile directory within a Firefox/Zen profiles dir."""
        # Parse profiles.ini to get all profiles, sorted by priority (Install default, then Default=1, then others)
        candidates = []
        for ini_dir in [profile_dir, profile_dir.parent]:
            profiles_ini = ini_dir / 'profiles.ini'
            if profiles_ini.exists():
                candidates.extend(self._parse_profiles_ini(profiles_ini))

        # Check candidate profiles from profiles.ini (first one with cookies.sqlite wins)
        for profile_path in candidates:
            if (profile_path / 'cookies.sqlite').exists():
                return profile_path

        # Fallback: glob the profile directory and look for any directory containing cookies.sqlite
        for pattern in ['*.default-release', '*.Default (release)', '*.default', '*.Default Profile', '*']:
            matches = list(profile_dir.glob(pattern))
            dirs = [m for m in matches if m.is_dir() and not m.name.startswith('.')]
            if dirs:
                # Prefer the one with cookies.sqlite
                for d in dirs:
                    if (d / 'cookies.sqlite').exists():
                        return d

        # If none contain cookies.sqlite, fallback to first candidate from profiles.ini
        if candidates:
            return candidates[0]
        return None

    def _parse_profiles_ini(self, ini_path: Path) -> List[Path]:
        """Parse profiles.ini to find all profile paths, ordered by priority."""
        install_defaults = []
        profile_defaults = []
        others = []
        
        try:
            import configparser
            parser = configparser.ConfigParser()
            parser.read(str(ini_path), encoding='utf-8')

            # First, check [Install...] sections to find default profile paths
            for section in parser.sections():
                if section.startswith('Install'):
                    default_path = parser.get(section, 'Default', fallback=None)
                    if default_path:
                        full_path = ini_path.parent / default_path
                        if full_path.exists():
                            install_defaults.append(full_path)

            # Next, parse all [Profile...] sections
            for section in parser.sections():
                if section.startswith('Profile'):
                    path = parser.get(section, 'Path', fallback=None)
                    is_relative = parser.get(section, 'IsRelative', fallback='1')
                    is_default = parser.get(section, 'Default', fallback='0')
                    
                    if path:
                        if is_relative == '1':
                            full_path = ini_path.parent / path
                        else:
                            full_path = Path(path)
                            
                        if full_path.exists():
                            if is_default == '1':
                                profile_defaults.append(full_path)
                            else:
                                others.append(full_path)
        except Exception:
            pass

        # Return combined candidates ordered by priority:
        # 1. Install section defaults (used by the current installation)
        # 2. Profiles with Default=1
        # 3. All other profiles
        seen = set()
        ordered_candidates = []
        for p in install_defaults + profile_defaults + others:
            if p not in seen:
                seen.add(p)
                ordered_candidates.append(p)
                
        return ordered_candidates

    def _get_brave_spec(self, manual_path: Optional[str] = None) -> Optional[str]:
        """
        Build yt-dlp browser spec for Brave Browser.
        yt-dlp natively supports 'brave' as a browser name.
        """
        if manual_path:
            profile_path = Path(manual_path)
            if profile_path.exists():
                return f"brave:{profile_path}"
            return None

        # Check if Brave is installed by looking for its data directory
        brave_dir = self._find_brave_data_dir()
        if brave_dir is None:
            return None

        return "brave"

    def _find_brave_data_dir(self) -> Optional[Path]:
        """Find Brave Browser's data directory."""
        if sys.platform == 'win32':
            candidates = [
                Path(os.environ.get('LOCALAPPDATA', '')) / 'BraveSoftware' / 'Brave-Browser' / 'User Data',
            ]
        else:
            home = Path.home()
            candidates = [
                home / '.config' / 'BraveSoftware' / 'Brave-Browser',
            ]

        for candidate in candidates:
            if candidate.exists() and candidate.is_dir():
                return candidate

        return None

    def _extract_with_ytdlp(self, browser_spec: str) -> bool:
        """
        Use yt-dlp to extract cookies from browser and save to file.

        Args:
            browser_spec: yt-dlp browser spec string

        Returns:
            True if extraction succeeded.
        """
        try:
            import yt_dlp

            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'cookiesfrombrowser': self._parse_browser_spec(browser_spec),
                'cookiefile': str(self._cookie_file),
                'extract_flat': True,
                'skip_download': True,
            }

            # Use a simple YouTube URL to trigger cookie extraction
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                # Just extracting info triggers cookie save
                ydl.extract_info('https://www.youtube.com', download=False)

            return self._cookie_file.exists() and self._cookie_file.stat().st_size > 0

        except Exception as e:
            console.print(f"[yellow]! Cookie extraction failed: {e}[/yellow]")
            return False

    def _parse_browser_spec(self, spec: str) -> Tuple:
        """
        Parse browser spec string into yt-dlp cookiesfrombrowser tuple.
        Format: 'browser_name:profile_path+key=value'
        yt-dlp expects: (browser_name, profile_path, keyring_name, container_name)
        """
        parts = spec.split('+')
        main_part = parts[0]
        keyring = None
        container = None

        for extra in parts[1:]:
            if extra.startswith('keyring='):
                keyring = extra.split('=', 1)[1]
            elif extra.startswith('container='):
                container = extra.split('=', 1)[1]

        if ':' in main_part:
            browser_name, profile_path = main_part.split(':', 1)
        else:
            browser_name = main_part
            profile_path = None

        return (browser_name, profile_path, keyring, container)

    def _test_browser_spec(self, browser_spec: str) -> bool:
        """
        Test if yt-dlp can use the browser spec to extract cookies.
        Quick test without downloading anything.
        """
        try:
            import yt_dlp

            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'cookiesfrombrowser': self._parse_browser_spec(browser_spec),
                'extract_flat': True,
                'skip_download': True,
                'socket_timeout': 10,
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.extract_info('https://www.youtube.com', download=False)

            return True
        except Exception:
            return False

    def _is_cookie_fresh(self, cookie_path: Path) -> bool:
        """Check if cookie file is less than 24 hours old."""
        try:
            max_age = getattr(self.config, 'COOKIE_MAX_AGE', 86400)
            file_age = time.time() - cookie_path.stat().st_mtime
            return file_age < max_age
        except Exception:
            return False

    def _validate_cookie_file(self, cookie_path: Path) -> bool:
        """
        Validate that the cookie file is in Netscape format and non-empty.
        Does a basic structural check.
        """
        try:
            if not cookie_path.exists():
                return False

            content = cookie_path.read_text(encoding='utf-8', errors='ignore')
            lines = content.strip().split('\n')

            # Filter out comments and empty lines
            data_lines = [l for l in lines if l.strip() and not l.startswith('#')]
            if not data_lines:
                return False

            # Check at least one line has tab-separated fields (Netscape format)
            for line in data_lines[:5]:
                fields = line.split('\t')
                if len(fields) >= 7:
                    return True

            return False
        except Exception:
            return False

    def get_cookie_status(self) -> dict:
        """Get current cookie status information."""
        status = {
            'has_cached_cookies': False,
            'cached_cookie_age': None,
            'cached_cookie_fresh': False,
            'manual_path': getattr(self.config, 'COOKIE_MANUAL_PATH', None),
            'browser_order': getattr(self.config, 'COOKIE_BROWSER_ORDER', ['zen', 'brave']),
            'zen_available': self._find_zen_profile_dir() is not None,
            'brave_available': self._find_brave_data_dir() is not None,
        }

        if self._cookie_file.exists():
            status['has_cached_cookies'] = True
            age_seconds = time.time() - self._cookie_file.stat().st_mtime
            status['cached_cookie_age'] = self._format_age(age_seconds)
            status['cached_cookie_fresh'] = self._is_cookie_fresh(self._cookie_file)

        return status

    def clear_cached_cookies(self):
        """Delete cached cookie file to force re-extraction."""
        try:
            if self._cookie_file.exists():
                self._cookie_file.unlink()
                console.print("[green]* Cached cookies cleared[/green]")
            else:
                console.print("[yellow]! No cached cookies to clear[/yellow]")
        except Exception as e:
            console.print(f"[red]X Failed to clear cookies: {e}[/red]")

    @staticmethod
    def _format_age(seconds: float) -> str:
        """Format age in seconds to human-readable string."""
        if seconds < 60:
            return f"{int(seconds)}s"
        elif seconds < 3600:
            return f"{int(seconds // 60)}m"
        elif seconds < 86400:
            return f"{seconds / 3600:.1f}h"
        else:
            return f"{seconds / 86400:.1f}d"
