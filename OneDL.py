#!/usr/bin/env python3

"""
OneDL - Universal Debrid & Downloader Tool
https://github.com/ellite/OneDL
By ellite

OneDL is a command-line tool to simplify downloading from hosters, torrents, cloud debrid services, direct HTTP(S) links, and container files (.torrent & .nzb).
It supports Real-Debrid, AllDebrid, Premiumize.me, Torbox and Debrid-Link, allowing you to resolve direct links from magnets,
hoster URLs, MEGA folders, standard HTTP(S) links, or by uploading .torrent and .nzb files, and download them.

USAGE:
    1. Run the script from the folder where you want your downloaded files: onedl
    2. Choose to load URLs from a file, paste them manually, or use a debrid service.
    3. For debrid services, select Real-Debrid, AllDebrid, Premiumize.me, Torbox, Debrid-Link or let OneDL find the best option.
    4. Paste your magnet, hoster, MEGA, HTTP(S) URL, or upload a .torrent/.nzb file when prompted.
    5. Select files if needed, and OneDL will resolve and download them for you.

FEATURES:
    - Supports magnet links, hoster URLs, MEGA folders, direct HTTP(S) links, and container files (.torrent & .nzb).
    - Integrates with Real-Debrid, AllDebrid, Premiumize.me, Torbox and Debrid-Link.
    - Shows download progress bars with speed and seeders.
    - Lets you pick files from torrents, NZBs, or containers.
    - Colorful, user-friendly terminal output.

Configure your API tokens by editing ~/.onedl.conf (check https://raw.githubusercontent.com/ellite/OneDL/refs/heads/main/.onedl.conf).
More info: https://github.com/ellite/OneDL/blob/main/README.md
"""

import os
import sys
import hashlib
import urllib.parse
import time
import requests
import json
import re
import bencodepy

VERSION = "1.8.0"

CYAN = "\033[96m"
YELLOW = "\033[93m"
GREEN = "\033[92m"
RED = "\033[91m"
RESET = "\033[0m"

LOADED_PATH = None

# --- CONFIGURATION LOADER ---
def load_config():
    # Define search paths in order of priority
    search_paths = [
        # 1. Same directory as the script (Portable / Windows friendly)
        os.path.join(os.path.dirname(os.path.abspath(__file__)), ".onedl.conf"),
        # 2. User Home Directory (Linux/macOS standard)
        os.path.join(os.path.expanduser("~"), ".onedl.conf")
    ]

    config = {}
    loaded_path = None

    for path in search_paths:
        if os.path.exists(path):
            try:
                with open(path, 'r') as f:
                    config = json.load(f)
                loaded_path = path
                break # Stop searching if found
            except Exception as e:
                print(f"{RED}Warning: Found config at {path} but failed to load: {e}{RESET}")

    return config, loaded_path

user_config, LOADED_PATH = load_config()

# Load keys from config, default to empty string if missing
REAL_DEBRID_API_TOKEN = user_config.get("REAL_DEBRID_API_TOKEN", "")
ALLDEBRID_API_TOKEN = user_config.get("ALLDEBRID_API_TOKEN", "")
PREMIUMIZE_API_TOKEN = user_config.get("PREMIUMIZE_API_TOKEN", "")
TORBOX_API_TOKEN = user_config.get("TORBOX_API_TOKEN", "")
DEBRID_LINK_API_TOKEN = user_config.get("DEBRID_LINK_API_TOKEN", "")

# --- STATUS DASHBOARD ---
def print_status_box():
    # Define services map
    services = [
        ("Real-Debrid", REAL_DEBRID_API_TOKEN),
        ("AllDebrid", ALLDEBRID_API_TOKEN),
        ("Premiumize", PREMIUMIZE_API_TOKEN),
        ("Torbox", TORBOX_API_TOKEN),
        ("Debrid-Link", DEBRID_LINK_API_TOKEN)
    ]

    # Calculate box width
    path_str = LOADED_PATH if LOADED_PATH else "None (Using defaults)"
    box_width = max(50, len(path_str) + 14)
    
    # Helper to print lines
    def print_line(content, color=CYAN):
        print(f"{color}║{RESET} {content} {color}║{RESET}")
    
    def print_border(start, mid, end, color=CYAN):
        print(f"{color}{start}{mid * (box_width - 2)}{end}{RESET}")

    # --- DRAW BOX ---
    print_border("╔", "═", "╗")
    
    # Title (Centered)
    title = f"OneDL v{VERSION}"
    padding = (box_width - 4 - len(title)) // 2
    # Adjust right padding if odd length
    r_padding = box_width - 4 - len(title) - padding
    print_line(" " * padding + f"{YELLOW}{title}{RESET}" + " " * r_padding)
    
    print_border("╠", "═", "╣")
    
    # Config Path (Left Aligned)
    label = "Config:"
    spaces = box_width - 4 - len(label) - 1 - len(path_str)
    print_line(f"{label} {GREEN}{path_str}{RESET}" + " " * spaces)
    
    print_border("╟", "─", "╢")
    
    # Service Status
    for name, token in services:
        status_text = "ENABLED" if token else "DISABLED"
        status_color = GREEN if token else RED
        
        spaces = box_width - 4 - len(name) - 1 - len(status_text)
        
        # Construct the line
        line_content = f"{name}:{ ' ' * spaces }{status_color}{status_text}{RESET}"
        print_line(line_content)

    print_border("╚", "═", "╝")

def list_files():
    files = [f for f in os.listdir('.') if os.path.isfile(f)]
    return files


def list_text_files():
    files = [f for f in os.listdir('.') if os.path.isfile(f) and f.endswith('.txt')]
    return files


def get_urls_from_file():
    files = list_files()
    if not files:
        print(f"{RED}No files found in the current directory.{RESET}")
        return []

    print()
    print(f"{CYAN}Select a file to load URLs from:{RESET}")
    for idx, f in enumerate(files, 1):
        print(f"{YELLOW}{idx}{RESET}: {f}")

    while True:
        choice = input(f"Enter the number of the file: ")
        if choice.isdigit() and 1 <= int(choice) <= len(files):
            filename = files[int(choice) - 1]
            try:
                with open(filename, 'r') as file:
                    # 1. Read all non-empty lines
                    all_urls = [line.strip() for line in file if line.strip()]

                if not all_urls:
                    print(f"{RED}File is empty.{RESET}")
                    return []

                print(f"{GREEN}Loaded {len(all_urls)} URLs from '{filename}'.{RESET}")

                selected_indexes = select_files_interactive(all_urls, "Select URLs to download")

                final_urls = [all_urls[i] for i in selected_indexes]
                
                print(f"{GREEN}Selected {len(final_urls)} URLs.{RESET}")
                return final_urls

            except Exception as e:
                print(f"{RED}Could not read file '{filename}': {e}{RESET}")
                print(f"{YELLOW}Please select a different file.{RESET}")
                continue
        
        print(f"{RED}Invalid choice, try again.{RESET}")


def get_urls_from_input():
    print()
    print("Paste your URLs one per line (press enter on an empty line to finish):")
    urls = []
    while True:
        line = input()
        if not line.strip():
            break
        urls.append(line.strip())
    return urls

def select_files_interactive(files, prompt="Enter selection"):
    """
    Unified selection handler for all debrid providers.
    
    files: list of dicts or strings (anything indexable)
    prompt: custom prompt string
    
    Returns: list of 0-based indexes
    """
    max_index = len(files)

    print(f"{CYAN}{prompt}:{RESET}")
    for idx, f in enumerate(files, 1):
        if isinstance(f, dict):
            name = f.get("name") or f.get("short_name") or f.get("path") or str(f)
        else:
            name = str(f)
        size = f.get("size") if isinstance(f, dict) else None
        if size:
            mb = size // (1024 * 1024)
            print(f"{YELLOW}{idx}{RESET}: {name} {CYAN}({mb} MB){RESET}")
        else:
            print(f"{YELLOW}{idx}{RESET}: {name}")

    choice = input(
        f"{CYAN}Enter numbers, commas, ranges (e.g. 1,3-5) or 'all' (default all): {RESET}"
    ).strip()

    # Default = all
    if not choice or choice.lower() == "all":
        return list(range(max_index))

    # Use your existing range parser
    raw = parse_selection(choice, max_index)

    selected = [i - 1 for i in raw if 1 <= i <= max_index]

    return selected

