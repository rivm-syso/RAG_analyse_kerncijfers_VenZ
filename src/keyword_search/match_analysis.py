import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import re
import logging
import os
from typing import List, Set, Optional
from sklearn.preprocessing import MultiLabelBinarizer

# --- Configuration ---
DATA_PATH = os.getenv('DATA_PATH', 'pdf_matches_brieven_2.csv')
CONTEXT_COLUMNS = ['PDF File', 'Matched Search Term', 'Matched Word', 'Page Number', 'Context']
UNWANTED_WORDS_PATH = os.getenv('UNWANTED_WORDS_PATH', 'src/keyword_search/unwanted_words.txt')  # (Optional) path to a file with unwanted words, else use in-code list

# Set up logging
logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')

# --- Data Loading ---
def load_matches(data_path: str) -> pd.DataFrame:
    """Load the matches CSV."""
    df = pd.read_csv(data_path)
    logging.info(f"Loaded {df.shape[0]} matches from {data_path}")
    return df

# --- Normalization ---
def normalize_word(word: Optional[str]) -> str:
    """Normalize words: remove punctuation/whitespace and lowercase."""
    if pd.isnull(word):
        return ''
    return re.sub(r'[\W_]+', '', str(word).lower())

def normalize_words(words: List[str]) -> Set[str]:
    """Normalize a list of words."""
    return set(normalize_word(w) for w in words)

# --- Filtering ---
def filter_matches_by_unwanted(
    matches_df: pd.DataFrame, 
    unwanted_words: List[str]
) -> pd.DataFrame:
    """Filter out matches with unwanted normalized words."""
    normalized_unwanted = normalize_words(unwanted_words)
    matches_df['Normalized Matched Word'] = matches_df['Matched Word'].apply(normalize_word)
    filtered_df = matches_df[~matches_df['Normalized Matched Word'].isin(normalized_unwanted)].copy()
    logging.info(f"Filtered matches: {filtered_df.shape[0]} rows remain after filtering unwanted words.")
    return filtered_df

# --- Mapping to Institutes ---
def combine_and_map(term: str) -> str:
    """Combine and map terms to institutes."""
    term_lower = str(term).lower()
    if term_lower == "venz" or "staatvenz.nl" in term_lower or "www.staatvenz.nl" in term_lower:
        return "VENZ"
    elif term_lower.startswith("statline"):
        return "cbs"
    elif "vzinfo.nl" in term_lower or "www.vzinfo.nl" in term_lower:
        return "VZinfo"
    else:
        return term

LABEL_MAP = {
    "VENZ": "StaatVenZ",
    "cbs": "CBS",
    "RIVM": "RIVM",
    "NZa": "NZa",
    "ZIN": "ZIN",
    "trimbos": "Trimbos",
    "nivel": "Nivel",
    "SCP": "SCP",
    "Nji": "NJi",
    "VZinfo": "VZinfo",
}

def map_institutes(filtered_df: pd.DataFrame) -> pd.DataFrame:
    """Add columns for combined and labeled institutes."""
    filtered_df["Kennisinstituut_combined"] = filtered_df["Matched Search Term"].apply(combine_and_map)
    filtered_df["Kennisinstituut"] = (
        filtered_df["Kennisinstituut_combined"]
        .map(LABEL_MAP)
        .fillna(filtered_df["Kennisinstituut_combined"])
    )
    return filtered_df

# --- Plotting ---
def plot_institute_counts(summary_df: pd.DataFrame, title=None):
    """Plot horizontal bar chart with Nivel house style and custom colors."""
    # Remove first row if you wish (as in your code)
    summary_df = summary_df.iloc[1:]
    bar_height = 0.35
    index = np.arange(len(summary_df))

    nivel_blauw = "#0074a0"
    nivel_rood = "#e50046"

    fig, ax = plt.subplots(figsize=(14, 6))
    # First red (unique), then blue (total)
    ax.barh(index + bar_height/2, summary_df['Unique_PDFs'], height=bar_height, color=nivel_rood, label="Unieke documenten", alpha=0.8)
    ax.barh(index - bar_height/2, summary_df['Total_matches'], height=bar_height, color=nivel_blauw, label="Totaal")

    for i, (v1, v2) in enumerate(zip(summary_df['Total_matches'], summary_df['Unique_PDFs'])):
        ax.text(v2 + 1, i + bar_height/2, str(v2), va='center', color=nivel_rood)
        ax.text(v1 + 1, i - bar_height/2, str(v1), va='center', color=nivel_blauw)
        
    ax.set_yticks(index)
    ax.set_yticklabels(summary_df.index)
    ax.set_xlabel("Aantal matches")
    ax.set_ylabel("Kennisinstituut")
    if title:
        ax.set_title(title)

    # Legend outside the plot, right bottom
    ax.legend(loc='lower right', bbox_to_anchor=(1.25, 0.05))
    plt.tight_layout()
    plt.show()

def plot_cooccurrence_heatmap(filtered_df: pd.DataFrame):
    """Plot a co-occurrence heatmap of institutes per document."""
    pdf_partner = (
        filtered_df.groupby("PDF File")["Kennisinstituut"]
        .unique().reset_index()
    )
    pdf_partner["Kennisinstituut"] = pdf_partner["Kennisinstituut"].apply(
        lambda x: [i for i in x if isinstance(i, str) and i.strip() != ""]
    )
    pdf_partner = pdf_partner[pdf_partner["Kennisinstituut"].apply(lambda x: len(x) > 0)]
    mlb = MultiLabelBinarizer()
    binary_matrix = pd.DataFrame(
        mlb.fit_transform(pdf_partner["Kennisinstituut"]),
        index=pdf_partner["PDF File"],
        columns=mlb.classes_
    )
    co_occurrence = binary_matrix.T.dot(binary_matrix)
    np.fill_diagonal(co_occurrence.values, 0)
    plt.figure(figsize=(10, 8))
    sns.heatmap(co_occurrence, annot=True, fmt='d', cmap="Blues")
    plt.title("Co-occurrence van kennisinstituten per document")
    plt.ylabel("Kennisinstituut")
    plt.xlabel("Kennisinstituut")
    plt.tight_layout()
    plt.show()

# --- Main Workflow ---
def main():
    # 1. Load data
    matches_df = load_matches(DATA_PATH)
    
    # 2. Define or load unwanted words
    try:
        with open(UNWANTED_WORDS_PATH) as f:
            unwanted_words = [line.strip() for line in f if line.strip()]
            logging.info(f"Loaded {len(unwanted_words)} unwanted words from {UNWANTED_WORDS_PATH}")
    except FileNotFoundError:
        logging.error(f"Unwanted words file not found: {UNWANTED_WORDS_PATH}")
        logging.error(f"Set UNWANTED_WORDS_PATH environment variable or ensure file exists")
        raise

    # 3. Filter and normalize
    filtered_df = filter_matches_by_unwanted(matches_df, unwanted_words)

    # 4. Map to institutes
    filtered_df = map_institutes(filtered_df)

    # 5. Compute summary
    summary_df = (
        filtered_df.groupby('Kennisinstituut')
        .agg(
            Total_matches=('Matched Word', 'count'),
            Unique_PDFs=('PDF File', pd.Series.nunique)
        )
        .sort_values('Total_matches', ascending=True)
    )

    # 6. Plot results
    plot_institute_counts(summary_df, title="Aantal matches en unieke documenten per kennisinstituut")
    plot_cooccurrence_heatmap(filtered_df)

    logging.info("Done.")

if __name__ == "__main__":
    main()