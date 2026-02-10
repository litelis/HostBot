import requests
import zipfile
import io
import os
import shutil
from urllib.parse import urlparse

REPO_URL = "https://github.com/litelis/HostBot"
BRANCH = "master"
VERSION_FILE = "version.txt"
LOCAL_PATH = os.getcwd()

def parse_repo(url):
    path = urlparse(url).path.strip("/").split("/")
    return path[0], path[1]

def get_github_version(user, repo):
    url = f"https://raw.githubusercontent.com/{user}/{repo}/{BRANCH}/{VERSION_FILE}"
    r = requests.get(url, timeout=10)
    r.raise_for_status()
    return r.text.strip()

def get_local_version():
    if not os.path.exists(VERSION_FILE):
        return "0.0.0"
    with open(VERSION_FILE, "r") as f:
        return f.read().strip()

def version_tuple(v):
    return tuple(map(int, v.split(".")))

def update_repo(user, repo):
    zip_url = f"https://github.com/{user}/{repo}/archive/refs/heads/{BRANCH}.zip"
    r = requests.get(zip_url, timeout=20)
    r.raise_for_status()

    with zipfile.ZipFile(io.BytesIO(r.content)) as z:
        z.extractall("temp_update")

    extracted = os.path.join("temp_update", f"{repo}-{BRANCH}")

    for item in os.listdir(extracted):
        src = os.path.join(extracted, item)
        dst = os.path.join(LOCAL_PATH, item)

        if os.path.isdir(src):
            shutil.copytree(src, dst, dirs_exist_ok=True)
        else:
            shutil.copy2(src, dst)

    shutil.rmtree("temp_update")

def main():
    user, repo = parse_repo(REPO_URL)

    local_v = get_local_version()
    github_v = get_github_version(user, repo)

    print(f"Versión local:  {local_v}")
    print(f"Versión GitHub: {github_v}")

    if version_tuple(local_v) < version_tuple(github_v):
        choice = input("Hay una versión nueva. ¿Actualizar? (y/n): ").lower()
        if choice == "y":
            update_repo(user, repo)
            print("Actualizado.")
        else:
            print("No se actualizó.")
    else:
        print("Ya está actualizado.")

if __name__ == "__main__":
    main()

