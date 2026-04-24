import re
import csv
import logging
from typing import List, Tuple, Dict, Optional, Any
from pathlib import Path
from collections import defaultdict, Counter

import numpy as np
import pdfplumber
import pandas as pd
from tqdm import tqdm

import os

# Load configuration from environment variables
PDF_DIR = Path(os.getenv('PDF_DIR', './data/brieven'))
URLS_CSV = Path(os.getenv('URLS_CSV', './data/urls.csv'))
OUTPUT_MATCHES = Path(os.getenv('OUTPUT_MATCHES', 'pdf_matches_brieven.csv'))
OUTPUT_SUMMARY = Path(os.getenv('OUTPUT_SUMMARY', 'keyword_summary_brieven.csv'))
OUTPUT_STATS = Path(os.getenv('OUTPUT_STATS', 'pdf_stats_brieven.csv'))
CONTEXT_WINDOW = int(os.getenv('CONTEXT_WINDOW', '20'))

# Set up logging
logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')

# --- Search Terms ---
BASE_SEARCH_TERMS = [
    'www.staatvenz.nl', 'staatvenz.nl', 'de staat venz', 'de staat v en z', 'destaatvenz',
    'staatvenz', 'de staat', 'venz', 'v en z', 'www.vzinfo.nl', 'statline.cbs',
    'Centraal Bureau voor de Statistiek', 'statline', 'de staat volksgezondheid en zorg',
    'Trimbos Instituut', 'trimbos', 'cbs.statline', 'cbsstatline', 'cbs', 'nivel',
    'Nederlands instituut voor onderzoek van de gezondheidszorg', 'Nederlands Jeugdinstituut',
    'Nji', 'Nederlandse Zorgautoriteit', 'NZa', 'Rijksinstituut voor Volksgezondheid en Milieu',
    'RIVM', 'Sociaal en Cultureel Planbureau', 'Sociaal Cultureel Planbureau', 'SCP',
    'Zorginstituut Nederland', 'ZINL', 'ZIN', "ZN", "Het zorginstituut", "zorginstituut"
    # ... add more terms as needed
]


def load_url_terms(urls_csv: Path) -> List[str]:
    """Load URL search terms from a CSV file."""
    df = pd.read_csv(urls_csv, sep=';')
    urls = df['Page URL'].dropna().tolist()
    return urls

def build_search_terms(base_terms: List[str], url_terms: List[str]) -> List[str]:
    """Combine and deduplicate all search terms, longest first."""
    all_terms = list(dict.fromkeys(sorted(base_terms + url_terms, key=len, reverse=True)))
    return all_terms

def find_longest_match(word: str, search_terms: List[str]) -> Optional[str]:
    """Return the longest search term that matches the word (case-insensitive)."""
    matches = [term for term in search_terms if term.lower() in word.lower()]
    return max(matches, key=len) if matches else None

def get_context(words: List[str], idx: int, window: int = CONTEXT_WINDOW) -> str:
    """Return a string with context window around a word index."""
    start = max(0, idx - window)
    end = min(len(words), idx + window + 1)
    return ' '.join(words[start:end])

def is_url(term: str) -> bool:
    """Check if a term looks like a URL or domain."""
    url_pattern = r"(www\.[\w\.\-]+)|([\w\.\-]+\.(nl|com|org|info|net|gov|eu|edu))"
    return bool(re.match(url_pattern, term.lower()))

def find_reference_number(words: List[str], idx: int, window: int = CONTEXT_WINDOW) -> Tuple[Optional[str], Optional[int]]:
    """Look for a reference number (all digits) near the matched word."""
    start = max(0, idx - window)
    end = min(len(words), idx + window + 1)
    for i in range(start, end):
        if i != idx and re.fullmatch(r"\d+", words[i]):
            return words[i], i
    return None, None

def find_reference_citation(pages_text: str, ref_number: str) -> Optional[str]:
    """Find the citation text for a reference number in the full document text."""
    pattern = re.compile(rf"^{re.escape(ref_number)}\s+(.+)", re.MULTILINE)
    match = pattern.search(pages_text)
    return match.group(1) if match else None

