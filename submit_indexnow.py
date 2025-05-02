#!/usr/bin/env python3
import os
import sys
import json
import logging
import requests
import xml.etree.ElementTree as ET
from urllib.parse import urlparse

# ——— Configuration ———
INDEXNOW_KEY = os.getenv("INDEXNOW_KEY")
if not INDEXNOW_KEY:
    logging.error("INDEXNOW_KEY environment variable not set. Exiting.")
    sys.exit(1)

SITEMAP_URL = os.getenv(
    "SITEMAP_URL", "https://www.togetherplatform.com/sitemap.xml"
)
STATE_SUBMITTED = "submitted_urls.json"
STATE_DELETED  = "deleted_urls.json"
API_ENDPOINT   = "https://api.indexnow.org/indexnow"

# ——— Helpers ———

def fetch_sitemap(url):
    resp = requests.get(url, timeout=10)
    resp.raise_for_status()
    return resp.text


def parse_urls(xml_text):
    root = ET.fromstring(xml_text)
    return [loc.text.strip() for loc in root.findall(".//{*}loc") if loc.text]


def load_state(filename):
    if not os.path.exists(filename):
        return []
    try:
        with open(filename, "r", encoding="utf-8") as fp:
            return json.load(fp)
    except Exception as e:
        logging.warning(f"Could not load {filename}: {e}. Using empty list.")
        return []


def save_state(filename, data):
    with open(filename, "w", encoding="utf-8") as fp:
        json.dump(data, fp, indent=2)


def submit_batch(urls, action):
    if not urls:
        return True

    parsed = urlparse(SITEMAP_URL)
    host = parsed.hostname

    payload = {
        "host": host,
        "key": INDEXNOW_KEY,
        "keyLocation": f"https://{host}/{INDEXNOW_KEY}",
        "urlList": urls,
    }
    if action == "delete":
        payload["action"] = "delete"

    resp = requests.post(API_ENDPOINT, json=payload, timeout=10)
    if 200 <= resp.status_code < 300:
        logging.info(f"Successfully submitted {len(urls)} '{action}' URLs.")
        return True
    else:
        logging.error(
            f"Error ({resp.status_code}) submitting {action} URLs: {resp.text}"
        )
        return False

# ——— Main Flow ———

def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    xml = fetch_sitemap(SITEMAP_URL)
    all_urls = set(parse_urls(xml))

    submitted = set(load_state(STATE_SUBMITTED))
    deleted   = set(load_state(STATE_DELETED))

    # Determine diffs
    new_urls     = list(all_urls - submitted)
    removed_urls = list((submitted - all_urls) - deleted)

    success = True
    if new_urls:
        success &= submit_batch(new_urls, "new")
        if success:
            submitted.update(new_urls)

    if removed_urls:
        success &= submit_batch(removed_urls, "delete")
        if success:
            deleted.update(removed_urls)

    # Persist state
    save_state(STATE_SUBMITTED, list(submitted))
    save_state(STATE_DELETED,   list(deleted))

    logging.info(f"Done. New: {len(new_urls)}, Removed: {len(removed_urls)}")
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
