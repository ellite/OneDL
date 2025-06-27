#!/usr/bin/env python3

"""
OneDL - Universal Debrid & Downloader Tool

OneDL is a command-line tool to simplify downloading from hosters, torrents, cloud debrid services, and direct HTTP(S) links.
It supports Real-Debrid, AllDebrid, and Premiumize.me, allowing you to resolve direct links from magnets,
hoster URLs, MEGA folders, or standard HTTP(S) links, and download them.

USAGE:
    1. Run the script from the folder where you want your downloaded files: onedl
    2. Choose to load URLs from a file, paste them manually, or use a debrid service.
    3. For debrid services, select Real-Debrid, AllDebrid, Premiumize.me, or let OneDL find the best option.
    4. Paste your magnet, hoster, MEGA, or HTTP(S) URL when prompted.
    5. Select files if needed, and OneDL will resolve and download them for you.

FEATURES:
    - Supports magnet links, hoster URLs, MEGA folders, and direct HTTP(S) links.
    - Integrates with Real-Debrid, AllDebrid, and Premiumize.me.
    - Shows download progress bars with speed and seeders.
    - Lets you pick files from torrents or containers.
    - Colorful, user-friendly terminal output.

Configure your API tokens at the top of this script for each service you want to use.
"""

import os
import sys
import urllib.parse
import urllib.request
import time
import requests
import json
import re

VERSION = "1.0.1"

REAL_DEBRID_API_TOKEN = ""
ALLDEBRID_API_TOKEN = ""
PREMIUMIZE_API_TOKEN = ""

CYAN = "\033[96m"
YELLOW = "\033[93m"
GREEN = "\033[92m"
RED = "\033[91m"
RESET = "\033[0m"

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
                    urls = [line.strip() for line in file if line.strip()]
                return urls
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

def show_progress_factory():
    start_time = [time.time()]
    last_downloaded = [0]

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
            print()  # Newline after completion

    return show_progress

def download_file(url):
    try:
        # Follow redirects to get the real file and filename
        with requests.get(url, stream=True, allow_redirects=True) as r:
            r.raise_for_status()
            # Try to get filename from Content-Disposition
            cd = r.headers.get('content-disposition')
            if cd:
                fname = re.findall('filename="(.+)"', cd)
                filename = fname[0] if fname else url.split("/")[-1]
            else:
                # Fallback: use last part of final URL
                filename = r.url.split("/")[-1]
                
            filename = urllib.parse.unquote(filename)    
            print(f"Downloading: {YELLOW}{filename}{RESET}")
            show_progress = show_progress_factory()
            with open(filename, "wb") as f:
                downloaded = 0
                block_size = 8192
                total_size = int(r.headers.get('content-length', 0))
                for block_num, chunk in enumerate(r.iter_content(block_size), 1):
                    if chunk:
                        f.write(chunk)
                        show_progress(block_num, block_size, total_size)
            print(f"{GREEN}Saved as:{RESET} {YELLOW}{filename}{RESET}")
    except Exception as e:
        print(f"{RED}Failed to download:{RESET} {YELLOW}{url}{RESET} {RED}- {e}{RESET}")

def is_magnet(url):
    return url.strip().startswith("magnet:")

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
            info = requests.get(f"https://api.real-debrid.com/rest/1.0/torrents/info/{torrent_id}", headers=headers).json()
            if info["status"] in ("waiting_files", "waiting_files_selection"):
                if not selection_sent:
                    files = info["files"]
                    print()
                    print(f"{CYAN}Select files in torrent:{RESET}")
                    for idx, f in enumerate(files, 1):
                        path = f['path'].lstrip("/\\")
                        print(f"{YELLOW}{idx}{RESET}: {path} {CYAN}({f['bytes']//1024//1024} MB){RESET}")
                    selection = input(f"Enter numbers separated by commas, or 'all' (default all): ")
                    if selection.strip().lower() == "all" or not selection.strip():
                        file_ids = [str(f["id"]) for f in files]
                    else:
                        file_ids = [str(files[int(i)-1]["id"]) for i in selection.split(",") if i.strip().isdigit()]
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
                        f"\r{YELLOW}Downloading to cloud...{RESET} [{bar_colored}] {percent_str} | Speed: {CYAN}{speed_str}{RESET} | Seeders: {GREEN}{seeders}{RESET}   "
                    )
                    sys.stdout.flush()
                else:
                    print(f"{YELLOW}Waiting for Real-Debrid... Status: {info['status']}{RESET}")
                time.sleep(3)
                if info["status"] != "downloading":
                    print()  # Print newline after progress bar when done
                time.sleep(3)
    elif "mega.nz/folder/" in url:
        # Extract file links from folder
        file_links = extract_mega_file_links_with_premiumize(url)
        if not file_links:
            print(f"{RED}Could not extract MEGA file links from folder.{RESET}")
            return []
        unlocked = []
        for f in file_links:
            resp = requests.post(
                "https://api.real-debrid.com/rest/1.0/unrestrict/link",
                data={"link": f},
                headers=headers
            )
            data = resp.json()
            if "download" in data:
                print(f"{GREEN}Unlocked:{RESET} {YELLOW}{f}{RESET} {CYAN}→{RESET} {GREEN}{data['download']}{RESET}")
                unlocked.append(data["download"])
            else:
                print(f"{RED}Could not unlock:{RESET} {YELLOW}{f}{RESET}")
        return unlocked
    else:
        # Hoster logic as before
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

