"""Security and authorization manager for filesystem operations in Vault AI."""

from pathlib import Path
from typing import List, Optional, Set
import os
import sys


class SecurityManager:
    """Manages authorized filesystem roots and validates paths to protect the system."""

    def __init__(self, custom_roots: Optional[List[str]] = None):
        self._authorized_roots: Set[Path] = set()
        self._discover_default_roots()
        if custom_roots:
            for root in custom_roots:
                self.add_authorized_root(root)

    @staticmethod
    def _get_windows_known_folders() -> dict:
        """Read actual Windows shell folder paths from registry (handles OneDrive, D: drive redirects)."""
        folders = {}
        if sys.platform != "win32":
            return folders
        try:
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders"
            )
            mapping = {
                "{374DE290-123F-4565-9164-39C4925E467B}": "Downloads",
                "Desktop": "Desktop",
                "Personal": "Documents",
                "My Pictures": "Pictures",
            }
            for reg_name, folder_name in mapping.items():
                try:
                    val, _ = winreg.QueryValueEx(key, reg_name)
                    # Expand environment variables like %USERPROFILE%
                    val = os.path.expandvars(val)
                    folders[folder_name] = Path(val)
                except FileNotFoundError:
                    pass
            winreg.CloseKey(key)
        except Exception:
            pass
        return folders

    def _discover_default_roots(self) -> None:
        """Discover standard Windows user directories using registry for correct paths."""
        home = Path.home()

        # Try to get real paths from Windows registry first
        known = self._get_windows_known_folders()

        candidates = []

        # Use registry paths if available, else fall back to home-relative paths
        for name in ["Downloads", "Desktop", "Documents", "Pictures"]:
            if name in known:
                candidates.append(known[name])
            else:
                candidates.append(home / name)

        # Also check OneDrive redirected folders
        onedrive = os.environ.get("OneDrive") or os.environ.get("OneDriveConsumer")
        if onedrive:
            od_path = Path(onedrive)
            for name in ["Desktop", "Documents", "Pictures", "Downloads"]:
                candidates.append(od_path / name)

        for path in candidates:
            if path and path.exists() and path.is_dir():
                self._authorized_roots.add(path.resolve())

    def get_authorized_roots(self) -> List[Path]:
        """Return a sorted list of current authorized root directories."""
        return sorted(list(self._authorized_roots))

    def add_authorized_root(self, folder_path: str) -> bool:
        """Add a user-selected folder to authorized roots."""
        path = Path(folder_path).resolve()
        if path.exists() and path.is_dir():
            self._authorized_roots.add(path)
            return True
        return False

    def remove_authorized_root(self, folder_path: str) -> None:
        path = Path(folder_path).resolve()
        self._authorized_roots.discard(path)

    def is_path_authorized(self, target_path: str) -> bool:
        """Verify whether a path is strictly located inside one of the authorized roots.

        Prevents path traversal, unauthorized root escaping, and symlink breakout.
        """
        try:
            resolved = Path(target_path).resolve()
            for root in self._authorized_roots:
                try:
                    resolved.relative_to(root)
                    return True
                except ValueError:
                    continue
            return False
        except Exception:
            return False

    def sanitize_and_validate(self, target_path: str) -> Optional[Path]:
        """Sanitize path string and validate authorization.

        Returns:
            Resolved Path object if valid and authorized, None otherwise.
        """
        if not target_path or ".." in target_path:
            return None

        try:
            path = Path(target_path).resolve()
            if self.is_path_authorized(str(path)):
                return path
        except Exception:
            return None
        return None
