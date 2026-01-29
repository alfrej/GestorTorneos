import io
import json
import os
import re
import shutil
import subprocess
import sys
import base64
import time
import urllib.request
import zipfile
import ssl

try:
    import certifi
except Exception:
    certifi = None


REPO_OWNER = "alfrej"
REPO_NAME = "GestorTorneos"
BRANCHES = ["main", "master"]
LOCAL_APP_PYMAIN = os.path.join("app", "pymain.py")
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


def _build_ssl_context():
    if os.environ.get("GTR_DISABLE_SSL_VERIFY") == "1":
        return ssl._create_unverified_context()
    if certifi:
        return ssl.create_default_context(cafile=certifi.where())
    return ssl.create_default_context()


def _fetch_url(url):
    cache_buster = int(time.time())
    sep = "&" if "?" in url else "?"
    headers = {
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        "User-Agent": "GestorTorneosUpdater/1.0",
    }
    if "api.github.com" in url:
        headers["Accept"] = "application/vnd.github+json"
    request = urllib.request.Request(
        f"{url}{sep}t={cache_buster}",
        headers=headers,
    )
    context = _build_ssl_context()
    with urllib.request.urlopen(request, timeout=20, context=context) as resp:
        return resp.read()


def _get_remote_pymain_and_branch():
    candidates = []
    last_error = ""
    for branch in BRANCHES:
        text = ""
        api_url = (
            f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/app/pymain.py"
            f"?ref={branch}"
        )
        try:
            payload = _fetch_url(api_url).decode("utf-8", errors="replace")
            data = json.loads(payload)
            content = data.get("content", "")
            if content:
                text = base64.b64decode(content).decode("utf-8", errors="replace")
            else:
                message = data.get("message")
                if message:
                    last_error = f"GitHub API: {message}"
        except Exception:
            text = ""
            last_error = "No se pudo acceder a GitHub API."
        if not text:
            url = f"https://raw.githubusercontent.com/{REPO_OWNER}/{REPO_NAME}/{branch}/app/pymain.py"
            try:
                text = _fetch_url(url).decode("utf-8", errors="replace")
            except Exception:
                last_error = "No se pudo acceder a raw.githubusercontent.com."
                continue
        version = _extract_version(text)
        if version:
            candidates.append((version, text, branch))
    if not candidates:
        return "", "", last_error
    candidates.sort(key=lambda item: _version_tuple(item[0]) or (-1,))
    return candidates[-1][1], candidates[-1][2], ""


def _download_latest_app(branch):
    url = f"https://github.com/{REPO_OWNER}/{REPO_NAME}/archive/refs/heads/{branch}.zip"
    data = _fetch_url(url)
    zf = zipfile.ZipFile(io.BytesIO(data))

    app_prefix = ""
    for name in zf.namelist():
        if name.endswith("/app/pymain.py"):
            app_prefix = name[: -len("app/pymain.py")]
            break
    if not app_prefix:
        raise RuntimeError("No se encontro app/pymain.py en el zip del repositorio.")

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


def _ensure_latest_pymain():
    if not os.path.isfile(LOCAL_APP_PYMAIN):
        return
    dest = os.path.join(LATEST_DIR, "pymain.py")
    if os.path.isfile(dest):
        return
    try:
        os.makedirs(LATEST_DIR, exist_ok=True)
        shutil.copy2(LOCAL_APP_PYMAIN, dest)
    except OSError:
        pass


def _select_entrypoint(base_dir):
    if base_dir == LATEST_DIR:
        _ensure_latest_pymain()
    return os.path.join(base_dir, "pymain.py")


def main():
    print("Buscando nueva version...")
    latest_pymain = os.path.join(LATEST_DIR, "pymain.py")
    latest_version = _extract_version(_read_text(latest_pymain))
    remote_pymain, branch, error_detail = _get_remote_pymain_and_branch()
    remote_version = _extract_version(remote_pymain)

    if not remote_version:
        print("No se pudo leer la version remota.")
        if error_detail:
            print(f"Detalle: {error_detail}")
        return

    print(f"La version en git es {remote_version} ({branch}).")
    print(f"La version local es {latest_version or 'no disponible'}.")
    if not latest_version:
        print("No existe latest o no tiene version, descargo la nueva version.")
        _download_latest_app(branch)
        _run_main(_select_entrypoint(LATEST_DIR))
        return

    if _is_remote_newer(remote_version, latest_version):
        print(f"Descargo la nueva version {remote_version} desde {branch}...")
        _download_latest_app(branch)
        _run_main(_select_entrypoint(LATEST_DIR))
        return

    print("Ya esta actualizada.")
    _run_main(_select_entrypoint(LATEST_DIR))


if __name__ == "__main__":
    main()
