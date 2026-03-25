#!/usr/bin/env python3
"""
SME Local AI Orchestration — Installer
Checks prerequisites, writes .env, sets up Python environment, starts server.
"""
import subprocess
import sys
import os
import webbrowser
import time
from pathlib import Path

try:
    import httpx
except ImportError:
    httpx = None  # Not yet installed — we'll check uv first


def print_step(n: int, text: str):
    print(f"\n[{n}] {text}")


def print_ok(text: str):
    print(f"    ✓ {text}")


def print_fail(text: str):
    print(f"    ✗ {text}")


def fail(message: str):
    print(f"\n❌  {message}")
    sys.exit(1)


def check_uv():
    print_step(1, "Checking uv is installed...")
    result = subprocess.run(["uv", "--version"], capture_output=True)
    if result.returncode != 0:
        print_fail("uv not found.")
        print("""
    Install uv with:
        curl -LsSf https://astral.sh/uv/install.sh | sh
    Then re-run this installer.
""")
        sys.exit(1)
    print_ok(f"uv found: {result.stdout.decode().strip()}")


def check_lm_studio():
    print_step(2, "Checking LM Studio is running...")
    try:
        import urllib.request
        urllib.request.urlopen("http://127.0.0.1:1234/v1/models", timeout=5)
        print_ok("LM Studio is running at http://127.0.0.1:1234")
    except Exception:
        print_fail("LM Studio not reachable at http://127.0.0.1:1234")
        print("""
    Please:
    1. Open LM Studio
    2. Load the 'qwen/qwen3.5-9b' model
    3. Start the local server (Server tab → Start Server)
    Then re-run this installer.
""")
        sys.exit(1)


def prompt_erpnext_url() -> str:
    print_step(3, "ERPNext URL")
    url = input("    Enter your ERPNext URL [http://localhost:8000]: ").strip()
    return url or "http://localhost:8000"


def check_erpnext(url: str):
    print_step(4, f"Checking ERPNext is reachable at {url}...")
    try:
        import urllib.request
        urllib.request.urlopen(f"{url}/api/method/ping", timeout=5)
        print_ok("ERPNext is running.")
    except Exception:
        print_fail(f"ERPNext not reachable at {url}")
        print(f"""
    Please make sure ERPNext is running and accessible at {url}.
    If you installed via bench: run 'bench start' in your frappe-bench directory.
    If you used Docker: make sure the containers are running.
    Then re-run this installer.
""")
        sys.exit(1)


def prompt_credentials() -> tuple[str, str]:
    print_step(5, "ERPNext API credentials")
    print("""
    To find your API key and secret in ERPNext:
    1. Log into ERPNext
    2. Go to Settings → My Profile (top right)
    3. Scroll to 'API Access'
    4. Click 'Generate Keys' if none exist
""")
    api_key = input("    Paste your API Key: ").strip()
    api_secret = input("    Paste your API Secret: ").strip()
    if not api_key or not api_secret:
        fail("API key and secret are required.")
    return api_key, api_secret


def write_env(erpnext_url: str, api_key: str, api_secret: str):
    print_step(6, "Writing .env configuration...")
    env_content = f"""ERPNEXT_URL={erpnext_url}
ERPNEXT_API_KEY={api_key}
ERPNEXT_API_SECRET={api_secret}
LM_STUDIO_URL=http://127.0.0.1:1234
LM_STUDIO_MODEL=qwen/qwen3.5-9b
FASTAPI_PORT=8080
"""
    Path(".env").write_text(env_content)
    # Ensure .gitignore includes .env
    gitignore = Path(".gitignore")
    if gitignore.exists() and ".env" not in gitignore.read_text():
        with gitignore.open("a") as f:
            f.write("\n.env\n")
    print_ok(".env written.")


def setup_venv():
    print_step(7, "Setting up Python environment with uv...")
    subprocess.run(["uv", "venv", "--clear"], check=True)
    subprocess.run(["uv", "sync"], check=True)
    print_ok("Python environment ready.")


def start_server():
    print_step(8, "Starting the app server...")
    server_process = subprocess.Popen(
        ["uv", "run", "python", "main.py"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    time.sleep(2)
    if server_process.poll() is not None:
        fail("Server failed to start. Check that port 8080 is not in use.")
    print_ok("Server running at http://localhost:8080")
    return server_process


def main():
    print("\n=== SME Business Assistant — Setup ===\n")
    print("Platform:", sys.platform)
    if sys.platform.startswith("win"):
        fail("Windows is not supported in Phase 1. Please use Linux or macOS.")

    check_uv()
    check_lm_studio()
    erpnext_url = prompt_erpnext_url()
    check_erpnext(erpnext_url)
    api_key, api_secret = prompt_credentials()
    write_env(erpnext_url, api_key, api_secret)
    setup_venv()
    start_server()

    print("\n✅  Setup complete!\n")
    print("   Opening http://localhost:8080 in your browser...\n")
    webbrowser.open("http://localhost:8080")
    print("   The app will keep running in the background.")
    print("   To stop it, close this terminal.\n")

    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        print("\nStopping server...")


if __name__ == "__main__":
    main()
