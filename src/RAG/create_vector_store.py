import os
from pathlib import Path
from openai_connection import RIVM_AI_PLATFORM

# === CONFIG ===
# Load configuration from environment variables
DIRECTORY = os.getenv('PDF_DIR', './data/brieven/')
VECTOR_STORE_ID_FILE = os.getenv('VECTOR_STORE_ID_FILE', 'vector_store_id.txt')
UPLOAD_BATCH_SIZE = int(os.getenv('UPLOAD_BATCH_SIZE', '100'))

# === INITIALISATIE AI PLATFORM ===
# Load credentials from environment variables
authorization_file_path = os.getenv('AUTHORIZATION_FILE_PATH')
if not authorization_file_path:
    raise ValueError("AUTHORIZATION_FILE_PATH environment variable not set. Please set it to the path of your authorization JSON file.")

config = {}
ai_platform = RIVM_AI_PLATFORM()
client = ai_platform.OpenAI(authorization_file_path, config)

def get_existing_vector_store_id():
    """Check if a vector store ID exists locally."""
    if os.path.exists(VECTOR_STORE_ID_FILE):
        with open(VECTOR_STORE_ID_FILE) as f:
            return f.read().strip()
    return None

def save_vector_store_id(vector_store_id):
    with open(VECTOR_STORE_ID_FILE, "w") as f:
        f.write(vector_store_id)

def get_all_local_files():
    """Collect all files in DIRECTORY."""
    return [
        os.path.join(DIRECTORY, fname)
        for fname in os.listdir(DIRECTORY)
        if os.path.isfile(os.path.join(DIRECTORY, fname))
    ]

def get_file_name(path):
    """Extract file name from path."""
    return os.path.basename(path)

def list_files_in_store(vector_store_id):
    """Return set of file names already uploaded to vector store."""
    try:
        files = client.vector_stores.files.list(vector_store_id=vector_store_id)
        return set((f.file_name if hasattr(f, 'file_name') else f.id) for f in files)
    except Exception as e:
        print(f"[WARNING] Could not fetch files from vector store: {e}")
        return set()

def upload_files_in_batches(vector_store_id, file_paths, already_uploaded_names):
    """Upload missing files in batches."""
    to_upload = [f for f in file_paths if get_file_name(f) not in already_uploaded_names]
    if not to_upload:
        print("[INFO] All local files are already present in the vector store.")
        return
    total = len(to_upload)
    print(f"[INFO] Start upload of {total} new files (batch size {UPLOAD_BATCH_SIZE})")
    for i in range(0, total, UPLOAD_BATCH_SIZE):
        batch_paths = to_upload[i:i+UPLOAD_BATCH_SIZE]
        print(f"[INFO] Uploading batch {i//UPLOAD_BATCH_SIZE+1}: {len(batch_paths)} files.")
        file_streams = []
        try:
            for path in batch_paths:
                try:
                    file_streams.append(open(path, "rb"))
                except Exception as e:
                    print(f"[ERROR] Cannot open file: {path} ({e})")
            if not file_streams:
                print("[WARNING] No files in this batch to upload.")
                continue
            file_batch = client.vector_stores.file_batches.upload_and_poll(
                vector_store_id=vector_store_id, files=file_streams
            )
            print("  Upload status:", file_batch.status)
            print("  File counts:", file_batch.file_counts)
        except Exception as e:
            print(f"[ERROR] Upload failed for batch: {e}")
        finally:
            for fs in file_streams:
                try:
                    fs.close()
                except:
                    pass
    print("[INFO] Upload of missing files completed.")

def get_or_create_vector_store(client, file_paths):
    """
    Get an existing vector store or create a new one and upload missing files.
    """
    vector_store_id = get_existing_vector_store_id()
    if vector_store_id:
        print(f"[INFO] Using existing vector store: {vector_store_id}")
    else:
        print("[INFO] No vector store found, creating a new one.")
        vector_store = client.vector_stores.create(name="VenZ_beleidsstukken")
        vector_store_id = vector_store.id
        save_vector_store_id(vector_store_id)
        print(f"[INFO] New vector store created with ID: {vector_store_id}")

    already_uploaded_names = list_files_in_store(vector_store_id)
    print(f"[INFO] {len(already_uploaded_names)} files already in vector store.")

    upload_files_in_batches(vector_store_id, file_paths, already_uploaded_names)
    return vector_store_id

if __name__ == "__main__":
    # Gather all file paths
    file_paths = get_all_local_files()
    print(f"[INFO] Found {len(file_paths)} local files.")

    # Create or get vector store, upload missing files
    vector_store_id = get_or_create_vector_store(client, file_paths)
    print(f"[INFO] Vector store now contains: {len(list_files_in_store(vector_store_id))} files.")