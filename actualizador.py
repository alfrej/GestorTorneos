import io
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.request
import zipfile


REPO_OWNER = "alfrej"
REPO_NAME = "GestorTorneos"
BRANCHES = ["main", "master"]
LOCAL_APP_MAIN = os.path.join("app", "main.py")
LATEST_DIR = "latest"


def _read_text(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return ""


def _extract_version(text):
    match = re.search(r'^__version__\s*=\s*["\']([^"\']+)["\']', text, re.M)
    return match.group(1).strip() if match else ""


def _version_tuple(version):
    parts = []
    for part in version.split("."):
        try:
            parts.append(int(part))
        except ValueError:
            return ()
    return tuple(parts)


def _is_remote_newer(remote, local):
    if not remote:
        return False
    if not local:
        return True
    if remote == local:
        return False
    remote_tuple = _version_tuple(remote)
    local_tuple = _version_tuple(local)
    if remote_tuple and local_tuple:
        return remote_tuple > local_tuple
    return True


def _fetch_url(url):
    cache_buster = int(time.time())
    sep = "&" if "?" in url else "?"
    request = urllib.request.Request(
        f"{url}{sep}t={cache_buster}",
        headers={"Cache-Control": "no-cache", "Pragma": "no-cache"},
    )
    with urllib.request.urlopen(request, timeout=20) as resp:
        return resp.read()


def _get_remote_main_and_branch():
    candidates = []
    for branch in BRANCHES:
        url = f"https://raw.githubusercontent.com/{REPO_OWNER}/{REPO_NAME}/{branch}/app/main.py"
        try:
            text = _fetch_url(url).decode("utf-8", errors="replace")
        except Exception:
            continue
        version = _extract_version(text)
        if version:
            candidates.append((version, text, branch))
    if not candidates:
        return "", ""
    candidates.sort(key=lambda item: _version_tuple(item[0]) or (-1,))
    return candidates[-1][1], candidates[-1][2]


def _download_latest_app(branch):
    url = f"https://github.com/{REPO_OWNER}/{REPO_NAME}/archive/refs/heads/{branch}.zip"
    data = _fetch_url(url)
    zf = zipfile.ZipFile(io.BytesIO(data))

    app_prefix = ""
    for name in zf.namelist():
        if name.endswith("/app/main.py"):
            app_prefix = name[: -len("app/main.py")]
            break
    if not app_prefix:
        raise RuntimeError("No se encontro app/main.py en el zip del repositorio.")

    if os.path.isdir(LATEST_DIR):
        for name in os.listdir(LATEST_DIR):
            if name.lower() == "torneos":
                continue
            path = os.path.join(LATEST_DIR, name)
            if os.path.isdir(path):
                shutil.rmtree(path)
            else:
                os.remove(path)
    os.makedirs(LATEST_DIR, exist_ok=True)

    for name in zf.namelist():
        if not name.startswith(app_prefix + "app/"):
            continue
        rel_path = name[len(app_prefix + "app/") :]
        if rel_path.startswith("Torneos/") or rel_path == "Torneos":
            continue
        if not rel_path:
            continue
        dest_path = os.path.join(LATEST_DIR, rel_path)
        if name.endswith("/"):
            os.makedirs(dest_path, exist_ok=True)
            continue
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        with zf.open(name) as src, open(dest_path, "wb") as dst:
            shutil.copyfileobj(src, dst)


def _run_main(path):
    subprocess.run([sys.executable, path], check=False)


def _ensure_requirements(requirements_path):
    if not os.path.isfile(requirements_path):
        return
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "-r", requirements_path],
        check=False,
    )


def main():
    print("Buscando nueva version...")
    latest_main = os.path.join(LATEST_DIR, "main.py")
    latest_version = _extract_version(_read_text(latest_main))
    remote_main, branch = _get_remote_main_and_branch()
    remote_version = _extract_version(remote_main)

    if not remote_version:
        print("No se pudo leer la version remota.")
        return

    print(f"La version en git es {remote_version} ({branch}).")
    print(f"La version local es {latest_version or 'no disponible'}.")
    if not latest_version:
        print("No existe latest o no tiene version, descargo la nueva version.")
        _download_latest_app(branch)
        _ensure_requirements(os.path.join(LATEST_DIR, "requirements.txt"))
        _run_main(os.path.join(LATEST_DIR, "main.py"))
        return

    if _is_remote_newer(remote_version, latest_version):
        print(f"Descargo la nueva version {remote_version} desde {branch}...")
        _download_latest_app(branch)
        _ensure_requirements(os.path.join(LATEST_DIR, "requirements.txt"))
        _run_main(os.path.join(LATEST_DIR, "main.py"))
        return

    print("Ya esta actualizada.")
    _ensure_requirements(os.path.join(LATEST_DIR, "requirements.txt"))
    _run_main(latest_main)


if __name__ == "__main__":
    main()
