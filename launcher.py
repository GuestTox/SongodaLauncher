import hashlib
import json
import os
import subprocess
import uuid
import requests
import minecraft_launcher_lib
from supabase import create_client, Client

HEADERS = {
    "User-Agent": "SongodaLauncher/1.0.0 (contact@songodamc.com)"
}

GITHUB_MANIFEST_URL = "https://raw.githubusercontent.com/GuestTox/SongodaLauncher/refs/heads/main/manifest.json"

SUPABASE_URL = "https://wwfmfeowjvfsrbskzhun.supabase.co"
SUPABASE_KEY = "sb_publishable_81G19U5ujt1ONIQqrUxWEA_z3-5O4mN"

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY) if SUPABASE_URL and SUPABASE_KEY else None

DEFAULT_CONFIG = {
    "mc_version": "1.21.1",
    "neoforge_version": "21.1.249"
}


# --- HELPER UTILITIES & USER TOKEN SYNC ---

def calculate_file_hash(file_path: str, algorithm: str = "sha256") -> str:
    algo = algorithm.lower().strip()
    hasher = hashlib.sha512() if algo in ["sha512", "sha-512"] else hashlib.sha256()
    try:
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                hasher.update(chunk)
        return hasher.hexdigest().lower()
    except Exception as e:
        print(f"[Launcher] Error hashing file {file_path}: {e}")
        return ""


def update_user_launch_token(game_dir: str, username: str) -> str:
    """Generates a secure token, saves it locally, and updates the token column in Supabase via RPC."""
    token = str(uuid.uuid4())
    token_path = os.path.join(game_dir, "launcher_token.txt")
    
    # Save token locally for KubeJS client to read upon connecting
    try:
        with open(token_path, "w", encoding="utf-8") as f:
            f.write(token)
    except Exception as e:
        print(f"[Launcher Error] Failed to save local session token: {e}")

    # Update the 'token' column securely using Supabase RPC
    if supabase and username:
        try:
            supabase.rpc(
                "update_user_token", 
                {
                    "p_username": username, 
                    "p_new_token": token
                }
            ).execute()
            print(f"[Supabase] Successfully updated launch token via RPC for {username}")
        except Exception as e:
            print(f"[Supabase Error] Failed to update user token via RPC: {e}")
            
    return token


def extract_neoforge_version(loader_str: str) -> str:
    if not loader_str:
        return DEFAULT_CONFIG["neoforge_version"]
    parts = loader_str.split("-")
    candidate = parts[-1].strip()
    if any(char.isdigit() for char in candidate):
        return candidate
    return DEFAULT_CONFIG["neoforge_version"]


def fetch_github_manifest() -> dict:
    print(f"[GitHub] Fetching mod manifest from {GITHUB_MANIFEST_URL}...")
    try:
        response = requests.get(GITHUB_MANIFEST_URL, headers=HEADERS, timeout=10)
        if response.status_code == 200:
            return response.json()
        print(f"[GitHub Error] Failed to fetch manifest. HTTP Status: {response.status_code}")
    except Exception as e:
        print(f"[GitHub Error] Error loading manifest: {e}")
    return {}


def find_installed_neoforge_version(game_dir: str, neoforge_version: str) -> str | None:
    game_dir = os.path.abspath(game_dir)
    versions_dir = os.path.join(game_dir, "versions")
    
    if not os.path.exists(versions_dir):
        return None

    installed_versions = [v["id"] for v in minecraft_launcher_lib.utils.get_installed_versions(game_dir)]
    
    candidates = [
        f"neoforge-{neoforge_version}",
        f"NeoForge-{neoforge_version}",
        neoforge_version
    ]
    
    for candidate in candidates:
        json_path = os.path.join(versions_dir, candidate, f"{candidate}.json")
        if candidate in installed_versions or os.path.exists(json_path):
            return candidate
            
    return None


# --- DOWNLOAD & SYNC WITH PROGRESS CALLBACKS ---

def download_file_with_progress(url: str, output_path: str, status_cb=None, progress_cb=None) -> bool:
    temp_path = f"{output_path}.tmp"
    try:
        response = requests.get(url, headers=HEADERS, stream=True, timeout=30)
        if response.status_code == 200:
            total_length = response.headers.get('content-length')
            downloaded = 0
            
            with open(temp_path, "wb") as f:
                if total_length is None:
                    f.write(response.content)
                else:
                    total_length = int(total_length)
                    for chunk in response.iter_content(chunk_size=8192):
                        downloaded += len(chunk)
                        f.write(chunk)
                        if progress_cb:
                            percent = int((downloaded / total_length) * 100)
                            progress_cb(percent)

            if os.path.exists(output_path):
                os.remove(output_path)
            os.rename(temp_path, output_path)
            return True
        print(f"[Download Error] HTTP {response.status_code}")
    except Exception as e:
        print(f"[Download Error] {e}")
        if os.path.exists(temp_path):
            os.remove(temp_path)
    return False