def extract_pdf_data(pdf_path: Path, search_terms: List[str]) -> Tuple[List[List[Any]], Dict[str, Counter], List[Any]]:
    """
    Extract matches and stats from a single PDF.
    Returns:
        main_output_rows: List of CSV rows for all matches in this PDF
        summary_counter: Dict of term -> Counter(PDF filename)
        pdf_stats_row: Stats row for this PDF
    """
    main_output_rows = []
    summary_counter = defaultdict(Counter)
    failed_to_parse = False
    error_type = ''
    num_pages = 0
    total_words = 0
    word_counts = []
    pdf_matches = 0

    try:
        with pdfplumber.open(pdf_path) as pdf:
            num_pages = len(pdf.pages)
            all_text = ""
            for page_num, page in enumerate(pdf.pages, start=1):
                try:
                    words = page.extract_words() or []
                except Exception as e:
                    logging.warning(f"Error extracting words from page {page_num} in {pdf_path.name}: {e}")
                    words = []

                page_word_count = len(words)
                word_counts.append(page_word_count)
                total_words += page_word_count
                word_texts = [w['text'] for w in words]
                page_text = page.extract_text() or ""
                all_text += page_text + "\n"

                for idx, word_dict in enumerate(words):
                    word = word_dict['text']
                    match_term = find_longest_match(word, search_terms)
                    if match_term:
                        context = get_context(word_texts, idx, CONTEXT_WINDOW)
                        ref_num, ref_citation = None, None
                        if is_url(match_term):
                            ref_num, ref_idx = find_reference_number(word_texts, idx, window=CONTEXT_WINDOW)
                            if ref_num:
                                ref_citation = find_reference_citation(all_text, ref_num)
                        main_output_rows.append([
                            pdf_path.name,
                            num_pages,
                            total_words,
                            float(np.mean(word_counts)) if word_counts else 0,
                            float(np.std(word_counts)) if word_counts else 0,
                            page_num,
                            idx + 1,
                            word,
                            match_term,
                            word_dict.get('x0', ''),
                            word_dict.get('y0', ''),
                            word_dict.get('x1', ''),
                            word_dict.get('y1', ''),
                            context,
                            False,    # failed_to_parse
                            '',       # error_type
                            ref_num,
                            ref_citation
                        ])
                        summary_counter[match_term][pdf_path.name] += 1
                        pdf_matches += 1
    except Exception as e:
        failed_to_parse = True
        error_type = str(e)
        logging.error(f"Failed to parse {pdf_path.name}: {e}")
        main_output_rows.append([
            pdf_path.name, '', '', '', '', '', '', '', '', '', '', '', '', '', True, error_type, None, None
        ])

    pdf_stats_row = [
        pdf_path.name,
        num_pages,
        total_words,
        float(np.mean(word_counts)) if word_counts else 0,
        float(np.std(word_counts)) if word_counts else 0,
        failed_to_parse,
        error_type
    ]
    return main_output_rows, summary_counter, pdf_stats_row

def process_pdfs(pdf_dir: Path, search_terms: List[str]) -> Tuple[List[List[Any]], Dict[str, Counter], List[List[Any]]]:
    """
    Process all PDFs in the directory and collect outputs.
    Returns:
        main_output: list of matches
        summary_counter: dict of term -> Counter(pdf_file)
        pdf_stats: list of stats per PDF
    """
    main_output = []
    summary_counter = defaultdict(Counter)
    pdf_stats = []

    pdf_files = sorted([p for p in pdf_dir.glob("*.pdf") if p.is_file()])

    for pdf_path in tqdm(pdf_files, desc="Processing PDFs"):
        rows, file_summary, stats_row = extract_pdf_data(pdf_path, search_terms)
        main_output.extend(rows)
        for term, counter in file_summary.items():
            summary_counter[term].update(counter)
        pdf_stats.append(stats_row)

    return main_output, summary_counter, pdf_stats

def write_csv(path: Path, header: List[str], rows: List[List[Any]]) -> None:
    """Write rows to a CSV file with the specified header."""
    with path.open('w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(header)
        for row in rows:
            writer.writerow(row)

def write_summary_csv(path: Path, summary_counter: Dict[str, Counter]) -> None:
    """Write the summary of matches per search term."""
    with path.open('w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([
            'Search Term', 'Total Matches', 'Num Distinct PDFs', 'PDF List (with counts)'
        ])
        for term, counter in summary_counter.items():
            total = sum(counter.values())
            num_pdfs = len(counter)
            pdf_list = '; '.join([f"{pdf} ({cnt})" for pdf, cnt in counter.items()])
            writer.writerow([term, total, num_pdfs, pdf_list])

def main():
    """Main workflow for PDF term searching and reporting."""
    logging.info("Loading search terms...")
    url_terms = load_url_terms(URLS_CSV)
    search_terms = build_search_terms(BASE_SEARCH_TERMS, url_terms)
    logging.info(f"Loaded {len(search_terms)} search terms.")

    logging.info("Processing PDF files...")
    main_output, summary_counter, pdf_stats = process_pdfs(PDF_DIR, search_terms)

    logging.info(f"Writing matches to {OUTPUT_MATCHES}")
    write_csv(OUTPUT_MATCHES, [
        'PDF File', 'Num Pages', 'Word Count', 'Avg Words/Page', 'StdDev Words/Page',
        'Page Number', 'Word Index', 'Matched Word', 'Matched Search Term',
        'x0', 'y0', 'x1', 'y1', 'Context', 'Failed To Parse', 'Error Type',
        'Reference Number', 'Reference Citation'
    ], main_output)

    logging.info(f"Writing summary to {OUTPUT_SUMMARY}")
    write_summary_csv(OUTPUT_SUMMARY, summary_counter)

    logging.info(f"Writing PDF stats to {OUTPUT_STATS}")
    write_csv(OUTPUT_STATS, [
        'PDF File', 'Num Pages', 'Word Count', 'Avg Words/Page', 'StdDev Words/Page', 'Failed To Parse', 'Error Type'
    ], pdf_stats)

    logging.info("Done.")

if __name__ == "__main__":
    main()