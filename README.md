# StaatVenZ key figure Analysis Toolkit

**Auteurs:** Claudia Laarman, Joost Vanhommerig, Jens Ruhof, Carlijn Hendriks, Louise Dekker, Bart Knottnerus  
**Publicatie:** Utrecht: Nivel, 2026

---

## Overview
This repository contains scripts and tools for the analysis of Kamerbrieven (parliamentary letters) and related documents concerning the Staat van Volksgezondheid en Zorg (StaatVenZ). The toolkit enables PDF keyword searching, matched word analysis, web scraping, and Retrieval Augmented Generation (RAG) topic extraction. Outputs include detailed CSV files for downstream analysis and visualization.

---

## Folder Structure
```
staatVenZ/
│
├── src/
│   ├── keyword_search/
│   │   ├── keyword_search.py
│   │   ├── match_analysis.py
│   │   └── unwanted_words.txt
│   ├── RAG/
│   │   ├── create_vector_store.py.py
│   │   ├── openai_connection.py
│   │   ├── pipeline.py
│   │   └── topics.py
│   └── webscraping/
│       └── scrape_brieven.py
│
├── environment.yml
├── .gitignore
├── CITATION.cff
├── LICENSE.md
├── README.md
```


## Background
The website www.staatvenz.nl aims to provide up-to-date and unambiguous data, which exist to support policy monitoring and accounting. The website is built specifically for the Minister of Health, the policy makers of the Ministry and the Members of the House of Representatives. The website is hosted by the Dutch National Institute for Public Health and the Environment. 

---

## Setup & Configuration

### Installation

1. **Create conda environment**
   ```bash
   conda env create -f environment.yml
   conda activate VenZ
   ```

3. **Key Configuration Variables:**
   - `PDF_DIR` - Directory containing PDF files to analyze
   - `URLS_CSV` - Path to CSV with additional URLs to search
   - `AUTHORIZATION_FILE_PATH` - Path to AI platform authorization JSON
   - `MODEL_NAME` - AI model name (for RAG pipeline)
   - `VECTOR_STORE_ID` - Vector store identifier (for RAG pipeline)

---

## Usage

### Script: `scrape_brieven.py` - Download Dutch Parliamentary Letters
```bash
python src/webscraping/scrape_brieven.py --max-pages 10 --output ./downloads
```
**Parameters:**
- `--max-pages`: Maximum number of pages to scrape (optional, default: all)
- `--output`: Output directory for downloaded PDFs (optional, default: `downloads`)

**Output:** PDF files in the specified directory

---

### Script: `keyword_search.py` - Search PDFs for Keywords
```bash
python src/keyword_search/keyword_search.py
```
**Configuration (via `.env`):**
- `PDF_DIR` - Directory with PDF files
- `URLS_CSV` - CSV file with additional URLs to search
- `OUTPUT_MATCHES` - Output CSV file (detailed matches)
- `OUTPUT_SUMMARY` - Output CSV file (summary statistics)
- `OUTPUT_STATS` - Output CSV file (per-PDF statistics)

**Output:** 
- `pdf_matches_brieven.csv` - Detailed match information
- `keyword_summary_brieven.csv` - Aggregated statistics
- `pdf_stats_brieven.csv` - Per-PDF statistics

---

### Script: `match_analysis.py` - Analyze and Visualize Keyword Matches
```bash
python src/keyword_search/match_analysis.py
```
**Configuration (via `.env`):**
- `DATA_PATH` - Input CSV from keyword_search.py
- `UNWANTED_WORDS_PATH` - File with unwanted words to filter

**Output:**
- Institute count bar chart (visualization)
- Co-occurrence heatmap (visualization)

---

### Script: `pipeline.py` - RAG-based Statistics Extraction
```bash
python src/RAG/pipeline.py
```
**Configuration (via `.env`):**
- `PDF_DIR` - Directory with PDF files
- `AUTHORIZATION_FILE_PATH` - AI platform credentials
- `MODEL_NAME` - AI model to use
- `VECTOR_STORE_ID` - Vector store identifier
- `LOG_FILE` - Output CSV for results

**Output:** `rag_3_0_response.csv` - Extracted statistics with AI analysis

---

## Methode

### Data