def download_neoforge_installer(neoforge_version: str, installer_path: str, status_cb=None, progress_cb=None) -> bool:
    urls = [
        f"https://maven.neoforged.net/releases/net/neoforged/neoforge/{neoforge_version}/neoforge-{neoforge_version}-installer.jar",
        f"https://maven.neoforged.net/releases/net/neoforged/neoforge/{neoforge_version}/neoforge-{neoforge_version}.jar"
    ]

    for url in urls:
        if status_cb:
            status_cb(f"Downloading NeoForge installer ({neoforge_version})...")
        if download_file_with_progress(url, installer_path, status_cb, progress_cb):
            with open(installer_path, "rb") as f:
                if f.read(4) == b"PK\x03\x04":
                    return True
            print(f"[Launcher Warning] Corrupt installer received from {url}")
            os.remove(installer_path)

    return False


def setup_game_environment(game_dir: str, status_cb=None, progress_cb=None) -> tuple[str, dict]:
    game_dir = os.path.abspath(game_dir)
    manifest = fetch_github_manifest()
    
    mc_version = manifest.get("mc_version", DEFAULT_CONFIG["mc_version"])
    raw_loader = manifest.get("modloader", "")
    neoforge_version = extract_neoforge_version(raw_loader)
    
    target_version = f"neoforge-{neoforge_version}"

    state_file = os.path.join(game_dir, "installed_state.json")
    installed_state = {}
    if os.path.exists(state_file):
        try:
            with open(state_file, "r") as f:
                installed_state = json.load(f)
        except Exception:
            installed_state = {}

    installed_versions = [v["id"] for v in minecraft_launcher_lib.utils.get_installed_versions(game_dir)]
    
    if mc_version not in installed_versions:
        if status_cb:
            status_cb(f"Downloading Minecraft {mc_version} base files...")
        
        callback = {
            "setStatus": lambda s: status_cb(s) if status_cb else None,
            "setProgress": lambda p: progress_cb(p) if progress_cb else None,
            "setMax": lambda m: None
        }
        try:
            minecraft_launcher_lib.install.install_minecraft_version(mc_version, game_dir, callback=callback)
        except Exception as e:
            print(f"[Launcher Warning] Asset download issue: {e}")

    found_installed = find_installed_neoforge_version(game_dir, neoforge_version)
    needs_installer = found_installed is None

    if needs_installer:
        installer_path = os.path.join(game_dir, "neoforge-installer.jar")
        
        success = download_neoforge_installer(neoforge_version, installer_path, status_cb, progress_cb)
        if not success:
            raise RuntimeError(f"Failed to fetch valid NeoForge installer for {neoforge_version}")

        if status_cb:
            status_cb("Installing NeoForge... (This may take a minute)")
        if progress_cb:
            progress_cb(50)

        # Create a dummy launcher_profiles.json so NeoForge installer recognizes the directory
        launcher_profiles_path = os.path.join(game_dir, "launcher_profiles.json")
        if not os.path.exists(launcher_profiles_path):
            try:
                with open(launcher_profiles_path, "w", encoding="utf-8") as pf:
                    json.dump({"profiles": {}}, pf)
            except Exception as e:
                print(f"[Launcher Warning] Failed to create launcher profiles: {e}")

        subprocess.run(["java", "-jar", installer_path, "--installClient", game_dir], check=True)

        if os.path.exists(installer_path):
            os.remove(installer_path)

        found_installed = find_installed_neoforge_version(game_dir, neoforge_version)
        if not found_installed:
            found_installed = target_version

        installed_state["installed_neoforge"] = neoforge_version
        installed_state["mc_version"] = mc_version
        installed_state["version_id"] = found_installed
        with open(state_file, "w") as f:
            json.dump(installed_state, f, indent=2)
    else:
        target_version = found_installed

    return target_version, manifest


import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

