import subprocess
import sys
from importlib import metadata

from ui_services import AnalysisService, ScanService


def configure_console_output():
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except ValueError:
                pass


def install_missing_requirements(auto_confirm=False):
    requirements_file = "requirements.txt"
    try:
        with open(requirements_file, "r") as f:
            requirements = [line.strip() for line in f if line.strip() and not line.startswith("#")]

        missing = []
        for requirement in requirements:
            package_name = requirement.split("==")[0].split(">=")[0].split("<=")[0].strip()
            try:
                metadata.version(package_name)
            except metadata.PackageNotFoundError:
                missing.append(requirement)

        if not missing:
            print("[*] All requirements are already met.")
            return True

        if not auto_confirm:
            print(f"[!] Missing packages found: {missing}.")
            print("[!] Install them yourself with:")
            print(f"    python -m pip install --user {' '.join(missing)}")
            print("[!] ...or re-run this program with --install-deps to install them automatically.")
            return False

        print(f"[*] Missing packages found: {missing}. Installing...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "--user", *missing])
            print("[*] All packages installed successfully.")
            return True
        except subprocess.CalledProcessError:
            print("[!] Pip installation failed. Try running as Administrator.")
            return False

    except FileNotFoundError:
        print("[!] requirements.txt not found. Skipping auto-install.")
        return True
    except Exception as e:
        print(f"[!] Auto-install failed: {e}")
        return True


def setup_llm(progress_callback=None):
    print("[i] Setting up LLM...")
    return AnalysisService.ensure_model(progress_callback=progress_callback)


def scan_apps():
    return ScanService.scan()


def select_app(apps):
    registry_apps = [app for app in apps if app.source_kind == "Registry"]
    exe_apps = [app for app in apps if app.source_kind == "Filesystem"]

    if not registry_apps and not exe_apps:
        print("[!] No apps available to select.")
        return None

    print("\nRegistry applications:")
    for idx, app in enumerate(registry_apps, start=1):
        print(f"  {idx}. {app.name}")
    print("\nExecutable files:")
    for idx, app in enumerate(exe_apps, start=1):
        print(f"  {idx}. {app.name}")

    try:
        category = input("Select category (r=registry, e=exe): ").strip().lower()
        if category.startswith("r") and registry_apps:
            num = int(input("Enter registry program number: ").strip())
            return registry_apps[num - 1]
        if category.startswith("e") and exe_apps:
            num = int(input("Enter exe file number: ").strip())
            return exe_apps[num - 1]
        print("[!] Invalid selection or empty list.")
    except (ValueError, IndexError):
        print("[!] Selection out of range or invalid.")
    except EOFError:
        print("[!] No input received; skipping selection.")
    return None


def analyze_app(app):
    print(f"[*] Researching web for: {app.name}")
    assessment = AnalysisService.analyze(app)
    print(f"[v] Web info collected for {app.name}.")
    return assessment


def main():
    print("[*] Starting AppsAnalyst...")

    apps = scan_apps()
    app_to_analyze = select_app(apps)

    if app_to_analyze:
        model_ready = setup_llm()
        if model_ready is not True:
            print(f"[!] LLM setup failed: {model_ready}")
            return

        assessment = analyze_app(app_to_analyze)
        print(f"[v] Risk Assessment Vector: {assessment.risk_flags}")
        print(f"[v] Risk Level: {assessment.risk_level.title()}")
        print(f"[v] Overview: {assessment.overview}")
        print(f"[v] Recommended Action: {assessment.recommended_action}")
        print("[v] LLM analysis completed.")
    else:
        print("[!] No app selected for analysis.")

    print("[v] Scan completed.")


if __name__ == "__main__":
    configure_console_output()

    args = sys.argv[1:]
    auto_install = "--install-deps" in args
    gui_mode = "--gui" in args

    install_missing_requirements(auto_confirm=auto_install)

    if gui_mode:
        from gui import run_gui
        run_gui()
    else:
        main()
