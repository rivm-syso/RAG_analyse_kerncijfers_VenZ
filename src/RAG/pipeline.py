import os
import csv
import pdfplumber
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime

import pandas as pd
from tqdm.auto import tqdm

# External dependencies
from openai_connection import RIVM_AI_PLATFORM
from topics import TOPICS

# === CONFIGURATION ===
# Load all configuration from environment variables
LOG_FILE = Path(os.getenv('LOG_FILE', 'rag_3_0_response.csv'))
DIRECTORY = os.getenv('PDF_DIR', './data/brieven/')
VECTOR_STORE_ID_FILE = os.getenv('VECTOR_STORE_ID_FILE', 'vector_store_id.txt')
MODEL_NAME = os.getenv('MODEL_NAME')
if not MODEL_NAME:
    raise ValueError("MODEL_NAME environment variable not set. Please configure it.")
UPLOAD_BATCH_SIZE = int(os.getenv('UPLOAD_BATCH_SIZE', '100'))  # API limit
VECTOR_STORE_ID = os.getenv('VECTOR_STORE_ID')
if not VECTOR_STORE_ID:
    raise ValueError("VECTOR_STORE_ID environment variable not set. Please configure it or read from vector_store_id.txt.")
AUTHORIZATION_FILE_PATH = os.getenv('AUTHORIZATION_FILE_PATH')
if not AUTHORIZATION_FILE_PATH:
    raise ValueError("AUTHORIZATION_FILE_PATH environment variable not set. Please set it to the path of your authorization JSON file.")

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')


# === AI Platform Initialization ===
def get_openai_client(authorization_file_path: str, config: dict) -> Any:
    ai_platform = RIVM_AI_PLATFORM()
    return ai_platform.OpenAI(authorization_file_path, config)

client = get_openai_client(AUTHORIZATION_FILE_PATH, config={})