def sync_and_verify_environment(game_dir: str, status_cb=None, progress_cb=None) -> str:
    game_dir = os.path.abspath(game_dir)
    mods_dir = os.path.join(game_dir, "mods")
    os.makedirs(mods_dir, exist_ok=True)
    
    target_version, manifest = setup_game_environment(game_dir, status_cb, progress_cb)
    manifest_mods = manifest.get("mods", [])

    allowed_filenames = set()
    total_mods = len(manifest_mods)

    if status_cb:
        status_cb(f"Checking {total_mods} mod files...")

    mods_to_download = []
    for mod in manifest_mods:
        filename = mod.get("filename")
        download_url = mod.get("download_url")
        hash_info = mod.get("hash", {})
        expected_algo = hash_info.get("algorithm", "sha256")
        expected_hash = hash_info.get("value", "").lower()

        if not filename or not download_url:
            continue

        allowed_filenames.add(filename)
        filepath = os.path.join(mods_dir, filename)

        needs_download = False
        if not os.path.exists(filepath):
            needs_download = True
        else:
            local_hash = calculate_file_hash(filepath, expected_algo)
            if expected_hash and local_hash != expected_hash:
                needs_download = True

        if needs_download:
            mods_to_download.append((filename, download_url, filepath))

    completed_count = 0
    progress_lock = threading.Lock()
    total_downloads = len(mods_to_download)

    def process_mod_download(mod_info):
        nonlocal completed_count
        filename, download_url, filepath = mod_info
        
        download_file_with_progress(download_url, filepath)

        with progress_lock:
            completed_count += 1
            if status_cb:
                status_cb(f"Downloaded ({completed_count}/{total_downloads}): {filename}")
            if progress_cb and total_downloads > 0:
                progress_cb(int((completed_count / total_downloads) * 100))

    if mods_to_download:
        max_workers = min(5, len(mods_to_download))
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(process_mod_download, mod) for mod in mods_to_download]
            for future in as_completed(futures):
                future.result()
    else:
        if status_cb:
            status_cb("All mods are up to date!")
        if progress_cb:
            progress_cb(100)

    if status_cb:
        status_cb("Cleaning up old mods...")
        
    for item in os.listdir(mods_dir):
        file_path = os.path.join(mods_dir, item)
        if os.path.isfile(file_path) and item.endswith(".jar"):
            if item not in allowed_filenames:
                print(f"[Purge] Deleting removed mod: {item}")
                try:
                    os.remove(file_path)
                except OSError as e:
                    print(f"[Purge Error] {e}")

    return target_version


# --- LAUNCH ENTRYPOINT ---

def launch_game(game_dir, username, ram_gb=4, server_ip="play.songodamc.com", port="25565", status_cb=None, progress_cb=None):
    game_dir = os.path.abspath(game_dir)
    
    if status_cb:
        status_cb("Initializing launch sequence...")
    if progress_cb:
        progress_cb(0)

    target_version = sync_and_verify_environment(game_dir, status_cb, progress_cb)

    # 1. Update the dynamic token on every single launch
    if status_cb:
        status_cb("Updating dynamic session token...")
    new_token = update_user_launch_token(game_dir, username)

    # 2. Generate a permanent, consistent offline UUID based on the username 
    # (This ensures their Minecraft save data, inventories, and stats remain tied permanently to their username)
    import uuid
    persistent_uuid = str(uuid.uuid3(uuid.NAMESPACE_DNS, f"songodamc:{username}"))

    if status_cb:
        status_cb("Preparing launch arguments...")
    if progress_cb:
        progress_cb(95)

    mods_dir = os.path.join(game_dir, "mods")

    options = {
        "username": username if username else "Player",
        "uuid": persistent_uuid,  # Permanent and unchangeable per user for saves
        "token": new_token,       # Dynamic session token changing every launch
        "gameDirectory": game_dir,
        "customArgs": [
            "--modsDir", mods_dir,
            "--server", server_ip,
            "--port", str(port),
            "--auth-token", new_token # Passed safely as a custom command-line argument for KubeJS to read
        ],
        "jvmArgs": [
            f"-Xmx{int(ram_gb)}G",
            "-Xms2G",
            "-Djava.security.manager=allow",
        ],
    }

    try:
        launch_command = minecraft_launcher_lib.command.get_minecraft_command(
            target_version, game_dir, options
        )
        if status_cb:
            status_cb("Starting Minecraft process...")
        if progress_cb:
            progress_cb(100)

        process = subprocess.Popen(launch_command, cwd=game_dir)
        return process
    except Exception as e:
        if status_cb:
            status_cb(f"Launch failed: {e}")
        print(f"[Launcher Error] Failed to start game: {e}")
        return None