def show_progress_factory():
    start_time = [time.time()]

    def show_progress(block_num, block_size, total_size):
        downloaded = block_num * block_size
        elapsed = time.time() - start_time[0]
        speed = downloaded / elapsed if elapsed > 0 else 0
        percent = min(100, downloaded * 100 // (total_size or 1))
        bar_length = 50
        num_hashes = percent // 2
        bar = '#' * num_hashes
        bar = bar.ljust(bar_length)
        bar_colored = f"{YELLOW}{bar}{RESET}"
        if speed >= 1024 * 1024:
            speed_str = f"{speed/1024/1024:.2f} MB/s"
        elif speed >= 1024:
            speed_str = f"{speed/1024:.1f} KB/s"
        else:
            speed_str = f"{speed:.0f} B/s"
        elapsed_str = time.strftime("%M:%S", time.gmtime(elapsed))
        sys.stdout.write(f"\r[{bar_colored}] {GREEN}{percent}%{RESET} {YELLOW}::{RESET} {speed_str} {YELLOW}::{RESET} {elapsed_str}")
        sys.stdout.flush()
        if downloaded >= total_size:
            print()

    return show_progress


def download_file(url, filename=None):
    def human_readable_size(num):
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if num < 1024:
                return f"{num:.2f} {unit}"
            num /= 1024
        return f"{num:.2f} PB"

    try:
        with requests.get(url, stream=True, allow_redirects=True) as r:
            r.raise_for_status()

            if filename is None:
                cd = r.headers.get('content-disposition')
                if cd:
                    fname = re.findall('filename="(.+)"', cd)
                    filename = fname[0] if fname else url.split("/")[-1]
                else:
                    filename = r.url.split("/")[-1]
            else:
                cd = r.headers.get('content-disposition')
                if cd:
                    fname = re.findall('filename="(.+)"', cd)
                    filename = fname[0] if fname else url.split("/")[-1]
                else:
                    filename = r.url.split("/")[-1]

            filename = urllib.parse.unquote(filename)
            total_size = int(r.headers.get('content-length', 0))
            total_human = human_readable_size(total_size)

            print(f"Downloading: {YELLOW}{filename}{RESET} ({CYAN}{total_human}{RESET})")

            start_time = time.time()
            downloaded = 0
            block_size = 8192

            with open(filename, "wb") as f:
                for chunk in r.iter_content(block_size):
                    if not chunk:
                        continue

                    f.write(chunk)
                    downloaded += len(chunk)

                    elapsed = time.time() - start_time
                    speed = downloaded / elapsed if elapsed > 0 else 0

                    percent = int(downloaded * 100 / total_size) if total_size else 0
                    bar_length = 50
                    filled = percent * bar_length // 100
                    bar = "#" * filled + " " * (bar_length - filled)

                    # Convert speed
                    if speed >= 1024 * 1024:
                        speed_str = f"{speed/1024/1024:.2f} MB/s"
                    elif speed >= 1024:
                        speed_str = f"{speed/1024:.1f} KB/s"
                    else:
                        speed_str = f"{speed:.0f} B/s"

                    elapsed_str = time.strftime("%M:%S", time.gmtime(elapsed))
                    downloaded_human = human_readable_size(downloaded)

                    sys.stdout.write(
                        f"\r[{YELLOW}{bar}{RESET}] "
                        f"{GREEN}{percent}%{RESET} "
                        f":: {CYAN}{speed_str}{RESET} "
                        f":: {downloaded_human}/{total_human} "
                        f":: {elapsed_str}"
                    )
                    sys.stdout.flush()

            print()
            print(f"{GREEN}Saved as:{RESET} {YELLOW}{filename}{RESET}")

    except Exception as e:
        print(f"{RED}Failed to download:{RESET} {YELLOW}{url}{RESET} {RED}- {e}{RESET}")



def torrent_to_magnet(filepath):
    with open(filepath, 'rb') as f:
        torrent = bencodepy.decode(f.read())
    info = torrent[b'info']
    # Get the bencoded info dict and SHA1 hash
    info_bencoded = bencodepy.encode(info)
    info_hash = hashlib.sha1(info_bencoded).hexdigest()
    # Get display name
    name = info.get(b'name', b'').decode('utf-8', errors='ignore')
    # Build magnet link
    magnet = f"magnet:?xt=urn:btih:{info_hash}"
    if name:
        magnet += f"&dn={urllib.parse.quote(name)}"
    return magnet


def is_magnet(url):
    return url.strip().startswith("magnet:")


def parse_selection(selection_input, max_index):
    selection = set()
    for part in selection_input.split(","):
        part = part.strip()
        if '-' in part:
            try:
                start, end = map(int, part.split('-'))
                if start <= end and 1 <= start <= max_index and 1 <= end <= max_index:
                    selection.update(range(start, end + 1))
            except ValueError:
                continue
        elif part.isdigit():
            idx = int(part)
            if 1 <= idx <= max_index:
                selection.add(idx)
    return sorted(selection)


def get_real_debrid_links(url=None):
    token = REAL_DEBRID_API_TOKEN
    while not url:
        url = input(f"Paste your magnet or hoster URL: ").strip()
    headers = {"Authorization": f"Bearer {token}"}

    if is_magnet(url):
        # Magnet logic
        resp = requests.post(
            "https://api.real-debrid.com/rest/1.0/torrents/addMagnet",
            data={"magnet": url},
            headers=headers
        )
        if resp.status_code != 201:
            print(f"{RED}Failed to add magnet.{RESET}")
            return []
        torrent_id = resp.json()["id"]

        # Wait for torrent to be ready
        selection_sent = False
        while True:
            info = requests.get(
                f"https://api.real-debrid.com/rest/1.0/torrents/info/{torrent_id}",
                headers=headers
            ).json()
            if info["status"] in ("waiting_files", "waiting_files_selection"):
                if not selection_sent:
                    files = info["files"]

                    display_files = []
                    for f in files:
                        path = f.get("path", "").lstrip("/\\")
                        size_bytes = f.get("bytes", 0)
                        mb = size_bytes // (1024 * 1024)
                        display_files.append({
                            "name": path,
                            "size": size_bytes,
                        })

                    print()
                    selected_indexes = select_files_interactive(
                        display_files,
                        "Select files in torrent"
                    )

                    if not selected_indexes:
                        print(f"{RED}No files selected.{RESET}")
                        return []

                    file_ids = [str(files[i]["id"]) for i in selected_indexes]

                    requests.post(
                        f"https://api.real-debrid.com/rest/1.0/torrents/selectFiles/{torrent_id}",
                        data={"files": ",".join(file_ids)},
                        headers=headers
                    )
                    print(f"{GREEN}Selection sent, waiting for Real-Debrid to process...{RESET}")
                    selection_sent = True
                else:
                    print(f"{YELLOW}Waiting for Real-Debrid to process your selection...{RESET}")
                time.sleep(3)
            elif info["status"] == "downloaded":
                links = []
                for dl in info["links"]:
                    # Unrestrict each link to get the direct download
                    r = requests.post(
                        "https://api.real-debrid.com/rest/1.0/unrestrict/link",
                        data={"link": dl},
                        headers=headers
                    )
                    if r.status_code == 200 and "download" in r.json():
                        links.append(r.json()["download"])
                print(f"{GREEN}Resolved direct links:{RESET}")
                for l in links:
                    print(f"{YELLOW}{l}{RESET}")
                return links
            elif info["status"] == "magnet_error":
                print(f"{RED}Magnet error.{RESET}")
                return []
            else:
                if info["status"] == "downloading":
                    speed = info.get("speed", 0)
                    seeders = info.get("seeders", 0)
                    percent = info.get("progress", 0)
                    bar_length = 30
                    num_hashes = int(percent * bar_length // 100)
                    bar = '#' * num_hashes
                    bar = bar.ljust(bar_length)
                    bar_colored = f"{YELLOW}{bar}{RESET}"
                    percent_str = f"{GREEN}{percent}%{RESET}"
                    if speed >= 1024 * 1024:
                        speed_str = f"{speed/1024/1024:.2f} MB/s"
                    elif speed >= 1024:
                        speed_str = f"{speed/1024:.1f} KB/s"
                    else:
                        speed_str = f"{speed:.0f} B/s"
                    sys.stdout.write(
                        f"\r{YELLOW}Downloading to cloud...{RESET} [{bar_colored}] "
                        f"{percent_str} | Speed: {CYAN}{speed_str}{RESET} | "
                        f"Seeders: {GREEN}{seeders}{RESET}   "
                    )
                    sys.stdout.flush()
                else:
                    print(f"{YELLOW}Waiting for Real-Debrid... Status: {info['status']}{RESET}")
                time.sleep(3)
                if info["status"] != "downloading":
                    print()
                time.sleep(3)

    elif "mega.nz/folder/" in url and "/file/" not in url:
        # Extract file links from folder
        file_links = extract_mega_files_from_folder(url)
        if not file_links:
            print(f"{RED}Could not extract MEGA file links from folder.{RESET}")
            return []

        print()
        print(f"{YELLOW}Unlocking files...{RESET}")
        unlocked = []
        for f in file_links:
            resp = requests.post(
                "https://api.real-debrid.com/rest/1.0/unrestrict/link",
                data={"link": f},
                headers=headers
            )
            data = resp.json()
            if "download" in data:
                filename = data.get("filename") or urllib.parse.unquote(f.split("/")[-1])
                unlocked.append({
                    "name": filename,
                    "url": data["download"]
                })
            else:
                print(f"{RED}Could not unlock:{RESET} {YELLOW}{f}{RESET}")

        if not unlocked:
            print(f"{RED}No files were unlocked.{RESET}")
            return []

        selected_indexes = select_files_interactive(
            unlocked,
            "Select files to download"
        )

        if not selected_indexes:
            print(f"{RED}No files selected.{RESET}")
            return []

        return [unlocked[i]["url"] for i in selected_indexes]

    else:
        # Hoster logic
        resp = requests.post(
            "https://api.real-debrid.com/rest/1.0/unrestrict/link",
            data={"link": url},
            headers=headers
        )
        data = resp.json()
        if resp.status_code == 200 and "download" in data:
            print(f"{GREEN}Resolved direct link:{RESET}")
            print(f"{YELLOW}{data['download']}{RESET}")
            return [data["download"]]
        print(f"{RED}Hoster not supported or failed.{RESET}")

def parse_alldebrid_files(files_list):
    """
    Recursively extract files with links from AllDebrid's nested structure.
    AllDebrid uses 'e' for folder entries and 'l' for file links.
    """
    flat_files = []
    for item in files_list:
        # If it has a link ('l'), it's a download-ready file
        if "l" in item:
            flat_files.append({
                "name": item.get("n", "Unknown"),
                "size": item.get("s", 0),
                "link": item.get("l")
            })
        # If it has entries ('e'), it's a folder -> recurse down
        elif "e" in item:
            flat_files.extend(parse_alldebrid_files(item["e"]))
    return flat_files

def get_alldebrid_links(url=None):
    token = ALLDEBRID_API_TOKEN or input(f"{CYAN}Enter your AllDebrid API token:{RESET} ").strip()
    if not url:
        url = input(f"{CYAN}Paste your magnet or hoster URL:{RESET} ").strip()

    if is_magnet(url):
        # 1. UPLOAD MAGNET
        resp = requests.post(
            "https://api.alldebrid.com/v4/magnet/upload",
            data={"agent": "dl-script", "apikey": token, "magnets[]": url}
        )
        data = resp.json()

        if data.get("status") != "success":
            print(f"{RED}Failed to add magnet: {data.get('error', {}).get('message', 'Unknown error')}{RESET}")
            return []

        # AllDebrid upload response 'magnets' is a list
        magnet_id = data["data"]["magnets"][0]["id"]
        
        # 2. POLL STATUS
        while True:
            status_resp = requests.get(
                "https://api.alldebrid.com/v4.1/magnet/status",
                params={"agent": "dl-script", "apikey": token, "id": magnet_id}
            ).json()

            if status_resp.get("status") != "success":
                print(f"{RED}Error fetching status.{RESET}")
                return []

            # For ID requests, 'magnets' is usually a dict, but safety check for list
            magnet = status_resp["data"]["magnets"]
            if isinstance(magnet, list):
                magnet = magnet[0]

            status_code = magnet.get("statusCode")
            status_msg = magnet.get("status", "Unknown")

            # --- CASE A: READY (Links available) ---
            if status_code == 4:
                # FIXED: Extract links recursively from the 'files' tree
                files_tree = magnet.get("files", [])
                
                # Use our new helper function to flatten the nested JSON
                available_files = parse_alldebrid_files(files_tree)
                
                if not available_files:
                    print(f"{RED}Torrent is ready but returned no links/files.{RESET}")
                    # Debug print to help identify structure issues
                    # print(json.dumps(magnet, indent=3)) 
                    return []

                print(f"\n{GREEN}Torrent Ready! Found {len(available_files)} links.{RESET}")

                # Build display list for the Unified Selector
                display_files = []
                for f in available_files:
                    display_files.append({
                        "name": f["name"],
                        "size": f["size"]
                    })

                # 3. SELECT FILES (Client-Side)
                selected_indexes = select_files_interactive(
                    display_files, 
                    "Select files to download"
                )

                if not selected_indexes:
                    print(f"{RED}No files selected.{RESET}")
                    return []

                final_urls = []
                print(f"{CYAN}Unlocking selected links...{RESET}")

                # 4. UNLOCK SELECTED LINKS
                for idx in selected_indexes:
                    file_info = available_files[idx]
                    link_to_unlock = file_info["link"]
                    
                    unlock_resp = requests.get(
                        "https://api.alldebrid.com/v4.1/link/unlock",
                        params={"agent": "dl-script", "apikey": token, "link": link_to_unlock}
                    ).json()

                    if unlock_resp.get("status") == "success":
                        unlocked_link = unlock_resp["data"].get("link")
                        if unlocked_link:
                            final_urls.append(unlocked_link)
                            print(f"{GREEN}Unlocked:{RESET} {file_info['name']}")
                    else:
                         err = unlock_resp.get("error", {}).get("message", "Unknown")
                         print(f"{RED}Failed to unlock:{RESET} {file_info['name']} ({err})")

                return final_urls

            # --- CASE B: DOWNLOADING / QUEUED ---
            elif status_code in (0, 1, 2, 3):
                downloaded = magnet.get("downloaded", 0)
                size = magnet.get("size", 1)
                speed = magnet.get("downloadSpeed", 0)
                seeders = magnet.get("seeders", 0)
                
                percent = (downloaded / size) * 100 if size > 0 else 0
                
                if speed > 1024*1024: speed_str = f"{speed/1024/1024:.2f} MB/s"
                elif speed > 1024: speed_str = f"{speed/1024:.0f} KB/s"
                else: speed_str = f"{speed} B/s"

                bar_len = 30
                filled = int(percent / 100 * bar_len)
                bar = "#" * filled + "-" * (bar_len - filled)

                sys.stdout.write(
                    f"\r{YELLOW}{status_msg}...{RESET} "
                    f"[{bar}] {GREEN}{percent:.1f}%{RESET} "
                    f"| {CYAN}{speed_str}{RESET} | S: {seeders}   "
                )
                sys.stdout.flush()
                time.sleep(2)

            # --- CASE C: ERROR ---
            elif status_code > 4:
                error_code = magnet.get("errorCode")
                print(f"\n{RED}Magnet Error {error_code}: {status_msg}{RESET}")
                requests.get(
                    "https://api.alldebrid.com/v4.1/magnet/delete",
                    params={"agent": "dl-script", "apikey": token, "id": magnet_id}
                )
                return []
                
            else:
                time.sleep(2)

    elif "mega.nz/folder/" in url and "/file/" not in url:
        # Extract MEGA folder contents
        file_links = extract_mega_files_from_folder(url)
        if not file_links:
            print(f"{RED}Could not extract MEGA file links from folder.{RESET}")
            return []

        print(f"{YELLOW}Unlocking files...{RESET}")
        unlocked = []

        for f in file_links:
            resp = requests.get(
                "https://api.alldebrid.com/v4.1/link/unlock",
                params={"agent": "dl-script", "apikey": token, "link": f}
            )
            data = resp.json()

            if data.get("status") == "success" and "link" in data.get("data", {}):
                filename = data["data"].get("filename") or f.split("/")[-1]
                unlocked.append({
                    "name": filename,
                    "url": data["data"]["link"]
                })
            else:
                print(f"{RED}Could not unlock:{RESET} {YELLOW}{f}{RESET}")

        if not unlocked:
            print(f"{RED}No files were unlocked.{RESET}")
            return []

        # Unified selection
        selected = select_files_interactive(
            unlocked,
            "Select files to download"
        )

        return [unlocked[i]["url"] for i in selected]

    else:
        # Hoster direct unlock
        resp = requests.get(
            "https://api.alldebrid.com/v4.1/link/unlock",
            params={"agent": "dl-script", "apikey": token, "link": url}
        )
        data = resp.json()

        if data.get("status") == "success" and "link" in data.get("data", {}):
            print(f"{GREEN}Resolved direct link:{RESET}")
            print(f"{YELLOW}{data['data']['link']}{RESET}")
            return [data["data"]["link"]]

        print(f"{RED}Hoster not supported or failed.{RESET}")
        return []


def get_premiumize_links(url=None):
    token = PREMIUMIZE_API_TOKEN or input(f"{CYAN}Enter your Premiumize.me API token:{RESET} ").strip()
    if not url:
        url = input(f"{CYAN}Paste your magnet or hoster URL:{RESET} ").strip()

    if is_magnet(url):
        # Magnet logic
        resp = requests.get(
            "https://www.premiumize.me/api/transfer/create",
            params={"apikey": token, "src": url}
        )
        resp.raise_for_status()
        data = resp.json()
        transfer_id = data["id"]

        print()
        print(f"{GREEN}Transfer created, ID:{RESET} {YELLOW}{transfer_id}{RESET}")

        # Wait until finished
        while True:
            resp = requests.get(
                "https://www.premiumize.me/api/transfer/list",
                params={"apikey": token}
            )
            resp.raise_for_status()
            library = resp.json().get("transfers", [])
            transfer = next((t for t in library if t["id"] == transfer_id), None)
            if not transfer:
                print(f"{RED}Transfer not found after creation.{RESET}")
                return []

            progress = transfer.get('progress')
            if progress is None:
                progress = 1.0 if transfer.get("status") == "finished" else 0.0
            percent = progress * 100

            # Try to extract speed and peers from the message
            speed = 0
            seeders = 0
            msg = transfer.get("message") or ""
            if msg:
                speed_match = re.search(r"([\d\.]+)\s*(KB|MB|B)/s", msg)
                if speed_match:
                    val, unit = speed_match.groups()
                    val = float(val)
                    if unit == "MB":
                        speed = int(val * 1024 * 1024)
                    elif unit == "KB":
                        speed = int(val * 1024)
                    else:
                        speed = int(val)
                seeders_match = re.search(r"from (\d+) peer", msg)
                if seeders_match:
                    seeders = int(seeders_match.group(1))

            bar_length = 30
            num_hashes = int(percent * bar_length // 100)
            bar = '#' * num_hashes
            bar = bar.ljust(bar_length)
            bar_colored = f"{YELLOW}{bar}{RESET}"
            percent_str = f"{GREEN}{percent:.2f}%{RESET}"
            if speed >= 1024 * 1024:
                speed_str = f"{speed/1024/1024:.2f} MB/s"
            elif speed >= 1024:
                speed_str = f"{speed/1024:.1f} KB/s"
            else:
                speed_str = f"{speed:.0f} B/s"

            # Only show progress bar if actually downloading
            if transfer["status"] == "running" and progress < 1.0 and "Moving to cloud" not in msg:
                sys.stdout.write(
                    f"\r{YELLOW}Downloading to cloud...{RESET} [{bar_colored}] {percent_str} | Speed: {CYAN}{speed_str}{RESET} | Seeders: {GREEN}{seeders}{RESET}   "
                )
                sys.stdout.flush()
            else:
                # Print a status message instead of progress bar
                sys.stdout.write(f"\r{YELLOW}{msg or transfer['status'].capitalize()}{RESET} {' ' * 60}\n")
                sys.stdout.flush()
                if transfer["status"] == "finished":
                    folder_id = transfer["folder_id"]
                    break
                if transfer["status"] == "error":
                    print(f"\n{RED}Premiumize transfer error.{RESET}")
                    return []
            time.sleep(3)

        folder_resp = requests.get(
            "https://www.premiumize.me/api/folder/list",
            params={"apikey": token, "id": folder_id}
        ).json()

        files = [
            f for f in folder_resp.get("content", [])
            if f.get("type") == "file" and "link" in f
        ]

        if not files:
            print(f"{RED}No downloadable files found in transfer folder.{RESET}")
            return []

        display_files = [
            {"name": f.get("name", "Unknown"), "size": f.get("size", 0)}
            for f in files
        ]

        selected_indexes = select_files_interactive(
            display_files,
            "Select files to download"
        )

        return [files[i]["link"] for i in selected_indexes]

    else:
        # Hoster logic
        resp = requests.get(
            "https://www.premiumize.me/api/transfer/directdl",
            params={"apikey": token, "src": url}
        )
        data = resp.json()
        if data.get("status") == "success":
            if "location" in data:
                print(f"{GREEN}Resolved direct link:{RESET}")
                print(f"{YELLOW}{data['location']}{RESET}")
                return [data["location"]]
            elif data.get("type") == "container" and "content" in data:
                print(f"{CYAN}Container detected. Files in folder:{RESET}")
                files = data["content"]

                # Build display list for unified selector
                display_files = [
                    {"name": str(f), "size": None}
                    for f in files
                ]

                selected_indexes = select_files_interactive(
                    display_files,
                    "Select container entries"
                )

                selected = [files[i] for i in selected_indexes]
                # Now unlock each selected file
                unlocked = []
                for f in selected:
                    unlock_resp = requests.get(
                        "https://www.premiumize.me/api/transfer/directdl",
                        params={"apikey": token, "src": f}
                    )
                    unlock_data = unlock_resp.json()
                    if unlock_data.get("status") == "success" and "location" in unlock_data:
                        unlocked.append(unlock_data["location"])
                        print(f"{GREEN}Unlocked:{RESET} {YELLOW}{f}{RESET} {CYAN}→{RESET} {GREEN}{unlock_data['location']}{RESET}")
                    else:
                        print(f"{RED}Could not unlock:{RESET} {YELLOW}{f}{RESET}")
                return unlocked
        print(f"{RED}Hoster not supported or failed.{RESET}")
        return []

def get_premiumize_links_from_nzb(nzb_path: str) -> list[str]:
    from pathlib import Path
    import requests, time

    print(f"{CYAN}Processing NZB via Premiumize...{RESET}")
    params = {'apikey': PREMIUMIZE_API_TOKEN}
    nzb_name = Path(nzb_path).name

    try:
        # 1️⃣ Create transfer
        with open(nzb_path, "rb") as f:
            resp = requests.post(
                "https://www.premiumize.me/api/transfer/create",
                params=params,
                files={'file': (nzb_name, f, 'application/x-nzb')},
                timeout=30
            )

        data = resp.json()

        if data.get("status") != "success":
            if data.get("message") == "You have already added this nzb file.":
                print(f"{YELLOW}NZB already added. Attempting to find in transfer list...{RESET}")
                list_resp = requests.get(
                    "https://www.premiumize.me/api/transfer/list",
                    params=params,
                    timeout=10
                ).json()

                transfers = list_resp.get("transfers", [])
                match = next((t for t in transfers if t.get("name") == nzb_name), None)
                if match:
                    transfer_id = match.get("id")
                    print(f"{GREEN}Found existing transfer with ID {transfer_id}. Proceeding...{RESET}")
                else:
                    print(f"{RED}Could not find existing transfer for this NZB.{RESET}")
                    return []
            else:
                print(f"{RED}Transfer failed: {data.get('error') or data.get('message')}{RESET}")
                return []
        else:
            transfer_id = data["id"]
            print(f"{GREEN}Transfer queued—ID {transfer_id}. {RESET}")

        # 2️⃣ Poll until done (“finished” or “error”)
        status = None
        try:
            while True:
                lst = requests.get(
                    "https://www.premiumize.me/api/transfer/list",
                    params={**params, 'id': transfer_id},
                    timeout=10
                ).json()

                info = lst.get("transfers", [{}])[0]
                status = info.get("status")
                message = (info.get("message") or "").strip()
                progress = info.get("progress") or 0

                if status not in ("finished", "error"):
                    # Draw progress bar
                    bar_length = 30
                    bar = '#' * int(progress * bar_length)
                    bar = bar.ljust(bar_length)
                    percent = int(progress * 100)
                    sys.stdout.write(
                        f"\r{YELLOW}Downloading to cloud...{RESET} [{YELLOW}{bar}{RESET}] {GREEN}{percent}%{RESET} | {message}   "
                    )
                    sys.stdout.flush()

                if status in ("finished", "error"):
                    print()  # finish the line
                    break

                time.sleep(3)

        except KeyboardInterrupt:
            print(f"\n{RED}Cancelled by user.{RESET}")
            return []

        if status != "finished":
            error_message = (info.get("message") or "").strip().lower()

            if "cannot be completed" in error_message:
                print(f"{RED}Premiumize could not complete this NZB. It was aborted on their side and cannot be downloaded.{RESET}")
            else:
                print(f"{RED}Transfer did not finish (status={status}){RESET}")
            return []

        # 3️⃣ Try direct download via src first
        dl_resp = requests.post(
            "https://www.premiumize.me/api/transfer/directdl",
            data={"src": info.get("src")},
            params={"apikey": PREMIUMIZE_API_TOKEN},
            timeout=10
        )
        dl_data = dl_resp.json()

        if dl_data.get("status") == "success":
            content = dl_data.get("content", [])
            if not content:
                print(f"{RED}No files in direct download response.{RESET}")
                return []

            display_files = [
                {
                    "name": f.get("path", "Unknown"),
                    "size": f.get("size", 0)
                }
                for f in content
            ]

            selected_indexes = select_files_interactive(
                display_files,
                "Select NZB files to download"
            )

            return [content[i]["link"] for i in selected_indexes if content[i].get("link")]
        else:
            # 4️⃣ Fall back to /folder/list
            folder_id = info.get("folder_id")
            if not folder_id:
                print(f"{RED}No folder ID available to list contents.{RESET}")
                return []

            folder_resp = requests.get(
                "https://www.premiumize.me/api/folder/list",
                params={"id": folder_id, "apikey": PREMIUMIZE_API_TOKEN},
                timeout=10
            )
            folder_data = folder_resp.json()

            if folder_data.get("status") != "success":
                print(f"{RED}Failed to list folder: {folder_data.get('message')}{RESET}")
                return []

            files = [f for f in folder_data.get("content", []) if f.get("type") == "file" and f.get("link")]
            if not files:
                print(f"{RED}No downloadable files found in folder.{RESET}")
                return []

            display_files = [
                {
                    "name": f.get("name", "Unknown"),
                    "size": f.get("size", 0)
                }
                for f in files
            ]

            selected_indexes = select_files_interactive(
                display_files,
                "Select NZB files to download"
            )

            return [files[i]["link"] for i in selected_indexes]

    except Exception as e:
        print(f"{RED}Exception during Premiumize NZB processing: {e}{RESET}")
        return []

def get_torbox_links(url=None):
    token = TORBOX_API_TOKEN or input(f"{CYAN}Enter your Torbox API token:{RESET} ").strip()
    if not url:
        url = input(f"{CYAN}Paste your magnet or hoster URL:{RESET} ").strip()

    headers = {"Authorization": f"Bearer {token}"}

    #  MAGNET MODE
    if is_magnet(url):
        # 1. Create torrent job
        resp = requests.post(
            "https://api.torbox.app/v1/api/torrents/createtorrent",
            files={
                "magnet": (None, url),
                "allow_zip": (None, "true"),
                "as_queued": (None, "false"),
            },
            headers=headers,
            timeout=10
        )
        resp.raise_for_status()
        data = resp.json()

        if not data.get("success"):
            print(f"{RED}Error creating torrent: {data.get('error')}{RESET}")
            return []

        torrent_id = data["data"].get("torrent_id") or data["data"].get("id")
        print(f"{GREEN}Torrent queued — ID {torrent_id}. Getting file list...{RESET}")

        # 2. Fetch metadata with real file IDs
        mylist_resp = requests.get(
            "https://api.torbox.app/v1/api/torrents/mylist",
            params={"token": token, "id": torrent_id},
            headers=headers,
            timeout=15
        )
        mylist_data = mylist_resp.json()

        if not mylist_data.get("success") or not mylist_data.get("data"):
            print(f"{RED}Failed to fetch file list from /mylist{RESET}")
            return []

        files = mylist_data["data"].get("files", [])
        if not files:
            print(f"{RED}No files found in torrent metadata.{RESET}")
            return []

        print(f"{GREEN}Found {len(files)} files. Checking which are ready...{RESET}")

        display_files = []
        for f in files:
            size = f.get("size", 0)
            display_files.append({
                "name": f.get("short_name", f.get("name", "Unknown")),
                "size": size
            })

        selected_indexes = select_files_interactive(display_files, "Select files to download")

        links = []

        # 3. Request download link for each selected file
        for idx in selected_indexes:
            f = files[idx]
            file_id = f["id"]
            name = f.get("short_name") or f.get("name", "Unknown")

            print(f"{YELLOW}Waiting for file {CYAN}{idx+1}{RESET}: {name}{RESET}")

            # Keep polling until ready
            while True:
                r = requests.get(
                    "https://api.torbox.app/v1/api/torrents/requestdl",
                    params={
                        "token": token,
                        "torrent_id": torrent_id,
                        "file_id": file_id,
                        "redirect": "false",
                    },
                    timeout=10,
                )
                resp_data = r.json()

                if r.status_code == 200 and resp_data.get("success"):
                    download_url = resp_data.get("data")
                    print(f"{GREEN}File {idx + 1} is ready.{RESET}")
                    links.append(download_url)
                    break

                # File not ready yet
                if "not ready" in resp_data.get("error", "").lower():
                    print(f"{YELLOW}File {idx + 1} not ready. Retrying...{RESET}")
                    time.sleep(5)
                    continue

                # Unexpected error
                print(f"{RED}Unexpected error for file {idx+1}: {resp_data}{RESET}")
                break

        # Final printing
        if links:
            print(f"{GREEN}Resolved direct links:{RESET}")
            for l in links:
                print(f"{YELLOW}{l}{RESET}")
        else:
            print(f"{RED}No files ready for download.{RESET}")

        return links

    #  HOSTER MODE  (non-magnet)
    md5_hash = hashlib.md5(url.encode("utf-8")).hexdigest()

    check_resp = requests.post(
        "https://api.torbox.app/v1/api/webdl/checkcached",
        json={"hashes": [md5_hash]},
        headers=headers,
        timeout=30
    )

    if check_resp.status_code != 200 or not check_resp.json().get("success"):
        print(f"{RED}Failed to check cached webdl.{RESET}")
        return []

    cached_data = check_resp.json().get("data", {})
    is_cached = md5_hash in cached_data

    print(
        f"{GREEN}Found cached web download. Creating job...{RESET}"
        if is_cached else
        f"{YELLOW}Not cached. Creating new job...{RESET}"
    )

    create_resp = requests.post(
        "https://api.torbox.app/v1/api/webdl/createwebdownload",
        data={"link": url},
        headers=headers,
        timeout=30
    )

    if create_resp.status_code != 200 or not create_resp.json().get("success"):
        print(f"{RED}Failed to create web download job.{RESET}")
        return []

    data = create_resp.json().get("data", {})
    web_id = data.get("webdownload_id")

    if not web_id:
        print(f"{RED}Job created but no webdownload_id returned.{RESET}")
        return []

    print(f"{CYAN}Resolved web_id:{RESET} {web_id}")

    # First status check
    mylist_resp = requests.get(
        "https://api.torbox.app/v1/api/webdl/mylist",
        params={"token": token, "id": web_id},
        headers=headers,
        timeout=30
    )
    mylist_data = mylist_resp.json()

    if not mylist_data.get("success"):
        print(f"{RED}Failed to retrieve job status from mylist.{RESET}")
        return []

    data = mylist_data.get("data", {})
    state = data.get("download_state")
    progress = data.get("progress", 0.0)
    speed = data.get("download_speed", 0)
    files = data.get("files", [])

    # Poll if still processing
    pending_states = {"downloading", "processing", "waiting"}

    if state in pending_states and not files:
        print(f"{CYAN}Waiting for cloud download to finish...{RESET}")

        while state in pending_states:
            # Visual Progress Bar
            bar_len = 30
            filled = int(progress * bar_len)
            bar = "#" * filled
            bar = bar.ljust(bar_len)

            speed_mb = f"{speed / (1024 * 1024):.2f} MB/s" if speed else "—"

            sys.stdout.write(
                f"\r{YELLOW}Downloading to cloud...{RESET} "
                f"[{bar}] {GREEN}{int(progress*100)}%{RESET} :: {CYAN}{speed_mb}{RESET}   "
            )
            sys.stdout.flush()

            time.sleep(5)

            # Refresh status
            try:
                mylist_resp = requests.get(
                    "https://api.torbox.app/v1/api/webdl/mylist",
                    params={"token": token, "id": web_id},
                    headers=headers,
                    timeout=30
                )
                
                # Check for HTTP errors (e.g., 502 Bad Gateway)
                if mylist_resp.status_code != 200:
                    continue # Skip this loop iteration and try again in 5 seconds

                mylist_data = mylist_resp.json()
                
                # Check for API logic errors
                if not mylist_data.get("success"):
                    continue # API said "failed", skip and try again

                # safely get data, defaulting to empty dict if None
                data = mylist_data.get("data") or {} 
                
                state = data.get("download_state")
                progress = data.get("progress", 0.0)
                speed = data.get("download_speed", 0)
                
                # If state is None/Empty, break to avoid infinite loop of nothingness
                if not state:
                    print(f"\n{RED}Error: API returned empty state.{RESET}")
                    break

            except Exception as e:
                # If connection drops, don't crash. Just wait and try again.
                continue

        print() # Newline after progress bar finishes

    # Ensure file list exists
    files = data.get("files", [])
    if not files:
        print(f"{RED}No downloadable files listed.{RESET}")
        return []

    # Build display file entries for unified selector
    display_files = []
    for f in files:
        display_files.append({
            "name": f.get("short_name", "Unknown"),
            "size": f.get("size", 0)
        })

    # File selection
    selected_indexes = select_files_interactive(display_files, "Select files")

    print(f"{GREEN}Requesting download links...{RESET}")
    urls = []

    for idx in selected_indexes:
        f = files[idx]
        fid = f.get("id")
        name = f.get("short_name", "Unknown")

        dl_resp = requests.get(
            "https://api.torbox.app/v1/api/webdl/requestdl",
            params={"token": token, "web_id": web_id, "file_id": fid},
            headers=headers,
            timeout=10
        )

        if dl_resp.status_code == 200 and dl_resp.json().get("success"):
            url = dl_resp.json().get("data")
            if url:
                print(f"{YELLOW}{name}:{RESET} {url}")
                urls.append(url)
            else:
                print(f"{RED}No URL for {name}.{RESET}")
        else:
            print(f"{RED}Failed to get download for {name}.{RESET}")

    return urls


def get_torbox_links_from_nzb(nzb_path: str) -> list[str]:
    print(f"{CYAN}Uploading NZB to Torbox...{RESET}")

    headers = {"Authorization": f"Bearer {TORBOX_API_TOKEN}"}

    try:
        # 1. Upload the NZB
        upload_url = "https://api.torbox.app/v1/api/usenet/createusenetdownload"
        with open(nzb_path, "rb") as f:
            files = {
                'file': (os.path.basename(nzb_path), f, 'application/x-nzb')
            }
            upload_resp = requests.post(
                upload_url,
                files=files,
                headers=headers,
                timeout=30
            )

        if upload_resp.status_code != 200 or not upload_resp.json().get("success"):
            print(f"{RED}Failed to upload NZB to Torbox.{RESET}")
            return []

        upload_data = upload_resp.json().get("data", {})
        usenet_id = upload_data.get("usenetdownload_id")
        
        if not usenet_id:
            # Fallback: sometimes ID is in a different field depending on API version
            usenet_id = upload_data.get("id")

        if not usenet_id:
            print(f"{RED}Upload succeeded but no Usenet ID returned.{RESET}")
            return []

        print(f"{CYAN}Usenet job started (ID: {usenet_id}). Waiting for cloud download...{RESET}")

        # 2. Poll for Status (Download -> Repair -> Extract)
        # We assume these are the states where we should keep waiting
        pending_states = {"downloading", "repairing", "extracting", "processing", "queued", "waiting"}
        
        files = []

        while True:
            try:
                mylist_resp = requests.get(
                    "https://api.torbox.app/v1/api/usenet/mylist",
                    params={"token": TORBOX_API_TOKEN, "id": usenet_id},
                    headers=headers,
                    timeout=30
                )
                
                if mylist_resp.status_code != 200:
                    time.sleep(5)
                    continue

                mylist_data = mylist_resp.json()
                if not mylist_data.get("success"):
                    time.sleep(5)
                    continue

                data = mylist_data.get("data") or {}
                
                # Extract status info
                state = data.get("download_state", "unknown").lower()
                progress = data.get("progress", 0.0)
                speed = data.get("download_speed", 0)
                files = data.get("files", [])

                # --- SUCCESS CONDITION ---
                # If state is finished, or we are cached and have files
                if state == "finished" or (state == "cached" and files):
                    print(f"\n{GREEN}Cloud download complete.{RESET}")
                    break

                # --- FAILURE CONDITION ---
                if state == "error" or state == "stalled":
                    print(f"\n{RED}Usenet download failed. State: {state}{RESET}")
                    return []

                # --- PROGRESS BAR ---
                if state in pending_states:
                    bar_len = 30
                    filled = int(progress * bar_len)
                    bar = "#" * filled
                    bar = bar.ljust(bar_len)
                    
                    # Convert speed to MB/s
                    speed_mb = f"{speed / (1024 * 1024):.2f} MB/s" if speed else "—"
                    
                    # Visual status mapping (e.g. "extracting" might not have speed)
                    status_display = state.capitalize()

                    sys.stdout.write(
                        f"\r{YELLOW}{status_display}...{RESET} "
                        f"[{bar}] {GREEN}{int(progress*100)}%{RESET} :: {CYAN}{speed_mb}{RESET}   "
                    )
                    sys.stdout.flush()
                    
                    time.sleep(3)
                else:
                    # Unknown state (maybe "completed"?), check if we have files
                    if files:
                        print(f"\n{GREEN}Download seems finished (State: {state}).{RESET}")
                        break
                    else:
                        print(f"\n{RED}Unknown state with no files: {state}{RESET}")
                        return []

            except KeyboardInterrupt:
                print(f"\n{RED}Aborted by user.{RESET}")
                return []
            except Exception as e:
                # Network glitch? Just wait and retry
                time.sleep(3)
                continue

        # 3. File Selection (Unified)
        if not files:
            print(f"{RED}No files found in metadata.{RESET}")
            return []

        # Build display entries
        display_files = []
        for f in files:
            display_files.append({
                "name": f.get("name", "Unknown"),
                "size": f.get("size", 0)
            })

        # Interactive Selector
        selected_indexes = select_files_interactive(
            display_files, 
            "Select NZB files to download"
        )

        if not selected_indexes:
            print(f"{RED}No files selected.{RESET}")
            return []

        print(f"{GREEN}Requesting download links...{RESET}")
        urls = []

        # 4. Get Links
        for idx in selected_indexes:
            f = files[idx]
            fid = f.get("id")
            name = f.get("name", "Unknown")

            # Try/Except block for individual link fetching
            try:
                dl_resp = requests.get(
                    "https://api.torbox.app/v1/api/usenet/requestdl",
                    params={"token": TORBOX_API_TOKEN, "usenet_id": usenet_id, "file_id": fid},
                    headers=headers,
                    timeout=30
                )

                if dl_resp.status_code == 200 and dl_resp.json().get("success"):
                    url = dl_resp.json().get("data")
                    if url:
                        print(f"{YELLOW}{name}:{RESET} {url}")
                        urls.append(url)
                    else:
                        print(f"{RED}No URL returned for {name}.{RESET}")
                else:
                    # Try to read error message
                    err = dl_resp.json().get("error", "Unknown error")
                    print(f"{RED}Failed to get link for {name}: {err}{RESET}")

            except Exception as e:
                print(f"{RED}Error fetching link for {name}: {e}{RESET}")

        return urls

    except Exception as e:
        print(f"{RED}Critical Exception during NZB workflow: {e}{RESET}")
        return []

def get_debrid_link_links(url=None):
    token = DEBRID_LINK_API_TOKEN or input(f"{CYAN}Enter your Debrid-Link API token:{RESET} ").strip()
    if not url:
        url = input(f"{CYAN}Paste your magnet or hoster URL:{RESET} ").strip()

    headers = {"Authorization": f"Bearer {token}"}

    # --- 1. MAGNET / SEEDBOX MODE ---
    if is_magnet(url):
        print(f"{CYAN}Adding to Debrid-Link Seedbox...{RESET}")
        
        # Add Magnet
        add_resp = requests.post(
            "https://debrid-link.com/api/v2/seedbox/add",
            data={"url": url, "async": "true"},
            headers=headers
        )
        add_data = add_resp.json()

        if not add_data.get("success"):
            error_msg = add_data.get("error", "Unknown error")
            print(f"{RED}Failed to add magnet: {error_msg}{RESET}")
            return []

        torrent_id = add_data["value"]["id"]
        print(f"{GREEN}Torrent added (ID: {torrent_id}). Waiting for cloud download...{RESET}")

        # Poll for Status
        files = []
        while True:
            list_resp = requests.get(
                "https://debrid-link.com/api/v2/seedbox/list",
                headers=headers
            )
            list_data = list_resp.json()
            
            if not list_data.get("success"):
                time.sleep(2)
                continue

            # Find our torrent
            torrents = list_data.get("value", [])
            if isinstance(torrents, dict): 
                torrents = torrents.get("torrents", [])
                
            current = next((t for t in torrents if t["id"] == torrent_id), None)

            if not current:
                print(f"{RED}Torrent ID not found in list.{RESET}")
                return []

            status_code = current.get("downloadPercent", 0)
            
            if status_code == 100:
                print(f"\n{GREEN}Cloud download complete!{RESET}")
                files = current.get("files", [])
                break
            else:
                speed = current.get("downloadSpeed", 0)
                peers = current.get("peersConnected", 0)
                
                if speed > 1024*1024: speed_str = f"{speed/1024/1024:.2f} MB/s"
                elif speed > 1024: speed_str = f"{speed/1024:.0f} KB/s"
                else: speed_str = f"{speed} B/s"

                bar_len = 30
                filled = int(status_code / 100 * bar_len)
                bar = "#" * filled + "-" * (bar_len - filled)

                sys.stdout.write(
                    f"\r{YELLOW}Downloading to cloud...{RESET} "
                    f"[{bar}] {GREEN}{status_code}%{RESET} "
                    f"| {CYAN}{speed_str}{RESET} | Peers: {peers}   "
                )
                sys.stdout.flush()
                time.sleep(3)

        # File Selection
        if not files:
            print(f"{RED}No files found in torrent.{RESET}")
            return []

        display_files = []
        for f in files:
            display_files.append({
                "name": f.get("name", "Unknown"),
                "size": f.get("size", 0)
            })

        selected_indexes = select_files_interactive(
            display_files, 
            "Select files to download"
        )

        final_urls = []
        for i in selected_indexes:
            dl_url = files[i].get("downloadUrl")
            if dl_url:
                final_urls.append(dl_url)
        
        return final_urls

    # --- 2. MEGA FOLDER MODE (New Addition) ---
    elif "mega.nz/folder/" in url and "/file/" not in url:
        print(f"{CYAN}Extracting MEGA folder contents...{RESET}")
        
        # Use existing helper to get individual links
        mega_links = extract_mega_files_from_folder(url)
        
        if not mega_links:
            print(f"{RED}No files found in MEGA folder.{RESET}")
            return []

        # Build display list for selector (Using URL as name since helper only returns URLs)
        display_files = [{"name": link, "size": 0} for link in mega_links]

        # Interactive Selection
        selected_indexes = select_files_interactive(
            display_files, 
            "Select files from MEGA folder"
        )

        if not selected_indexes:
            return []

        print(f"{CYAN}Unlocking selected files...{RESET}")
        final_urls = []
        
        # Iterate over selected links and unlock them one by one
        for idx in selected_indexes:
            target_link = mega_links[idx]
            
            resp = requests.post(
                "https://debrid-link.com/api/v2/downloader/add",
                data={"url": target_link},
                headers=headers
            )
            data = resp.json()

            if data.get("success"):
                val = data.get("value")
                # Handle list or dict return
                if isinstance(val, list) and val:
                    dl_link = val[0].get("downloadUrl")
                    name = val[0].get("name")
                elif isinstance(val, dict):
                    dl_link = val.get("downloadUrl")
                    name = val.get("name")
                else:
                    dl_link = None
                    name = "Unknown"

                if dl_link:
                    print(f"{GREEN}Unlocked:{RESET} {name}")
                    final_urls.append(dl_link)
                else:
                    print(f"{RED}Unlocked but no link found for:{RESET} {target_link}")
            else:
                 err = data.get("error", "Unknown error")
                 print(f"{RED}Failed to unlock:{RESET} {target_link} ({err})")
        
        return final_urls

    # --- 3. STANDARD HOSTER LINK MODE ---
    else:
        print(f"{CYAN}Unlocking hoster link...{RESET}")
        
        resp = requests.post(
            "https://debrid-link.com/api/v2/downloader/add",
            data={"url": url},
            headers=headers
        )
        data = resp.json()

        if data.get("success"):
            val = data.get("value")
            if isinstance(val, list) and val:
                link = val[0].get("downloadUrl")
                name = val[0].get("name")
            elif isinstance(val, dict):
                link = val.get("downloadUrl")
                name = val.get("name")
            else:
                link = None
                name = "Unknown"

            if link:
                print(f"{GREEN}Unlocked:{RESET} {name}")
                print(f"{YELLOW}{link}{RESET}")
                return [link]
        
        print(f"{RED}Failed to resolve link.{RESET}")
        return []

def get_all_files_with_links(token, folder_id):
    def fetch_folder_contents(folder_id):
        resp = requests.get(
            "https://www.premiumize.me/api/folder/list",
            params={"apikey": token, "id": folder_id}
        )
        resp.raise_for_status()
        return resp.json().get("content", [])

    files = []

    def recurse(folder_id, prefix=""):
        contents = fetch_folder_contents(folder_id)
        for item in contents:
            name = prefix + item["name"]
            if item.get("type") == "folder":
                recurse(item["id"], name + "/")
            elif item.get("type") == "file" and "link" in item:
                files.append({
                    "id": item["id"],
                    "name": name,
                    "size": item.get("size", 0),
                    "link": item["link"]
                })

    recurse(folder_id)
    return files


def extract_mega_files_from_folder(folder_url: str) -> list[str]:
    match = re.search(
        r"mega\.nz/folder/([a-zA-Z0-9_-]+)#([a-zA-Z0-9_-]+)",
        folder_url
    )
    if not match:
        print("Invalid MEGA folder URL")
        return []

    folder_id, key = match.group(1), match.group(2)
    try:
        resp = requests.post(
            "https://g.api.mega.co.nz/cs",
            params={"id": 0, "n": folder_id},
            json=[{"a": "f", "c": 1, "r": 1}]
        )
        files = resp.json()[0].get("f", [])
        urls = []

        for file in files:
            if file.get("t") == 0:  # regular file, not folder
                file_id = file.get("h")
                if file_id:
                    file_url = (
                        f"https://mega.nz/folder/{folder_id}#{key}/file/{file_id}"
                    )
                    urls.append(file_url)
        return urls

    except Exception as e:
        print(f"{RED}Error fetching MEGA folder via API: {e}{RESET}")
        if PREMIUMIZE_API_TOKEN:
            print(f"{YELLOW}Falling back to Premiumize...{RESET}")
            return extract_mega_file_links_with_premiumize(folder_url)
        else:
            return []


def extract_mega_file_links_with_premiumize(folder_url):
    token = PREMIUMIZE_API_TOKEN
    resp = requests.get(
        "https://www.premiumize.me/api/transfer/directdl",
        params={"apikey": token, "src": folder_url}
    )
    data = resp.json()
    if data.get("status") == "success" and data.get("type") == "container" and "content" in data:
        return data["content"]
    return []


def check_real_debrid_cache(url):
    if not REAL_DEBRID_API_TOKEN:
        return None

    headers = {"Authorization": f"Bearer {REAL_DEBRID_API_TOKEN}"}
    base_url = "https://api.real-debrid.com/rest/1.0"

    # --- MAGNET LINK HANDLING ---
    if is_magnet(url):
        torrent_id = None
        try:
            # 1. Add Magnet to Account
            add_resp = requests.post(
                f"{base_url}/torrents/addMagnet", 
                data={"magnet": url}, 
                headers=headers
            )
            
            if add_resp.status_code != 201:
                data = add_resp.json()
                if data.get("error") == "hoster_unsupported":
                    return ("not_supported", None)
                return ("supported", False)

            torrent_id = add_resp.json()['id']

            # 2. Get Info
            info_resp = requests.get(f"{base_url}/torrents/info/{torrent_id}", headers=headers).json()

            # 3. Smart Selection (Select largest file to force check)
            if info_resp['status'] == 'waiting_files_selection':
                files = info_resp['files']
                largest_file = sorted(files, key=lambda x: x['bytes'], reverse=True)[0]
                file_id = str(largest_file['id'])
                
                requests.post(f"{base_url}/torrents/selectFiles/{torrent_id}", data={"files": file_id}, headers=headers)
                info_resp = requests.get(f"{base_url}/torrents/info/{torrent_id}", headers=headers).json()

            # 4. Determine Cache Status
            is_cached = (info_resp['status'] == 'downloaded')
            return ("supported", is_cached)

        except Exception as e:
            return ("not_supported", None)

        finally:
            if torrent_id:
                try:
                    requests.delete(f"{base_url}/torrents/delete/{torrent_id}", headers=headers)
                except:
                    pass

    # --- NEW: MEGA FOLDER HANDLING ---
    elif "mega.nz/folder/" in url and "/file/" not in url:
        # We cannot check a folder directly. We must check one of the files inside.
        try:
            links = extract_mega_files_from_folder(url)
            if not links:
                return ("not_supported", None)
            
            # RECURSION: Check the first file link using this same function
            # The first link will be a file link, so it will fall into the 'else' block below.
            return check_real_debrid_cache(links[0])
            
        except Exception:
            return ("not_supported", None)

    # --- HOSTER LINK HANDLING ---
    else:
        try:
            resp = requests.post(
                f"{base_url}/unrestrict/link",
                data={"link": url},
                headers=headers
            )
            data = resp.json()
            if resp.status_code != 200:
                if isinstance(data, dict) and (data.get("error") == "hoster_unsupported" or data.get("error") == "hoster_unavailable"):
                    return ("not_supported", None)
                return ("supported", False)
            return ("supported", "download" in data)
        except Exception:
            return ("not_supported", None)


def check_alldebrid_cache(url):
    if not ALLDEBRID_API_TOKEN:
        return None

    try:
        # --- MAGNET CHECK ---
        if is_magnet(url):
            # 1. Upload
            r = requests.post(
                "https://api.alldebrid.com/v4.1/magnet/upload",
                data={
                    "apikey": ALLDEBRID_API_TOKEN,
                    "magnets[]": url,
                    "agent": "OneDL"
                },
                timeout=10
            )
            data = r.json()

            if data.get("status") != "success":
                return ("not_supported", None)

            magnets = data.get("data", {}).get("magnets", [])
            if not magnets:
                return ("unknown", None)

            magnet_id = magnets[0].get("id")

            # 2. Check Status
            r2 = requests.get(
                "https://api.alldebrid.com/v4.1/magnet/status",
                params={"apikey": ALLDEBRID_API_TOKEN, "id": magnet_id},
                timeout=10
            )
            status_json = r2.json()
            magnets_data = status_json.get("data", {}).get("magnets", {})
            status_code = magnets_data.get("statusCode")

            # 3. Cleanup
            try:
                requests.get(
                    "https://api.alldebrid.com/v4.1/magnet/delete",
                    params={"apikey": ALLDEBRID_API_TOKEN, "id": magnet_id},
                    timeout=10
                )
            except:
                pass

            # 4 = Ready (Cached)
            if status_code == 4:
                return ("supported", True)
            
            # 0-3 = Processing (Supported, can be queued)
            elif status_code in (0, 1, 2, 3):
                return ("supported", False)
            
            else:
                return ("not_supported", None)

        # --- NEW: MEGA FOLDER HANDLING ---
        elif "mega.nz/folder/" in url and "/file/" not in url:
            # AllDebrid cannot unlock a folder URL directly for cache checking.
            # We must extract the files and check the first one.
            try:
                links = extract_mega_files_from_folder(url)
                if not links:
                    return ("not_supported", None)
                
                # RECURSION: Check the first file link using this same function
                return check_alldebrid_cache(links[0])
            except Exception:
                return ("not_supported", None)

        # --- HOSTER URL CHECK ---
        else:
            r = requests.get(
                "https://api.alldebrid.com/v4.1/link/unlock",
                params={"apikey": ALLDEBRID_API_TOKEN, "link": url, "agent": "OneDL"},
                timeout=10
            )
            data = r.json()

            if data.get("status") == "success":
                return ("supported", True)

            return ("not_supported", None)

    except Exception:
        return ("unknown", None)


def check_premiumize_cache(url):
    if not PREMIUMIZE_API_TOKEN:
        return None

    try:
        if is_magnet(url):
            r = requests.get(
                "https://www.premiumize.me/api/cache/check",
                params={"items[]": url, "apikey": PREMIUMIZE_API_TOKEN}
            )
            data = r.json()
            response = data.get("response")
            if isinstance(response, list) and response:
                return ("supported", response[0] is True)
            return ("supported", False)

        else:            
            r = requests.post(
                "https://www.premiumize.me/api/transfer/directdl",
                data={"src": url, "apikey": PREMIUMIZE_API_TOKEN},
                timeout=10
            )
            data = r.json()

            if r.status_code == 200 and data.get("status") == "success":
                return ("supported", True)
            
            else:
                return ("not_supported", None)

    except Exception as e:
        print(f"Error checking Premiumize cache: {e}")
        return ("not_supported", None)


def extract_info_hash(magnet_link):
    match = re.search(r'btih:([a-fA-F0-9]+)', magnet_link)
    if match:
        return match.group(1).lower()
    return None


def check_torbox_cache(url):
    if not TORBOX_API_TOKEN:
        return None

    headers = {"Authorization": f"Bearer {TORBOX_API_TOKEN}"}

    try:
        # --- MAGNET HANDLING ---
        if is_magnet(url):
            info_hash = extract_info_hash(url)
            if not info_hash:
                return ("not_supported", None)

            resp = requests.post(
                "https://api.torbox.app/v1/api/torrents/checkcached",
                json={"hashes": [info_hash]},
                headers=headers,
                timeout=10
            )

            if resp.status_code == 200:
                data = resp.json()
                cached_data = data.get("data", {})
                
                if isinstance(cached_data, list):
                    is_cached = info_hash in cached_data
                else:
                    is_cached = cached_data.get(info_hash, False)

                return ("supported", is_cached)
            else:
                return ("not_supported", None)

        # --- WEB/HOSTER LINK HANDLING ---
        else:
            md5_hash = hashlib.md5(url.encode()).hexdigest()
            
            resp = requests.post(
                "https://api.torbox.app/v1/api/webdl/checkcached",
                json={"hashes": [md5_hash]},
                headers=headers,
                timeout=10
            )

            if resp.status_code == 200:
                data = resp.json()
                cached_data = data.get("data", {})
                
                if isinstance(cached_data, list):
                    is_cached = md5_hash in cached_data
                else:
                    is_cached = cached_data.get(md5_hash, False)

                if is_cached:
                    return ("supported", True)
                
                try:
                    hoster_resp = requests.get(
                        "https://api.torbox.app/v1/api/webdl/hosters",
                        headers=headers,
                        timeout=10
                    )
                    
                    if hoster_resp.status_code == 200:
                        hoster_data = hoster_resp.json()
                        hoster_list = hoster_data.get("data", [])
                        
                        # Parse user domain
                        parsed_url = urllib.parse.urlparse(url)
                        user_domain = parsed_url.netloc.lower()
                        if user_domain.startswith("www."):
                            user_domain = user_domain[4:]

                        # Iterate through the hoster objects to find a match
                        is_supported = False
                        
                        for hoster_obj in hoster_list:
                            # Extract the list of domains for this hoster
                            allowed_domains = hoster_obj.get("domains", [])
                            
                            # Check if the domain matches any of the allowed domains
                            for domain in allowed_domains:
                                if domain.lower() in user_domain:
                                    is_supported = True
                                    break
                            if is_supported:
                                break
                        
                        if is_supported:
                            return ("supported", False)
                        else:
                            return ("not_supported", None)
                    else:
                        return ("unknown", False) 

                except Exception:
                    return ("unknown", False)

            else:
                # API error on checkcached
                return ("not_supported", None)

    except Exception as e:
        print(f"Error checking TorBox cache: {e}")
        return ("not_supported", None)

def check_debrid_link_cache(url):
    if not DEBRID_LINK_API_TOKEN:
        return None

    headers = {"Authorization": f"Bearer {DEBRID_LINK_API_TOKEN}"}

    try:
        # --- MAGNET LINK CHECK ---
        if is_magnet(url):
            # 1. Add the magnet (this is the only way to know if it's cached now)
            add_resp = requests.post(
                "https://debrid-link.com/api/v2/seedbox/add",
                data={"url": url, "async": "false"}, # async=false attempts to give us info immediately
                headers=headers,
                timeout=15
            )
            add_data = add_resp.json()
            
            # If add failed, it's not supported
            if not add_data.get("success"):
                return ("not_supported", None)

            # 2. Check the status immediately
            torrent = add_data.get("value", {})
            torrent_id = torrent.get("id")
            progress = torrent.get("downloadPercent", 0)
            
            # If "downloadPercent" is missing in the add response, we might need a quick list check
            if "downloadPercent" not in torrent and torrent_id:
                 list_resp = requests.get("https://debrid-link.com/api/v2/seedbox/list", headers=headers)
                 if list_resp.status_code == 200:
                     torrents_list = list_resp.json().get("value", [])
                     # Handle pagination dict if present
                     if isinstance(torrents_list, dict): 
                         torrents_list = torrents_list.get("torrents", [])
                         
                     found_torrent = next((t for t in torrents_list if t["id"] == torrent_id), None)
                     if found_torrent:
                         progress = found_torrent.get("downloadPercent", 0)

            # 3. Determine Cache Status (100% means cached)
            is_cached = (progress == 100)

            # 4. Cleanup: Delete the check-torrent so we don't spam the user's list
            # We only delete if we are just checking. If the user actually selects it later, 
            # the main download function will add it again.
            if torrent_id:
                try:
                    requests.delete(
                        f"https://debrid-link.com/api/v2/seedbox/{torrent_id}/remove", 
                        headers=headers
                    )
                except:
                    pass

            return ("supported", is_cached)

        # --- HOSTER LINK CHECK ---
        else:
            # Same logic as before for hosters
            resp = requests.post(
                "https://debrid-link.com/api/v2/downloader/add",
                data={"url": url},
                headers=headers,
                timeout=15
            )
            data = resp.json()

            if data.get("success"):
                return ("supported", True)
            else:
                return ("not_supported", None)

    except Exception as e:
        print(f"Error checking Debrid-Link cache: {e}")
        return ("unknown", None)

def find_best_debrid(url: str = None) -> list[str]:
    if not url:
        url = input("Paste your magnet or hoster URL: ").strip()
    print("Checking availability across services...")
    services = []

    if REAL_DEBRID_API_TOKEN:
        status = check_real_debrid_cache(url)
        if status:
            support, cached = status
            services.append(("Real-Debrid", support, cached))

    if ALLDEBRID_API_TOKEN:
        status = check_alldebrid_cache(url)
        if status:
            support, cached = status
            services.append(("AllDebrid", support, cached))

    if PREMIUMIZE_API_TOKEN:
        status = check_premiumize_cache(url)
        if status:
            support, cached = status
            services.append(("Premiumize.me", support, cached))

    if TORBOX_API_TOKEN:
        status = check_torbox_cache(url)
        if status:
            support, cached = status
            services.append(("Torbox", support, cached))

    if DEBRID_LINK_API_TOKEN:
        status = check_debrid_link_cache(url)
        if status:
            support, cached = status
            services.append(("Debrid-Link", support, cached))        

    if not services:
        print("No debrid services available or none support this URL.")
        return []

    print()
    print(f"{CYAN}Available options:{RESET}")
    for idx, (name, support, cached) in enumerate(services, 1):
        if support == "not_supported":
            status_str = f"{RED}Not Supported{RESET}"
        elif support == "unknown":
            status_str = f"{YELLOW}Not Cached | Support unknown{RESET}"
        else:
            status_str = (
                f"{GREEN}Cached{RESET}"
                if cached else f"{YELLOW}Not Cached{RESET}"
            )
        print(f"{YELLOW}{idx}{RESET}. {name} ({status_str})")

    choice = input("Choose a service: ")
    if not choice.isdigit():
        return []
    idx = int(choice)
    if idx < 1 or idx > len(services):
        return []

    name = services[idx - 1][0]
    if name == "Real-Debrid":
        return get_real_debrid_links(url)
    elif name == "AllDebrid":
        return get_alldebrid_links(url)
    elif name == "Premiumize.me":
        return get_premiumize_links(url)
    elif name == "Torbox":
        return get_torbox_links(url)
    elif name == "Debrid-Link":
        return get_debrid_link_links(url)
    return []


def list_container_files():
    files = [
        f for f in os.listdir('.')
        if os.path.isfile(f) and (f.endswith('.torrent') or f.endswith('.nzb'))
    ]
    return files


def main():
    print_status_box()
    print()
    print(f"{CYAN}What do you want to do?{RESET}")
    print(f"{YELLOW}1{RESET}. Paste URL(s)")
    print(f"{YELLOW}2{RESET}. Load URLs from text file")
    if REAL_DEBRID_API_TOKEN or ALLDEBRID_API_TOKEN or PREMIUMIZE_API_TOKEN or TORBOX_API_TOKEN:
        print(f"{YELLOW}3{RESET}. Use Debrid Service")
    choice = input("Enter 1, 2 or 3: ").strip()

    if choice == '1':
        urls = get_urls_from_input()

    elif choice == '2':
        urls = get_urls_from_file()

    elif choice == '3':
        print()
        print(f"{CYAN}What do you want to do?{RESET}")
        print(f"{YELLOW}1{RESET}. Add Magnet or URL")
        if PREMIUMIZE_API_TOKEN or TORBOX_API_TOKEN:
            print(f"{YELLOW}2{RESET}. Upload Container File (.torrent or .nzb)")
        submode = input("Enter 1 or 2: ").strip()
        if submode not in ("1", "2"):
            print(f"{RED}Invalid choice.{RESET}")
            return

        if submode == "2":
            files = list_container_files()
            if not files:
                print(f"{RED}No .torrent or .nzb files found in this folder.{RESET}")
                return
            print()
            print(f"{CYAN}Select a container file to upload:{RESET}")
            for idx, f in enumerate(files, 1):
                print(f"{YELLOW}{idx}{RESET}: {f}")
            while True:
                file_choice = input("Enter the number of the file: ").strip()
                if file_choice.isdigit() and 1 <= int(file_choice) <= len(files):
                    container_file = files[int(file_choice) - 1]
                    break
                print(f"{RED}Invalid choice, try again.{RESET}")
            ext = os.path.splitext(container_file)[1].lower()
        else:
            container_file = None
            ext = None

        print()
        print(f"{CYAN}Which debrid service do you want to use?{RESET}")
        idx = 1
        options = []
        labels = []
        show_find_best = False

        if submode == "2":
            # Container file mode
            if ext == ".torrent":
                if REAL_DEBRID_API_TOKEN:
                    print(f"{YELLOW}{idx}{RESET}. Real-Debrid")
                    options.append(get_real_debrid_links)
                    labels.append("Real-Debrid")
                    idx += 1
                if ALLDEBRID_API_TOKEN:
                    print(f"{YELLOW}{idx}{RESET}. AllDebrid")
                    options.append(get_alldebrid_links)
                    labels.append("AllDebrid")
                    idx += 1
                if PREMIUMIZE_API_TOKEN:
                    print(f"{YELLOW}{idx}{RESET}. Premiumize.me")
                    options.append(get_premiumize_links)
                    labels.append("Premiumize.me")
                    idx += 1
                if TORBOX_API_TOKEN:
                    print(f"{YELLOW}{idx}{RESET}. Torbox")
                    options.append(get_torbox_links)
                    labels.append("Torbox")
                    idx += 1
                if DEBRID_LINK_API_TOKEN:
                    print(f"{YELLOW}{idx}{RESET}. Debrid-Link")
                    options.append(get_debrid_link_links)
                    labels.append("Debrid-Link")
                    idx += 1

                show_find_best = sum(bool(x) for x in [
                    REAL_DEBRID_API_TOKEN,
                    ALLDEBRID_API_TOKEN,
                    PREMIUMIZE_API_TOKEN,
                    TORBOX_API_TOKEN,
                    DEBRID_LINK_API_TOKEN
                ]) > 1

            elif ext == ".nzb":
                if PREMIUMIZE_API_TOKEN:
                    print(f"{YELLOW}{idx}{RESET}. Premiumize.me")
                    options.append(get_premiumize_links)
                    labels.append("Premiumize.me")
                    idx += 1
                if TORBOX_API_TOKEN:
                    print(f"{YELLOW}{idx}{RESET}. Torbox")
                    options.append(get_torbox_links)
                    labels.append("Torbox")
                    idx += 1
            else:
                print(f"{RED}Unsupported file type: {ext}{RESET}")
                return

        else:
            # Magnet/URL mode
            if REAL_DEBRID_API_TOKEN:
                print(f"{YELLOW}{idx}{RESET}. Real-Debrid")
                options.append(get_real_debrid_links)
                labels.append("Real-Debrid")
                idx += 1
            if ALLDEBRID_API_TOKEN:
                print(f"{YELLOW}{idx}{RESET}. AllDebrid")
                options.append(get_alldebrid_links)
                labels.append("AllDebrid")
                idx += 1
            if PREMIUMIZE_API_TOKEN:
                print(f"{YELLOW}{idx}{RESET}. Premiumize.me")
                options.append(get_premiumize_links)
                labels.append("Premiumize.me")
                idx += 1
            if TORBOX_API_TOKEN:
                print(f"{YELLOW}{idx}{RESET}. Torbox")
                options.append(get_torbox_links)
                labels.append("Torbox")
                idx += 1
            if DEBRID_LINK_API_TOKEN:
                print(f"{YELLOW}{idx}{RESET}. Debrid-Link")
                options.append(get_debrid_link_links)
                labels.append("Debrid-Link")
                idx += 1

            show_find_best = sum(bool(x) for x in [
                REAL_DEBRID_API_TOKEN,
                ALLDEBRID_API_TOKEN,
                PREMIUMIZE_API_TOKEN,
                TORBOX_API_TOKEN,
                DEBRID_LINK_API_TOKEN
            ]) > 1

        if show_find_best:
            print(f"{YELLOW}{idx}{RESET}. Find best option")
            options.append(find_best_debrid)
            labels.append("Find best option")

        if not options:
            print(f"{RED}No debrid services configured for this file type.{RESET}")
            return

        sub_choice = input("Enter your choice: ").strip()
        if not sub_choice.isdigit():
            print(f"{RED}Invalid choice.{RESET}")
            return
        sub_choice = int(sub_choice)

        if 1 <= sub_choice <= len(options):
            print()
            if submode == "2":
                if ext == ".torrent":
                    print(f"{CYAN}Using container file: {container_file}{RESET}")
                    magnet_url = torrent_to_magnet(container_file)
                    urls = options[sub_choice - 1](magnet_url)
                elif ext == ".nzb":
                    if options[sub_choice - 1] == get_torbox_links:
                        print(f"{CYAN}Using NZB file: {container_file}{RESET}")
                        urls = get_torbox_links_from_nzb(container_file)
                    elif options[sub_choice - 1] == get_premiumize_links:
                        print(f"{CYAN}Using NZB file: {container_file}{RESET}")
                        urls = get_premiumize_links_from_nzb(container_file)
                else:
                    print(f"{RED}Unsupported file type.{RESET}")
                    return
            else:
                url = input("Paste your magnet or hoster URL: ").strip()
                urls = options[sub_choice - 1](url)
        else:
            print(f"{RED}Invalid choice.{RESET}")
            return

    else:
        print(f"{RED}Invalid choice.{RESET}")
        return

    # Download phase
    total = len(urls)
    for idx, url in enumerate(urls, 1):
        print(f"\n{CYAN}Download {idx} of {total}:{RESET}")
        download_file(url)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n{RED}Aborted by user (Ctrl+C).{RESET}")
        sys.exit(1)
