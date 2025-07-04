#!/usr/bin/env python3

"""
OneDL - Universal Debrid & Downloader Tool

OneDL is a command-line tool to simplify downloading from hosters, torrents, cloud debrid services, direct HTTP(S) links, and container files (.torrent & .nzb).
It supports Real-Debrid, AllDebrid, Premiumize.me, and Torbox, allowing you to resolve direct links from magnets,
hoster URLs, MEGA folders, standard HTTP(S) links, or by uploading .torrent and .nzb files, and download them.

USAGE:
    1. Run the script from the folder where you want your downloaded files: onedl
    2. Choose to load URLs from a file, paste them manually, or use a debrid service.
    3. For debrid services, select Real-Debrid, AllDebrid, Premiumize.me, Torbox or let OneDL find the best option.
    4. Paste your magnet, hoster, MEGA, HTTP(S) URL, or upload a .torrent/.nzb file when prompted.
    5. Select files if needed, and OneDL will resolve and download them for you.

FEATURES:
    - Supports magnet links, hoster URLs, MEGA folders, direct HTTP(S) links, and container files (.torrent & .nzb).
    - Integrates with Real-Debrid, AllDebrid, Premiumize.me and Torbox.
    - Shows download progress bars with speed and seeders.
    - Lets you pick files from torrents, NZBs, or containers.
    - Colorful, user-friendly terminal output.

Configure your API tokens at the top of this script for each service you want to use.
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

VERSION = "1.5.1"

REAL_DEBRID_API_TOKEN = ""
ALLDEBRID_API_TOKEN = ""
PREMIUMIZE_API_TOKEN = ""
TORBOX_API_TOKEN = ""

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

def download_file(url, filename=None):
    try:
        # Follow redirects to get the real file and filename
        with requests.get(url, stream=True, allow_redirects=True) as r:
            r.raise_for_status()
            # Only override filename if not given
            if filename is None:
                # Try to get filename from Content-Disposition
                cd = r.headers.get('content-disposition')
                if cd:
                    fname = re.findall('filename="(.+)"', cd)
                    filename = fname[0] if fname else url.split("/")[-1]
                else:
                    # Fallback: use last part of final URL
                    filename = r.url.split("/")[-1]
            else:
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
            info = requests.get(f"https://api.real-debrid.com/rest/1.0/torrents/info/{torrent_id}", headers=headers).json()
            if info["status"] in ("waiting_files", "waiting_files_selection"):
                if not selection_sent:
                    files = info["files"]
                    print()
                    print(f"{CYAN}Select files in torrent:{RESET}")
                    for idx, f in enumerate(files, 1):
                        path = f['path'].lstrip("/\\")
                        print(f"{YELLOW}{idx}{RESET}: {path} {CYAN}({f['bytes']//1024//1024} MB){RESET}")

                    selection = input(f"Enter numbers (e.g., 1,2,5-10) or 'all' (default all): ").strip().lower()
                    if selection == "all" or not selection:
                        file_ids = [str(f["id"]) for f in files]
                    else:
                        selected_indices = parse_selection(selection, len(files))
                        file_ids = [str(files[i - 1]["id"]) for i in selected_indices]

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
                unlocked.append({"name": filename, "url": data["download"]})
            else:
                print(f"{RED}Could not unlock:{RESET} {YELLOW}{f}{RESET}")

        if not unlocked:
            print(f"{RED}No files were unlocked.{RESET}")
            return []

        # Prompt user for selection
        print(f"{CYAN}Select files to download:{RESET}")
        for idx, f in enumerate(unlocked, 1):
            print(f"{YELLOW}{idx}{RESET}: {f['name']}")

        selection = input(f"Enter numbers separated by commas or ranges (e.g., 1,3-5), or press Enter for all: ").strip()
        if not selection or selection.lower() == "all":
            return [f["url"] for f in unlocked]

        selected_indices = parse_selection(selection, len(unlocked))
        return [unlocked[i - 1]["url"] for i in selected_indices]

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
            resp = requests.get(
                "https://api.alldebrid.com/v4/link/unlock",
                params={"agent": "dl-script", "apikey": token, "link": f}
            )
            data = resp.json()
            if data.get("status") == "success" and "link" in data.get("data", {}):
                filename = data["data"].get("filename") or urllib.parse.unquote(f.split("/")[-1])
                unlocked.append({"name": filename, "url": data["data"]["link"]})
            else:
                print(f"{RED}Could not unlock:{RESET} {YELLOW}{f}{RESET}")

        if not unlocked:
            print(f"{RED}No files were unlocked.{RESET}")
            return []

        # Prompt user to select which files to download
        print(f"{CYAN}Select files to download:{RESET}")
        for idx, f in enumerate(unlocked, 1):
            print(f"{YELLOW}{idx}{RESET}: {f['name']}")

        selection = input(f"Enter numbers separated by commas or ranges (e.g., 1,3-5), or press Enter for all: ").strip()
        if not selection or selection.lower() == "all":
            return [f["url"] for f in unlocked]

        selected_indices = parse_selection(selection, len(unlocked))
        return [unlocked[i - 1]["url"] for i in selected_indices]

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
    
def get_torbox_links(url=None):
    token = TORBOX_API_TOKEN or input(f"{CYAN}Enter your Torbox API token:{RESET} ").strip()
    if not url:
        url = input(f"{CYAN}Paste your magnet or hoster URL:{RESET} ").strip()

    headers = {"Authorization": f"Bearer {token}"}

    if is_magnet(url):
        # 1️⃣ Create the torrent with multipart/form-data
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
        print()
        print(f"{GREEN}Torrent queued—ID {torrent_id}. Getting file list...{RESET}")

        # 2️⃣ Get correct file list using /mylist endpoint (has real file IDs)
        mylist_resp = requests.get(
            "https://api.torbox.app/v1/api/torrents/mylist",
            params={"token": TORBOX_API_TOKEN, "id": torrent_id},
            headers=headers,
            timeout=15,
        )

        mylist_data = mylist_resp.json()
        if not mylist_data.get("success") or not mylist_data.get("data"):
            print(f"{RED}Failed to fetch file list from /mylist: {mylist_data.get('error')}{RESET}")
            return []

        files = mylist_data["data"].get("files", [])
        if not files:
            print(f"{RED}No files found in torrent metadata.{RESET}")
            return []

        print(f"{GREEN}Found {len(files)} files. Checking which are ready...{RESET}")

        # 3️⃣ File size formatting helper
        def sizeof_fmt(num, suffix="B"):
            for unit in ["", "K", "M", "G", "T"]:
                if abs(num) < 1024:
                    return f"{num:.0f} {unit}{suffix}"
                num /= 1024
            return f"{num:.0f} P{suffix}"

        # 4️⃣ Display list to user (1-based)
        print("Select files to download:")
        for i, f in enumerate(files, 1):
            print(f"{YELLOW}{i}{RESET}: {f['short_name']} {CYAN}({sizeof_fmt(f['size'])}){RESET}")

        selection = input("Enter file numbers separated by commas, or 'all' [default=all]: ").strip()

        if not selection or selection.lower() == "all":
            selected_indexes = set(range(len(files)))
        else:
            try:
                selected_indexes = set(
                    int(i.strip()) - 1
                    for i in selection.split(",")
                    if i.strip().isdigit() and 0 < int(i.strip()) <= len(files)
                )
            except Exception as e:
                print(f"{RED}Invalid selection: {e}{RESET}")
                return []

        # 5️⃣ Request download links using real file IDs
        links = []

        for idx in selected_indexes:
            f = files[idx]
            file_id = f["id"]  # ✅ use API-supplied file ID
            print(f"{YELLOW}Waiting for file {CYAN}{idx + 1}{RESET}: {f['name']}{RESET}")

            while True:
                r = requests.get(
                    "https://api.torbox.app/v1/api/torrents/requestdl",
                    params={
                        "token": TORBOX_API_TOKEN,
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
                elif "not ready" in resp_data.get("error", "").lower():
                    print(f"{YELLOW}File {idx + 1} not ready. Retrying...{RESET}")
                    time.sleep(5)
                else:
                    print(f"{RED}Unexpected error for file {idx + 1}: {resp_data}{RESET}")
                    break

        if links:
            print(f"{GREEN}Resolved direct links:{RESET}")
            for l in links:
                print(f"{YELLOW}{l}{RESET}")
        else:
            print(f"{RED}No files could be downloaded at this time.{RESET}")

        return links
    
    else:
        # Hoster logic
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

        print(f"{GREEN}Found cached web download. Creating job to retrieve file list...{RESET}" if is_cached else f"{YELLOW}Not cached. Creating new job...{RESET}")

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

        # Get full file list
        # First status check
        mylist_resp = requests.get(
            "https://api.torbox.app/v1/api/webdl/mylist",
            params={"token": TORBOX_API_TOKEN, "id": web_id},
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

                # These states mean "not ready yet"
        pending_states = {"downloading", "processing", "waiting"}
        last_state = state

        if state in pending_states and not files:
            print(f"{CYAN}Waiting for cloud download to finish...{RESET}")

            while state in pending_states:
                bar_len = 30
                bar = "#" * int(progress * bar_len)
                bar = bar.ljust(bar_len)
                percent = int(progress * 100)
                speed_mb = f"{speed / (1024 * 1024):.2f} MB/s" if speed else "–"

                sys.stdout.write(
                    f"\r{YELLOW}Downloading to cloud...{RESET} [{bar}] {GREEN}{percent}%{RESET} :: {CYAN}{speed_mb}{RESET}   "
                )
                sys.stdout.flush()

                time.sleep(5)

                # Re-check status
                mylist_resp = requests.get(
                    "https://api.torbox.app/v1/api/webdl/mylist",
                    params={"token": TORBOX_API_TOKEN, "id": web_id},
                    headers=headers,
                    timeout=30
                )
                mylist_data = mylist_resp.json()
                data = mylist_data.get("data", {})
                state = data.get("download_state")
                progress = data.get("progress", 0.0)
                speed = data.get("download_speed", 0)

            print()  # Newline after progress bar

            if state != "completed":
                print(f"{RED}Download failed or is still not ready. Final state: {state}{RESET}")
                return []

            files = data.get("files", [])


        # Final check for file list
        if not files:
            print(f"{RED}No downloadable files listed.{RESET}")
            return []


        print(f"{GREEN}Found {len(files)} file(s).{RESET}")
        for idx, f in enumerate(files, 1):
            name = f.get("short_name", "Unknown")
            size = f.get("size", 0)
            mb = size // (1024 * 1024)
            print(f"{YELLOW}{idx}{RESET}: {name} {CYAN}({mb} MB){RESET}")

        choice = input(f"{CYAN}Enter file numbers separated by commas or ranges (e.g., 1,3-5), or 'all' [default=all]:{RESET} ").strip()

        if not choice or choice.lower() == "all":
            selected_indexes = set(range(len(files)))
        else:
            selected_indexes = set()
            for part in choice.split(","):
                part = part.strip()
                if '-' in part:
                    try:
                        start, end = map(int, part.split('-'))
                        selected_indexes.update(range(start - 1, end))
                    except Exception:
                        continue
                elif part.isdigit():
                    i = int(part)
                    if 1 <= i <= len(files):
                        selected_indexes.add(i - 1)

        print(f"{GREEN}Requesting download links...{RESET}")
        urls = []
        for idx in sorted(selected_indexes):
            f = files[idx]
            fid = f.get("id")
            name = f.get("short_name", "Unknown")

            dl_resp = requests.get(
                "https://api.torbox.app/v1/api/webdl/requestdl",
                params={"token": TORBOX_API_TOKEN, "web_id": web_id, "file_id": fid},
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

            print(f"{GREEN}Found {len(content)} file(s).{RESET}")
            for idx, f in enumerate(content, 1):
                name = f.get("path", "Unknown")
                size = f.get("size", 0)
                mb = size // (1024 * 1024)
                print(f"{YELLOW}{idx}{RESET}: {name} {CYAN}({mb} MB){RESET}")

            choice = input(f"{CYAN}Enter file numbers separated by commas or ranges (e.g. 1,3-5), or 'all' (default all):{RESET} ").strip()
            if not choice or choice.lower() == "all":
                selected_indexes = list(range(len(content)))
            else:
                selected_indexes = parse_selection(choice, len(content))
                if not selected_indexes:
                    print(f"{RED}No valid file indexes selected.{RESET}")
                    return []

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

            print(f"{GREEN}Found {len(files)} file(s).{RESET}")
            for idx, f in enumerate(files, 1):
                name = f.get("name", "Unknown")
                size = f.get("size", 0)
                mb = size // (1024 * 1024)
                print(f"{YELLOW}{idx}{RESET}: {name} {CYAN}({mb} MB){RESET}")

            choice = input(f"{CYAN}Enter file numbers separated by commas or ranges (e.g. 1,3-5), or 'all' (default all):{RESET} ").strip()
            if not choice or choice.lower() == "all":
                selected_indexes = list(range(len(files)))
            else:
                selected_indexes = parse_selection(choice, len(files))
                if not selected_indexes:
                    print(f"{RED}No valid file indexes selected.{RESET}")
                    return []

            return [files[i]["link"] for i in selected_indexes]


    except Exception as e:
        print(f"{RED}Exception during Premiumize NZB processing: {e}{RESET}")
        return []


def get_torbox_links_from_nzb(nzb_path: str) -> list[str]:
    print(f"{CYAN}Uploading NZB to Torbox...{RESET}")

    headers = {"Authorization": f"Bearer {TORBOX_API_TOKEN}"}

    try:
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
            print(f"{RED}Upload succeeded but no ID returned.{RESET}")
            return []

        # Now query mylist to get all file entries
        print(f"{CYAN}Getting download info for Usenet ID {usenet_id}...{RESET}")

        # Retry fetching file list up to 5 times with a delay
        max_retries = 10
        for attempt in range(1, max_retries + 1):
            mylist_resp = requests.get(
                "https://api.torbox.app/v1/api/usenet/mylist",
                params={"token": TORBOX_API_TOKEN, "id": usenet_id},
                headers=headers,
                timeout=30
            )

            if mylist_resp.status_code == 200 and mylist_resp.json().get("success"):
                mylist_data = mylist_resp.json().get("data", {})
                files = mylist_data.get("files", [])
                if files:
                    break
                else:
                    print(f"{YELLOW}No files found yet, retrying ({attempt}/{max_retries})...{RESET}")
            else:
                print(f"{RED}Failed to query mylist for NZB (attempt {attempt}/{max_retries}).{RESET}")

            time.sleep(3)
        else:
            print(f"{RED}No files found in mylist response after {max_retries} attempts.{RESET}")
            return []

        print(f"{GREEN}Found {len(files)} file(s).{RESET}")
        for idx, f in enumerate(files, 1):
            name = f.get("name", "Unknown")
            size = f.get("size", 0)
            mb = size // (1024 * 1024)
            print(f"{YELLOW}{idx}{RESET}: {name} {CYAN}({mb} MB){RESET}")

        # Prompt user for selection
        choice = input(f"{CYAN}Enter file numbers separated by commas or ranges (e.g. 1,3-5), or 'all' (default all):{RESET} ").strip()
        if not choice or choice.lower() == "all":
            selected_indexes = list(range(len(files)))
        else:
            selected_indexes = parse_selection(choice, len(files))
            if not selected_indexes:
                print(f"{RED}No valid file indexes selected.{RESET}")
                return []

        print(f"{GREEN}Requesting download links...{RESET}")
        urls = []
        for idx in selected_indexes:
            f = files[idx]
            fid = f.get("id")
            name = f.get("name", "Unknown")
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
                    print(f"{RED}No URL for {name}.{RESET}")
            else:
                print(f"{RED}Failed to get download for {name}.{RESET}")

        return urls

    except Exception as e:
        print(f"{RED}Exception during NZB upload or download: {e}{RESET}")
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
    match = re.search(r"mega\.nz/folder/([a-zA-Z0-9_-]+)#([a-zA-Z0-9_-]+)", folder_url)
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
                    file_url = f"https://mega.nz/folder/{folder_id}#{key}/file/{file_id}"
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

    if is_magnet(url):
        try:
            resp = requests.get(
                "https://api.real-debrid.com/rest/1.0/torrents/instantAvailability/" + urllib.parse.quote(url),
                headers=headers
            )
            data = resp.json()
            if "error" in data and data["error"] == "hoster_unsupported":
                return ("not_supported", None)
            return ("supported", bool(data and any(data.values())))
        except Exception:
            return ("not_supported", None)
    else:
        try:
            resp = requests.post(
                "https://api.real-debrid.com/rest/1.0/unrestrict/link",
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
        if is_magnet(url):
            r = requests.get(
                "https://api.alldebrid.com/v4/magnet/instant",
                params={"apikey": ALLDEBRID_API_TOKEN, "magnets[]": url}
            )
            data = r.json()
            if data.get("status") == "success":
                cached = data.get("data", {}).get("instant", False)
                return ("supported", cached)
            elif data.get("error", {}).get("code") == "MAGNET_NOT_SUPPORTED":
                return ("not_supported", None)
            else:
                return ("supported", False)
        else:
            r = requests.get(
                "https://api.alldebrid.com/v4/link/unlock",
                params={"apikey": ALLDEBRID_API_TOKEN, "link": url}
            )
            data = r.json()

            if data.get("status") == "success":
                return ("supported", True)
            elif data.get("error", {}).get("code") == "LINK_HOST_NOT_SUPPORTED":
                return ("not_supported", None)
            else:
                return ("supported", False)

    except Exception as e:
        print(f"Error checking AllDebrid cache: {e}")
        return ("not_supported", None)


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
            r = requests.get(
                "https://www.premiumize.me/api/transfer/directdl",
                params={"apikey": PREMIUMIZE_API_TOKEN, "src": url}
            )
            data = r.json()

            if data.get("status") == "success":
                return ("supported", True)
            elif data.get("message", "").lower().startswith("unsupported link"):
                return ("not_supported", None)
            else:
                return ("supported", False)

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
                return ("supported", info_hash in data.get("data", {}))
            else:
                return ("not_supported", None)

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
                cached = md5_hash in data.get("data", {})
                if cached:
                    return ("supported", True)
                else:
                    return ("unknown", False)  # ✅ could be unsupported or just not cached
            else:
                return ("not_supported", None)

    except Exception as e:
        print(f"Error checking TorBox cache: {e}")
        return ("not_supported", None)


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

    if not services:
        print("No debrid services available or none support this URL.")
        return []

    print()
    print(f"{CYAN}Available options:{RESET}")
    for idx, (name, support, cached) in enumerate(services, 1):
        if support == "not_supported":
            status = f"{RED}Not Supported{RESET}"
        elif support == "unknown":
            status = f"{YELLOW}Not Cached | Support unknown{RESET}"
        else:
            status = f"{GREEN}Cached{RESET}" if cached else f"{YELLOW}Not Cached{RESET}"
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
    elif name == "Torbox":
        return get_torbox_links(url)
    return []


def list_container_files():
    files = [f for f in os.listdir('.') if os.path.isfile(f) and (f.endswith('.torrent') or f.endswith('.nzb'))]
    return files

def main():
    print(f"{CYAN}OneDL v{VERSION}{RESET}")
    print()
    print(f"{CYAN}Do you want to:{RESET}")
    print(f"{YELLOW}1{RESET}. Load URLs from a file")
    print(f"{YELLOW}2{RESET}. Paste URLs manually")
    if REAL_DEBRID_API_TOKEN or ALLDEBRID_API_TOKEN or PREMIUMIZE_API_TOKEN or TORBOX_API_TOKEN:
        print(f"{YELLOW}3{RESET}. Use Debrid Service")
    choice = input("Enter 1, 2 or 3: ").strip()

    if choice == '1':
        urls = get_urls_from_file()
    elif choice == '2':
        urls = get_urls_from_input()
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
                show_find_best = sum(bool(x) for x in [REAL_DEBRID_API_TOKEN, ALLDEBRID_API_TOKEN, PREMIUMIZE_API_TOKEN, TORBOX_API_TOKEN]) > 1
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
            # Magnet/URL mode (original logic)
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
            show_find_best = sum(bool(x) for x in [REAL_DEBRID_API_TOKEN, ALLDEBRID_API_TOKEN, PREMIUMIZE_API_TOKEN, TORBOX_API_TOKEN]) > 1

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
                    # Check choice for TorBox or Premiumize
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

