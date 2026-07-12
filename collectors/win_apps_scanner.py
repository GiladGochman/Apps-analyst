import os
import stat
import winreg
from collections import defaultdict
from pathlib import Path

try:
    import yaml
except Exception:  # pragma: no cover - optional dependency during runtime
    yaml = None


class WinAppsScanner:
    def __init__(self, scan_depth=None):
        self.registry_paths = [
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
            (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Uninstall"),
        ]
        configured_scan_depth = self._load_scan_depth()
        requested_scan_depth = str(scan_depth or configured_scan_depth).strip().lower()
        self.scan_depth = requested_scan_depth if requested_scan_depth in {"standard", "deep"} else configured_scan_depth
        self.max_filesystem_depth = 3 if self.scan_depth == "standard" else 8
        self.file_scan_paths = self._default_file_scan_paths()
        self.skip_dir_names = {
            "$recycle.bin",
            ".git",
            ".hg",
            ".idea",
            ".venv",
            "__pycache__",
            "node_modules",
            "temp",
            "tmp",
        }
        self.skip_dir_prefixes = ("windows kits", "microsoft sdk", "reference assemblies")

    def _load_scan_depth(self):
        if yaml is None:
            return "standard"

        config_path = Path(__file__).resolve().parents[1] / "config.yaml"
        try:
            with config_path.open("r", encoding="utf-8") as handle:
                config = yaml.safe_load(handle) or {}
        except OSError:
            return "standard"

        scan_depth = str(config.get("app_settings", {}).get("scan_depth", "standard")).strip().lower()
        return scan_depth if scan_depth in {"standard", "deep"} else "standard"

    def _default_file_scan_paths(self):
        candidates = [
            Path.home() / "Desktop",
            Path.home() / "Downloads",
            Path.home() / "Documents",
        ]

        local_app_data = os.environ.get("LOCALAPPDATA")
        if local_app_data:
            candidates.append(Path(local_app_data) / "Programs")
            if self.scan_depth == "deep":
                candidates.append(Path(local_app_data))

        if self.scan_depth == "deep":
            app_data = os.environ.get("APPDATA")
            if app_data:
                candidates.append(Path(app_data))
                candidates.append(Path(app_data) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup")

            program_data = os.environ.get("PROGRAMDATA")
            if program_data:
                candidates.append(Path(program_data) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup")

            for env_name in ("ProgramFiles", "ProgramFiles(x86)"):
                value = os.environ.get(env_name)
                if value:
                    candidates.append(Path(value))

        paths = []
        seen = set()
        for candidate in candidates:
            normalized = str(candidate).lower()
            if normalized in seen or not candidate.exists() or not candidate.is_dir():
                continue
            seen.add(normalized)
            paths.append(str(candidate))
        return paths

    def _is_reparse_point(self, path):
        try:
            attributes = os.lstat(path).st_file_attributes
        except (AttributeError, FileNotFoundError, OSError):
            return os.path.islink(path)
        return bool(attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT)

    def _prune_dirs(self, scan_root, current_root, dirs):
        base_depth = len(Path(scan_root).parts)
        allowed = []
        for name in dirs:
            full_path = os.path.join(current_root, name)
            current_depth = len(Path(full_path).parts) - base_depth
            if current_depth > self.max_filesystem_depth:
                continue
            if name.lower() in self.skip_dir_names:
                continue
            if any(name.lower().startswith(prefix) for prefix in self.skip_dir_prefixes):
                continue
            if self._is_reparse_point(full_path):
                continue
            allowed.append(name)
        dirs[:] = allowed

    def _iter_executables(self, path, progress_callback=None):
        if progress_callback:
            progress_callback(f"Scanning {path} for portable executables...")

        def handle_walk_error(error):
            print(f"[!] Failed to scan path {error.filename}: {error}")

        visited_dirs = 0
        for root, dirs, files in os.walk(path, topdown=True, onerror=handle_walk_error):
            visited_dirs += 1
            if progress_callback and visited_dirs % 150 == 0:
                progress_callback(f"Scanning {path}... {visited_dirs} directories visited")
            self._prune_dirs(path, root, dirs)
            for file in files:
                if file.lower().endswith(".exe"):
                    yield os.path.join(root, file)

    def get_base_name(self, name):
        parts = name.split()
        if len(parts) >= 2 and any(c.isdigit() for c in parts[1]):
            return " ".join(parts[:2])
        return parts[0]

    def _get_registry_value(self, key, value_name):
        try:
            value, _ = winreg.QueryValueEx(key, value_name)
            return value
        except FileNotFoundError:
            return None

    def scan(self, progress_callback=None, include_registry=True, include_filesystem=True):
        registry_apps = []
        exe_apps = []
        seen_apps = set()

        if include_registry:
            if progress_callback:
                progress_callback("Scanning installed programs from the Windows registry...")
            print("[*] Starting Windows apps scan (registry)...")

            for hive, sub_key_path in self.registry_paths:
                try:
                    with winreg.OpenKey(hive, sub_key_path) as parent_key:
                        num_subkeys = winreg.QueryInfoKey(parent_key)[0]

                        for i in range(num_subkeys):
                            try:
                                subkey_name = winreg.EnumKey(parent_key, i)
                                with winreg.OpenKey(parent_key, subkey_name) as app_key:
                                    display_name = self._get_registry_value(app_key, "DisplayName")
                                    if not display_name:
                                        continue

                                    app_info = {
                                        "name": display_name,
                                        "version": self._get_registry_value(app_key, "DisplayVersion") or "Unknown",
                                        "publisher": self._get_registry_value(app_key, "Publisher") or "Unknown",
                                        "install_date": self._get_registry_value(app_key, "InstallDate") or "Unknown",
                                        "uninstall_string": self._get_registry_value(app_key, "UninstallString"),
                                        "install_location": self._get_registry_value(app_key, "InstallLocation") or "Unknown",
                                        "source_registry": sub_key_path,
                                    }

                                    app_id = f"{app_info['name']}_{app_info['version']}"
                                    if app_id not in seen_apps:
                                        registry_apps.append(app_info)
                                        seen_apps.add(app_id)
                            except OSError:
                                continue
                except OSError as exc:
                    print(f"[!] Failed to access registry path {sub_key_path}: {exc}")

        if include_filesystem:
            if progress_callback:
                scope = "common user folders" if self.scan_depth == "standard" else "extended application folders"
                progress_callback(f"Scanning {scope} for portable executables...")
            print("[*] Starting filesystem scan for exe files...")
            total_paths = len(self.file_scan_paths)
            for index, path in enumerate(self.file_scan_paths, start=1):
                if progress_callback:
                    progress_callback(
                        f"Scanning filesystem location {index}/{total_paths}: {path}"
                    )
                try:
                    for full_path in self._iter_executables(path, progress_callback=progress_callback):
                        app_info = {
                            "name": os.path.splitext(os.path.basename(full_path))[0],
                            "version": "Unknown",
                            "publisher": "Unknown",
                            "install_date": "Unknown",
                            "uninstall_string": None,
                            "install_location": full_path,
                            "source_registry": f"Filesystem: {full_path}",
                        }
                        app_id = f"filesystem:{full_path.lower()}"
                        if app_id not in seen_apps:
                            exe_apps.append(app_info)
                            seen_apps.add(app_id)
                except OSError as exc:
                    print(f"[!] Failed to scan path {path}: {exc}")

        print(f"[v] Scan complete. Found {len(registry_apps)} registry apps and {len(exe_apps)} exe files.")
        return registry_apps, exe_apps


if __name__ == "__main__":
    scanner = WinAppsScanner()
    registry, exe = scanner.scan()

    print(f"\n--- Registry Apps ({len(registry)}) ---")
    for idx, app in enumerate(registry, start=1):
        print(f"{idx}. {app['name']}")
    print(f"\n--- EXE Files ({len(exe)}) ---")
    for idx, app in enumerate(exe, start=1):
        print(f"{idx}. {app['name']}")

    grouped = defaultdict(list)
    for app in registry:
        base = scanner.get_base_name(app["name"])
        grouped[base].append(app)

    output_dir = os.path.join(os.path.dirname(__file__), "..", "output")
    os.makedirs(output_dir, exist_ok=True)
    output_file = os.path.join(output_dir, "installed_apps.txt")
    with open(output_file, "w", encoding="utf-8") as handle:
        handle.write(f"Found {len(grouped)} Application Groups\n\n")
        for base in sorted(grouped.keys()):
            handle.write(f"[*] {base}\n")

    print(f"\nGrouped list saved to {output_file}")