# === Logging Results ===
def log_result(
    run_id: str,
    topic_key: str,
    discovery_queries: List[str],
    file_id: str,
    filename: str,
    qualification: str,
    extraction_output: str,
    model: str,
    temperature: float,
    prompt_version: str,
    error: Optional[str] = None
) -> None:
    """
    Logs the results to a CSV file.
    """
    is_new = not LOG_FILE.exists()
    with open(LOG_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if is_new:
            writer.writerow([
                "timestamp", "run_id", "topic_key", "discovery_queries",
                "file_id", "filename", "qualification", "extraction_output",
                "model", "temperature", "prompt_version", "error"
            ])
        writer.writerow([
            datetime.utcnow().isoformat(), run_id, topic_key, discovery_queries,
            file_id, filename, qualification, extraction_output,
            model, temperature, prompt_version, error
        ])
    logging.info(f"Logged result for file_id={file_id}, topic={topic_key}")

# === Document Discovery ===
def discover_documents(
    client: Any,
    discovery_queries: List[str],
    model: str,
    vector_store_id: str,
    max_results: int = 50
) -> Dict[str, str]:
    """
    Returns a dict {file_id: filename} for discovered documents.
    """
    documents = {}
    logging.info(f"Starting document discovery for {len(discovery_queries)} queries.")
    for query in discovery_queries:
        logging.info(f"Query: '{query}'")
        response = client.responses.create(
            model=model,
            input=query,
            temperature=0,
            tools=[{"type": "file_search", "max_num_results": max_results, "vector_store_ids": [vector_store_id]}]
        )
        for item in response.output:
            if hasattr(item, "content"):
                for content_item in item.content:
                    if hasattr(content_item, "annotations"):
                        for annotation in content_item.annotations:
                            if hasattr(annotation, "file_id") and hasattr(annotation, "filename"):
                                file_id = annotation.file_id
                                filename = annotation.filename
                                if file_id not in documents:
                                    logging.info(f"Document found: {filename} (file_id={file_id})")
                                documents[file_id] = filename
    logging.info(f"Total unique documents found: {len(documents)}")
    return documents

# === PDF Text Extraction ===
def fetch_document_text_from_pdf(filename: str, directory: str) -> Optional[str]:
    """
    Extracts all text from a PDF file.
    """
    filepath = os.path.join(directory, filename)
    logging.info(f"Fetching text from: {filepath}")
    try:
        with pdfplumber.open(filepath) as pdf:
            text = "\n".join(page.extract_text() for page in pdf.pages if page.extract_text())
        logging.info(f"Text extraction succeeded for {filename}.")
        return text
    except Exception as e:
        logging.error(f"Error reading {filename}: {e}")
        return None

# === Qualification ===
def qualifies_document(
    client: Any,
    file_id: str,
    filename: str,
    qualification_topic: str,
    model: str,
    directory: str
) -> (bool, str):
    """
    Determines if a document qualifies for further extraction.
    """
    doc_text = fetch_document_text_from_pdf(filename, directory)
    if doc_text is None:
        return False, f"ERROR: Could not extract text from {filename}"
    prompt = f"""
    Beoordeel of het onderstaande document letterlijk kwantitatieve uitspraken (percentages, aantallen, verhoudingen of breuken) bevat over {qualification_topic}.

    Antwoord uitsluitend met:
    - JA
    - NEE

    Indien JA:
    - Noem de pagina's waar deze cijfers voorkomen.

    Document:
    {doc_text}
    """
    logging.info(f"Checking document {filename} (file_id={file_id}) for topic: {qualification_topic}")
    response = client.responses.create(
        model=model,
        temperature=0,
        input=prompt
    )
    text = response.output_text.lower()
    logging.info(f"Qualification result for {filename}: {text[:120]}...")
    return text.startswith("ja"), text

# === Extraction ===
def extract_statistics(
    client: Any,
    file_id: str,
    filename: str,
    topic_label: str,
    model: str,
    directory: str
) -> str:
    """
    Extracts quantitative statistics from the document.
    """
    doc_text = fetch_document_text_from_pdf(filename, directory)
    if doc_text is None:
        return "ERROR: Could not extract text from PDF."
    prompt = f"""
    Zoek in het onderstaande document uitsluitend naar letterlijk genoemde kwantitatieve uitspraken over {topic_label}.

    Neem alleen op:
    - percentages
    - aantallen
    - verhoudingen (zoals '1 op de 5')
    - Breuken (zoals 'tweederde' of '2/3')

    Negeer vage formuleringen zonder cijfers.

    Extraheer per uitspraak:
    - Exacte formulering van het kerncijfer
    - Betrokken populatie
    - Eventuele uitsplitsing (geslacht, leeftijd, opleidingsniveau)
    - Geografische scope
    - Pagina (indien mogelijk)
    - Genoemde bron (indien aanwezig)

    Geef de output in dit format:
    **[{filename}]**
    - Cijfer:
    - Populatie:
    - Uitsplitsing:
    - Scope:
    - Pagina:
    - Bron:

    Document:
    {doc_text}
    """
    logging.info(f"Extracting statistics from {filename} (file_id={file_id})")
    response = client.responses.create(
        model=model,
        temperature=0,
        input=prompt
    )
    logging.info(f"Extraction done for {filename}.")
    return response.output_text

# === Main Pipeline ===
def run_topic_analysis(
    topic_key: str,
    client: Any,
    run_id: Optional[str] = None,
    model: str = MODEL_NAME,
    temperature: float = 0,
    prompt_version: str = "v1",
    directory: str = DIRECTORY,
    vector_store_id: str = VECTOR_STORE_ID
) -> List[Dict[str, Any]]:
    """
    Runs the complete analysis pipeline for a given topic.
    """
    if topic_key not in TOPICS:
        raise ValueError(f"Unknown topic key: {topic_key}. Available topics: {list(TOPICS.keys())}")
    topic = TOPICS[topic_key]
    logging.info(f"==== Analyse: {topic['label']} ====")
    discovered = discover_documents(client, topic['discovery_queries'], model, vector_store_id)
    logging.info(f"Found {len(discovered)} documents for topic '{topic_key}'")
    results = []

    if run_id is None:
        run_id = datetime.utcnow().strftime("%Y%m%d%H%M%S")

    for file_id, filename in discovered.items():
        logging.info(f"--- Document: {filename} ({file_id}) ---")
        try:
            qualifies, justification = qualifies_document(
                client, file_id, filename, topic['qualification_topic'], model, directory
            )
            if not qualifies:
                logging.info(f"Document {filename} does NOT qualify.")
                log_result(
                    run_id=run_id,
                    topic_key=topic_key,
                    discovery_queries=topic['discovery_queries'],
                    file_id=file_id,
                    filename=filename,
                    qualification=justification,
                    extraction_output="",
                    model=model,
                    temperature=temperature,
                    prompt_version=prompt_version,
                    error=None if "ERROR" not in justification else justification
                )
                continue

            logging.info(f"Document {filename} qualifies. Starting extraction...")
            extracted = extract_statistics(
                client, file_id, filename, topic['label'], model, directory
            )
            results.append({"file_id": file_id, "filename": filename, "extraction": extracted})

            log_result(
                run_id=run_id,
                topic_key=topic_key,
                discovery_queries=topic['discovery_queries'],
                file_id=file_id,
                filename=filename,
                qualification=justification,
                extraction_output=extracted,
                model=model,
                temperature=temperature,
                prompt_version=prompt_version,
                error=None
            )
        except Exception as e:
            logging.error(f"Error processing {filename}: {e}")
            log_result(
                run_id=run_id,
                topic_key=topic_key,
                discovery_queries=topic['discovery_queries'],
                file_id=file_id,
                filename=filename,
                qualification="ERROR",
                extraction_output="",
                model=model,
                temperature=temperature,
                prompt_version=prompt_version,
                error=str(e)
            )
    logging.info(f"Analysis complete for topic: {topic['label']}.")
    return results

# === Utility: Run for all topics ===
def run_all_topics(client: Any, model: str = MODEL_NAME, temperature: float = 0, prompt_version: str = "v1"):
    for topic_key in TOPICS:
        logging.info(f"\nAnalyzing topic: {TOPICS[topic_key]['label']} ({topic_key})")
        run_topic_analysis(
            topic_key,
            client=client,
            model=model,
            temperature=temperature,
            prompt_version=prompt_version
        )

# === Main workflow ===
def main():
    # Example: run for one topic
    results = run_topic_analysis("obesity_youth", client=client)

    # Example: run for all topics
    # run_all_topics(client=client)

    # Example: read the log as dataframe
    if LOG_FILE.exists():
        df_log = pd.read_csv(LOG_FILE)
        print(df_log.tail(10))
        # Optionally export to Excel
        df_log.to_excel("rq3_steps2.xlsx", index=False)
        logging.info("Exported log to rq3_steps.xlsx")

if __name__ == "__main__":
    main()