def get_alldebrid_links(url=None):
    token = ALLDEBRID_API_TOKEN or input(f"{CYAN}Enter your AllDebrid API token:{RESET} ").strip()
    if not url:
        url = input(f"{CYAN}Paste your magnet or hoster URL:{RESET} ").strip()

    if is_magnet(url):
        # Magnet logic
        resp = requests.post(
            "https://api.alldebrid.com/v4/magnet/upload",
            params={"agent": "dl-script", "apikey": token, "magnets[]": url}
        )
        try:
            data = resp.json()
        except Exception as e:
            # Handle concatenated JSON objects and print error/message if present
            text = resp.text
            parts = []
            if '}{' in text:
                # Split at every '}{' and add braces back
                split = text.split('}{')
                for i, part in enumerate(split):
                    if i == 0:
                        parts.append(part + '}')
                    elif i == len(split) - 1:
                        parts.append('{' + part)
                    else:
                        parts.append('{' + part + '}')
            else:
                parts = [text]
            for part in parts:
                try:
                    obj = json.loads(part)
                    if "error" in obj or "message" in obj:
                        print(f"{RED}AllDebrid error:{RESET} {obj.get('error','')}")
                        print(f"{YELLOW}{obj.get('message','')}{RESET}")
                except Exception:
                    continue
            return []
        if data.get("status") != "success":
            print(f"{RED}Failed to add magnet.{RESET}")
            return []
        magnet_id = data["data"]["magnets"][0]["id"]

        # Wait for magnet to be ready
        selection_sent = False
        while True:
            info = requests.get(
                "https://api.alldebrid.com/v4/magnet/status",
                params={"agent": "dl-script", "apikey": token, "id": magnet_id}
            ).json()
            if info.get("status") == "success":
                magnet = info["data"]["magnets"]
                if not isinstance(magnet, dict):
                    print(f"{RED}Unexpected magnet response.{RESET}")
                    print(json.dumps(magnet, indent=2))
                    return []

                if magnet["status"] == "waiting_files":
                    if not selection_sent:
                        files = magnet["files"]
                        print()
                        print(f"{CYAN}Files in torrent:{RESET}")
                        for idx, f in enumerate(files, 1):
                            path = f['path'].lstrip("/\\")
                            print(f"{YELLOW}{idx}{RESET}: {path} {CYAN}({f['size']//1024//1024} MB){RESET}")
                        selection = input(f"{CYAN}Enter file numbers to download (comma separated, or 'all'):{RESET} ")
                        if selection.strip().lower() == "all" or not selection.strip():
                            file_ids = [str(f["id"]) for f in files]
                        else:
                            file_ids = [str(files[int(i)-1]["id"]) for i in selection.split(",") if i.strip().isdigit()]
                        requests.post(
                            "https://api.alldebrid.com/v4/magnet/selectFiles",
                            params={"agent": "dl-script", "apikey": token, "id": magnet_id, "files": ",".join(file_ids)}
                        )
                        print(f"{GREEN}Selection sent, waiting for AllDebrid to process...{RESET}")
                        selection_sent = True
                    else:
                        print(f"{YELLOW}Waiting for AllDebrid to process your selection...{RESET}")
                    time.sleep(3)

                elif magnet["status"].lower() == "ready":
                    raw_links = [l["link"] for l in magnet.get("links", []) if "link" in l]
                    if not raw_links:
                        print(f"{RED}No links returned from AllDebrid.{RESET}")
                        return []

                    # Unlock all links to get real download URLs
                    final_links = []
                    for l in raw_links:
                        r = requests.get(
                            "https://api.alldebrid.com/v4/link/unlock",
                            params={"agent": "dl-script", "apikey": token, "link": l}
                        ).json()
                        if r.get("status") == "success" and "link" in r.get("data", {}):
                            final_links.append(r["data"]["link"])
                        else:
                            print(f"{RED}Failed to unlock link:{RESET} {YELLOW}{l}{RESET}")

                    print(f"{GREEN}Resolved direct links:{RESET}")
                    for i, link in enumerate(final_links, 1):
                        print(f"{YELLOW}{i}{RESET}: {link}")
                    choice = input(f"{CYAN}Enter numbers separated by commas, or 'all' (default all):{RESET} ")
                    if not choice.strip() or choice.strip().lower() == "all":
                        selected = final_links
                    else:
                        ids = set(int(x) for x in choice.split(",") if x.strip().isdigit())
                        selected = [link for idx, link in enumerate(final_links, 1) if idx in ids]
                    return selected

                elif magnet["status"] == "error":
                    print(f"{RED}Magnet error.{RESET}")
                    return []
                elif magnet["status"] == "Downloading":
                    downloaded = magnet.get("downloaded", 0)
                    size = magnet.get("size", 0)
                    if size:
                        percent = min(100, int(downloaded * 100 // size))
                    else:
                        percent = 0
                    seeders = magnet.get("seeders", 0)
                    bar_length = 30
                    num_hashes = int(percent * bar_length // 100)
                    bar = '#' * num_hashes
                    bar = bar.ljust(bar_length)
                    bar_colored = f"{YELLOW}{bar}{RESET}"
                    percent_str = f"{GREEN}{percent}%{RESET}"
                    speed = magnet.get("downloadSpeed", 0)
                    if speed >= 1024 * 1024:
                        speed_str = f"{speed/1024/1024:.2f} MB/s"
                    elif speed >= 1024:
                        speed_str = f"{speed/1024:.1f} KB/s"
                    else:
                        speed_str = f"{speed:.0f} B/s"
                    sys.stdout.write(
                        f"\r{YELLOW}Downloading to cloud...{RESET} [{bar_colored}] {percent_str} | Speed: {CYAN}{speed_str}{RESET} | Seeders: {GREEN}{seeders}{RESET}   "
                    )
                    sys.stdout.flush()
                    time.sleep(3)
            else:
                print(f"{YELLOW}Waiting for AllDebrid...{RESET}")
                time.sleep(3)
    elif "mega.nz/folder/" in url and PREMIUMIZE_API_TOKEN:
        # Extract file links from folder using Premiumize
        file_links = extract_mega_file_links_with_premiumize(url)
        if not file_links:
            print(f"{RED}Could not extract MEGA file links from folder.{RESET}")
            return []
        unlocked = []
        for f in file_links:
            resp = requests.get(
                "https://api.alldebrid.com/v4/link/unlock",
                params={"agent": "dl-script", "apikey": token, "link": f}
            )
            data = resp.json()
            if data.get("status") == "success" and "link" in data.get("data", {}):
                print(f"{GREEN}Unlocked:{RESET} {YELLOW}{f}{RESET} {CYAN}→{RESET} {GREEN}{data['data']['link']}{RESET}")
                unlocked.append(data["data"]["link"])
            else:
                print(f"{RED}Could not unlock:{RESET} {YELLOW}{f}{RESET}")
        return unlocked
    else:
        # Hoster logic
        resp = requests.get(
            "https://api.alldebrid.com/v4/link/unlock",
            params={"agent": "dl-script", "apikey": token, "link": url}
        )
        data = resp.json()
        if data.get("status") == "success" and "link" in data.get("data", {}):
            print(f"{GREEN}Resolved direct link:{RESET}")
            print(f"{YELLOW}{data['data']['link']}{RESET}")
            return [data["data"]["link"]]
        print(f"{RED}Hoster not supported or failed.{RESET}")

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

        # Fetch *all* files with links
        files = get_all_files_with_links(token, folder_id)
        if not files:
            print(f"{RED}No downloadable files found.{RESET}")
            return []

        # Show and let user select (or 'all')
        print(f"{CYAN}Files ready to download:{RESET}")
        for i, f in enumerate(files, 1):
            mb = f["size"] // (1024*1024)
            print(f"{YELLOW}{i}{RESET}: {f['name']} {CYAN}({mb} MB){RESET}")
        choice = input(f"{CYAN}Enter numbers separated by commas, or 'all':{RESET} ")
        if not choice.strip() or choice.strip().lower() == "all":
            selected = files
        else:
            ids = set(int(x) for x in choice.split(",") if x.strip().isdigit())
            selected = [f for idx, f in enumerate(files, 1) if idx in ids]
        return [f["link"] for f in selected]
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
                for idx, f in enumerate(files, 1):
                    print(f"{YELLOW}{idx}{RESET}: {f}")
                choice = input(f"{CYAN}Enter numbers separated by commas, or 'all' (default all):{RESET} ")
                if not choice.strip() or choice.strip().lower() == "all":
                    selected = files
                else:
                    ids = set(int(x) for x in choice.split(",") if x.strip().isdigit())
                    selected = [f for idx, f in enumerate(files, 1) if idx in ids]
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
    if is_magnet(url):
        info = requests.get("https://api.real-debrid.com/rest/1.0/torrents/instantAvailability/" + urllib.parse.quote(url), headers=headers).json()
        return bool(info and any(info.values()))
    else:
        resp = requests.post("https://api.real-debrid.com/rest/1.0/unrestrict/link", data={"link": url}, headers=headers)
        return resp.status_code == 200 and "download" in resp.json()

def check_alldebrid_cache(url):
    if not ALLDEBRID_API_TOKEN:
        return None
    if is_magnet(url):
        r = requests.get("https://api.alldebrid.com/v4/magnet/instant", params={"apikey": ALLDEBRID_API_TOKEN, "magnets[]": url})
        data = r.json()
        return data.get("status") == "success" and data.get("data", {}).get("instant")
    else:
        r = requests.get("https://api.alldebrid.com/v4/link/unlock", params={"apikey": ALLDEBRID_API_TOKEN, "link": url})
        return r.status_code == 200 and r.json().get("status") == "success"

def check_premiumize_cache(url):
    if not PREMIUMIZE_API_TOKEN:
        return None
    if is_magnet(url):
        r = requests.get("https://www.premiumize.me/api/cache/check", params={"items[]": url, "apikey": PREMIUMIZE_API_TOKEN})
        if r.status_code == 200:
            data = r.json()
            response = data.get("response")
            if isinstance(response, list) and response:
                return response[0] is True
        return False
    else:
        r = requests.get("https://www.premiumize.me/api/transfer/directdl", params={"apikey": PREMIUMIZE_API_TOKEN, "src": url})
        return r.status_code == 200 and r.json().get("status") == "success"

def find_best_debrid():
    url = input("Paste your magnet or hoster URL: ").strip()
    print("Checking availability across services...")
    services = []
    if REAL_DEBRID_API_TOKEN:
        cached = check_real_debrid_cache(url)
        if cached is not None:
            services.append(("Real-Debrid", cached))
    if ALLDEBRID_API_TOKEN:
        cached = check_alldebrid_cache(url)
        if cached is not None:
            services.append(("AllDebrid", cached))
    if PREMIUMIZE_API_TOKEN:
        cached = check_premiumize_cache(url)
        if cached is not None:
            services.append(("Premiumize.me", cached))

    if not services:
        print("No debrid services available or none support this URL.")
        return []

    print()
    print(f"{CYAN}Available options:{RESET}")
    for idx, (name, cached) in enumerate(services, 1):
        status = f"{GREEN}Cached{RESET}" if cached else f"{RED}Not Cached{RESET}"
        print(f"{YELLOW}{idx}{RESET}. {name} ({status})")

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
    return []

def main():
    print(f"{CYAN}OneDL v{VERSION}{RESET}")
    print()
    print(f"{CYAN}Do you want to:{RESET}")
    print(f"{YELLOW}1{RESET}. Load URLs from a file")
    print(f"{YELLOW}2{RESET}. Paste URLs manually")
    print(f"{YELLOW}3{RESET}. Use Debrid Service")
    choice = input("Enter 1, 2 or 3: ").strip()

    if choice == '1':
        urls = get_urls_from_file()
    elif choice == '2':
        urls = get_urls_from_input()
    elif choice == '3':
        print()
        print(f"{CYAN}Which debrid service do you want to use?{RESET}")
        idx = 1
        options = []
        labels = []
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
        if PREMIUMIZE_API_TOKEN or REAL_DEBRID_API_TOKEN or ALLDEBRID_API_TOKEN:    
            print(f"{YELLOW}{idx}{RESET}. Find best option")
            options.append(find_best_debrid)
            labels.append("Find best option")
        else:
            print(f"{RED}No debrid services configured.{RESET}")
            return

        sub_choice = input("Enter your choice: ").strip()
        if not sub_choice.isdigit():
            print(f"{RED}Invalid choice.{RESET}")
            return
        sub_choice = int(sub_choice)
        if 1 <= sub_choice < idx:
            print()
            url = input("Paste your magnet or hoster URL: ").strip()
            urls = options[sub_choice - 1](url)
        elif sub_choice == idx:
            urls = options[sub_choice - 1]()
        else:
            print(f"{RED}Invalid choice.{RESET}")
            return
    else:
        print(f"{RED}Invalid choice.{RESET}")
        return

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