- **Bron:** 2555 Kamerbrieven (2021–januari 2025), verzameld via [tweedekamer.nl](https://www.tweedekamer.nl/kamerstukken/brieven_regering)

### Webscraping
- **scrape_brieven.py** : The scrape_brieven.py script automates the retrieval of Dutch parliamentary government letters (brieven van de regering) from the Tweede Kamer website, specifically for the VWS committee between 2021 and 2025. When run, the script scrapes document metadata from the website's search pages, using robust HTTP requests to handle intermittent network errors. It parses the HTML content to extract document titles, dates, and unique identifiers, then downloads each PDF to the specified output directory with cleaned and length-limited filenames. Users can configure the maximum number of pages to scrape and the output folder via command-line options. Progress and errors are logged throughout, ensuring reliability and traceability. This tool streamlines large-scale collection of official government documents for research and analysis.

### Keyword search
- **keyword_search.py** 
    PDF Keyword Matching and Reporting

    This script scans a directory of PDF files (typically Dutch parliamentary letters) for specified keywords and URLs related to the Staat VenZ and its partner institutes. It combines a base list of search terms with additional URLs from a CSV file, then parses each PDF using pdfplumber, searching for matches at the word level. For each match, it records context, location, and—where applicable—reference numbers and citations. The results are saved to CSV files: one detailing all matches, one summarizing keyword frequencies across documents, and one reporting per-PDF statistics. The script uses robust logging, handles PDF parsing errors gracefully, and provides a progress bar during processing. All file and folder locations are managed via local_path.py for easy configuration.

- **match_analysis.py** This script processes a CSV file containing keyword matches extracted from parliamentary PDF documents. It normalizes matched words to ensure robust filtering, removes unwanted matches based on a user-provided list, and maps search terms to their corresponding knowledge institutes (e.g. StaatVenZ, CBS, RIVM). The script then computes summary statistics per institute, including total match counts and the number of unique documents where each institute appears. Results are visualized in a horizontal bar chart (using custom colors for the Nivel house style) and a co-occurrence heatmap showing how institutes are referenced together within documents. The workflow is fully automated and can be customized by editing the unwanted words list and mapping logic. Logging provides progress updates, and the script can be extended for batch processing or report generation.

### RAG
- **create_vector_store.py** 
    Vector Store Creation and Document Upload

    This script prepares a vector store for use in retrieval-augmented analysis workflows. It scans a specified directory for all available PDF documents, checks whether a vector store already exists (using a locally saved ID), and if not, creates a new vector store via the OpenAI platform. The script then compares local files to those already present in the vector store and uploads only missing documents, efficiently handling batches to comply with API limits. Upon completion, it confirms the number of files available in the vector store. This process ensures that all relevant documents are indexed and ready for semantic search and AI-driven extraction in subsequent analysis steps. All configuration options, such as upload directory and batch size, can be easily adjusted at the top of the script for flexible reuse.

- **pipeline.py** 

    AI-Driven Topic Extraction Pipeline for Parliamentary PDFs

    This script implements a Retrieval Augmented Generation (RAG) pipeline for extracting quantitative statistics from Dutch parliamentary letters. It connects to an external AI platform, searches for relevant documents using topic-specific queries, and downloads text from PDFs. For each document, it determines whether the text contains explicit quantitative statements about the topic (e.g., obesity among youth), then extracts detailed statistics using targeted prompts. Results—including document IDs, filenames, extracted statistics, and errors—are logged to a CSV file for downstream analysis. The pipeline can be run for a single topic or all topics, and outputs can be exported to Excel. All configuration (paths, model parameters, authorization) is handled at the top of the script. Logging provides progress updates and error tracking throughout the workflow.

- **topics.py** 
    Topics Configuration

    The topics.py file defines the analysis topics for the AI-driven pipeline. Each topic is represented as a dictionary entry, containing a descriptive label, a set of Dutch-language discovery queries for document search, a qualification phrase for filtering relevant content, and a list of accepted sources. This configuration enables flexible and targeted retrieval of statistics from parliamentary documents, guiding the pipeline to focus on health and care-related metrics such as obesity among youth, loneliness in adults, cancer mortality, and financial accessibility of care. New topics can easily be added or customized as needed.

### Kerncijfers geanalyseerd

**Top 5 meest bezochte kerncijfers (op basis van bezoekersaantallen):**
1. [Zorgverzekeringsconcerns: marktaandeel](https://www.staatvenz.nl/kerncijfers/zorgverzekeringsconcerns-marktaandeel)
2. [Eenzaamheid: volwassenen](https://www.staatvenz.nl/kerncijfers/eenzaamheid)
3. [Euthanasie: uitgevoerd met medicijnen volgens de richtlijn](https://www.staatvenz.nl/kerncijfers/euthanasie-uitgevoerd-met-medicijnen-volgens-de-richtlijn)
4. [Kanker: sterfte](https://www.staatvenz.nl/kerncijfers/kanker-sterfte)
5. [Wachttijd gespecialiseerde GGZ: overschrijding treeknorm en gemiddelde wachttijd](https://www.staatvenz.nl/kerncijfers/wachttijd-gespecialiseerde-ggz-overschrijding-treeknorm-en-gemiddelde-wachttijd)

**Drie kerncijfers uit string matching:**
1. [Overgewicht bij jongeren](https://www.staatvenz.nl/kerncijfers/overgewicht-en-obesitas-jongeren)
2. [Levensverwachting](https://www.staatvenz.nl/kerncijfers/levensverwachting)
3. [Financiële toegankelijkheid: afzien van zorg vanwege de kosten](https://www.staatvenz.nl/kerncijfers/financi%C3%ABle-toegankelijkheid-afzien-van-zorg-vanwege-de-kosten)

---

## Resultaten

- De Staat VenZ wordt weinig genoemd als bron (32 keer in 24 unieke Kamerbrieven).
- Consortiumpartners zoals RIVM, NZa en ZIN worden veel vaker genoemd (>4000 keer).
- Bronnen worden meestal vermeld in voetnoten, vaak met consortiumpartner als bron.
- De AI-methode RAG bleek effectief in het vinden van statistieken in Kamerbrieven.

**Voorbeeld van verkregen statistieken uit de AI analyse:**
- "De helft van de Nederlanders heeft op dit moment overgewicht."  
  Bron: Sociaal en Cultureel Planbureau (voetnoot 1)
- "Mensen met een praktische opleiding en laag inkomen hebben een levensverwachting in goed ervaren gezondheid die 15 jaar lager is dan mensen met een theoretische opleiding."  
  Bron: Raad voor Volksgezondheid en Samenleving (RVS)

---

## Limitaties

- Alleen Kamerbrieven geanalyseerd (geen commissieverslagen, nota's, etc.).
- Pdf-parser kan tekst of figuren missen.
- AI-output is niet deterministisch.
- Vier Kamerbrieven konden niet worden geanalyseerd door technische beperkingen.

---

## Aanbevelingen

- Herhaal onderzoek met andere kerncijfers en documenttypen.
- Doe kwalitatief onderzoek met beleidsmakers en Kamerleden voor meer inzicht.
- Ontwikkel een uniforme bronvermeldingsstrategie voor Kamerbrieven.
- Gebruik de RAG-methode als signaleringsfunctie voor relevante kerncijfers.
- Verbeter document recall door RAG met stringmatching the combineren.

---

## Gebruikte websites

1. [Overzicht kerncijfers](https://www.staatvenz.nl/kerncijfers/alfabetisch)
2. [Over de Staat van Volksgezondheid en Zorg](https://www.staatvenz.nl/over-de-staat)
3. [Brieven regering](https://www.tweedekamer.nl/kamerstukken/brieven_regering)
4. [Zorgverzekeringsconcerns: marktaandeel](https://www.staatvenz.nl/kerncijfers/zorgverzekeringsconcerns-marktaandeel)
5. [Eenzaamheid: volwassenen](https://www.staatvenz.nl/kerncijfers/eenzaamheid)
6. [Euthanasie: uitgevoerd met medicijnen volgens de richtlijn](https://www.staatvenz.nl/kerncijfers/euthanasie-uitgevoerd-met-medicijnen-volgens-de-richtlijn)
7. [Kanker: sterfte](https://www.staatvenz.nl/kerncijfers/kanker-sterfte)
8. [Wachttijd gespecialiseerde ggz: Overschrijding treeknorm en gemiddelde wachttijd](https://www.staatvenz.nl/kerncijfers/wachttijd-gespecialiseerde-ggz-overschrijding-treeknorm-en-gemiddelde-wachttijd)
9. [Overgewicht en obesitas: jongeren](https://www.staatvenz.nl/kerncijfers/overgewicht-en-obesitas-jongeren)
10. [Levensverwachting](https://www.staatvenz.nl/kerncijfers/levensverwachting)
11. [Financiële toegankelijkheid: afzien van zorg vanwege de kosten](https://www.staatvenz.nl/kerncijfers/financi%C3%ABle-toegankelijkheid-afzien-van-zorg-vanwege-de-kosten)

---

## Bronvermelding

Laarman, C, Vanhommerig, J, Ruhof, J, Hendriks, C, Dekker, L, Knottnerus, B. Het gebruik van kerncijfers van de Staat VenZ in Kamerbrieven. Utrecht: Nivel, 2026.

---

## Contact

<!-- Voor meer informatie en andere publicaties:  
[Nivel publicaties](https://www.nivel.nl/publicaties) -->
jens.ruhof@rivm.nl

C.laarman@nivel.nl

## License

This project is licensed under the European Union Public Licence (EUPL) v.1.2.  
See the [LICENSE](LICENSE.txt) file for the full license text.

If you distribute this code or derivative works, please retain copyright,
license, and disclaimer notices, and provide source code as required by the license.
---