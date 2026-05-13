"""
We strongly advise ignoring this script and instead look at https://opendata.tweedekamer.nl/ for data retrieval.

Script to scrape and download Dutch parliamentary government letters (brieven van de regering)
from the Tweede Kamer website for the VWS committee, between 2021 and 2025.

Features:
- Configurable output folder and page limit
- Robust downloading with retries and logging
- Sanitized, length-limited filenames
- CLI for easy use

Usage:
    python script.py --max-pages 5 --output myfolder
"""

import requests
from bs4 import BeautifulSoup
from urllib.parse import parse_qs, urlparse
from pathlib import Path
import re
import time
import logging
from typing import List, Dict, Optional


# --- Configuration Constants ---
SEARCH_URL = (
    "https://www.tweedekamer.nl/kamerstukken/brieven_regering?"
    "fld_prl_kamerstuk=Brieven%20regering"
    "&fld_prl_voortouwcommissie=Vaste%20commissie%20voor%20Volksgezondheid%2C%20Welzijn%20en%20Sport"
    "&fld_tk_categorie=Kamerstukken&fromdate=01/01/2021&qry=*&srt=date%3Adesc%3Adate"
    "&sta=1&todate=01/01/2025&page={page}"
)
HEADERS = {"User-Agent": "Mozilla/5.0"}
DEFAULT_FOLDER = Path("downloads")
SLEEP_BETWEEN_REQUESTS = 2
MAX_FILENAME_LENGTH = 240

logging.basicConfig(level=logging.INFO)

def clean_filename(name: str) -> str:
    """
    Sanitize a filename by removing forbidden characters and replacing spaces.
    """
    name = re.sub(r'[<>:"/\\|?*]', '', name)
    return name.strip().replace(' ', '_')

def robust_get(
    session: requests.Session,
    url: str,
    headers: dict,
    max_retries: int = 3,
    timeout: int = 15,
    pause: int = 2
) -> Optional[requests.Response]:
    """
    Make a robust GET request with retries.
    """
    for attempt in range(max_retries):
        try:
            response = session.get(url, headers=headers, timeout=timeout)
            response.raise_for_status()
            return response
        except requests.RequestException as e:
            logging.warning(f"Request error: {e}. Attempt {attempt + 1} of {max_retries}")
            if attempt < max_retries - 1:
                time.sleep(pause)
    return None

def parse_documents_from_html(html: str) -> List[Dict[str, str]]:
    """
    Parse document metadata from a page of HTML.
    """
    soup = BeautifulSoup(html, "html.parser")
    cards = soup.find_all("div", class_="m-card__main")
    documents = []
    for card in cards:
        time_tag = card.find("time")
        date = time_tag['datetime'][:10] if time_tag else ""
        h4 = card.find("h4", class_="u-mt-0")
        if not h4:
            continue
        a = h4.find("a", attrs={"data-test": "kamerstuk--link"})
        if not a:
            continue
        title = a.get_text(strip=True)
        href = a['href']
        params = parse_qs(urlparse(href).query)
        doc_id = params.get("id", [""])[0]
        did = params.get("did", [""])[0]
        docnr = ""
        for p in card.find_all("p", class_="u-mt-0 u-text-dark-gray"):
            if re.match(r"\d{4}D\d+", p.get_text(strip=True)):
                docnr = p.get_text(strip=True)
                break
        documents.append({
            "title": title,
            "id": doc_id,
            "did": did,
            "date": date,
            "docnr": docnr
        })
    return documents

def get_documents(max_pages: Optional[int] = None) -> List[Dict[str, str]]:
    """
    Scrape documents from the search pages.
    """
    documents = []
    page = 0
    with requests.Session() as session:
        while True:
            logging.info(f"Scraping page {page}...")
            url = SEARCH_URL.format(page=page)
            response = robust_get(session, url, HEADERS)
            if response is None:
                logging.error(f"Failed to retrieve page {page}.")
                break
            page_docs = parse_documents_from_html(response.text)
            if not page_docs:
                logging.info("No more results found.")
                break
            documents.extend(page_docs)
            page += 1
            if max_pages is not None and page >= max_pages:
                break
            time.sleep(SLEEP_BETWEEN_REQUESTS)
    return documents

def download_documents(documents: List[Dict[str, str]], folder: Path = DEFAULT_FOLDER) -> None:
    """
    Download document PDFs to the specified folder.
    """
    folder.mkdir(parents=True, exist_ok=True)
    with requests.Session() as session:
        for doc in documents:
            title_part = clean_filename(doc['title'])[:60]
            filename = f"{doc['date']}_{doc['docnr']}_{title_part}.pdf"
            if len(filename) > MAX_FILENAME_LENGTH:
                filename = filename[:MAX_FILENAME_LENGTH - 4] + ".pdf"
            filepath = folder / filename
            url = f"https://www.tweedekamer.nl/downloads/document?id={doc['docnr']}"
            logging.info(f"Downloading '{doc['title']}' as '{filename}'...")
            response = robust_get(session, url, HEADERS)
            if response and response.status_code == 200:
                filepath.write_bytes(response.content)
            else:
                logging.warning(f"Failed to download {url}")
            time.sleep(1)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Download Dutch parliamentary documents.")
    parser.add_argument("--max-pages", type=int, default=None, help="Maximum number of pages to scrape.")
    parser.add_argument("--output", type=str, default="downloads", help="Output directory.")
    args = parser.parse_args()

    docs = get_documents(max_pages=args.max_pages)
    logging.info(f"Found {len(docs)} documents.")
    download_documents(docs, folder=Path(args.output))