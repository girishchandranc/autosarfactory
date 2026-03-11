"""
Build the AUTOSAR semantic knowledge base for the autosarfactory MCP server.

Usage:
    python build_knowledge_base.py --docs /path/to/autosar/specs/

Supported input formats:
    - PDF  (.pdf)
    - HTML (.html, .htm)
    - Text (.txt)

Output:
    autosarfactory_mcp/kb/<name>.pkl  (loaded automatically by the MCP server)

Dependencies:
    pip install sentence-transformers numpy pdfplumber beautifulsoup4
"""

import argparse
import pathlib
import pickle
import re
import sys

CHUNK_SIZE    = 400   # words per chunk
CHUNK_OVERLAP = 50    # word overlap between chunks
_KB_DIR       = pathlib.Path(__file__).parent.parent / "autosarfactory_mcp" / "kb"

def extract_pdf(path: pathlib.Path) -> str:
    try:
        import pdfplumber
    except ImportError:
        print(f"  [skip] pdfplumber not installed — cannot read {path.name}")
        return ""
    text_parts = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                text_parts.append(text)
    return "\n".join(text_parts)

def extract_text(path: pathlib.Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")

def extract(path: pathlib.Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return extract_pdf(path)
    elif suffix == ".txt":
        return extract_text(path)
    else:
        print(f"  [skip] unsupported format: {path.name}")
        return ""


def clean(text: str) -> str:
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def chunk(text: str) -> list[str]:
    words  = text.split()
    chunks = []
    step   = CHUNK_SIZE - CHUNK_OVERLAP
    for i in range(0, len(words), step):
        chunk_words = words[i : i + CHUNK_SIZE]
        if len(chunk_words) < 20:          # skip tiny trailing chunks
            continue
        chunks.append(" ".join(chunk_words))
    return chunks


def build(docs_path: pathlib.Path, output_path: pathlib.Path) -> None:
    print(f"Scanning: {docs_path}")

    doc_files = list(docs_path.rglob("*.pdf")) + \
                list(docs_path.rglob("*.txt"))

    if not doc_files:
        print("No supported documents found (.pdf, .txt).")
        sys.exit(1)

    all_chunks = []
    for path in sorted(doc_files):
        print(f"  Reading: {path.name}")
        raw  = extract(path)
        text = clean(raw)
        if not text:
            continue
        doc_chunks = chunk(text)
        all_chunks.extend(doc_chunks)
        print(f"    -> {len(doc_chunks)} chunks")

    if not all_chunks:
        print("No text could be extracted from the documents.")
        sys.exit(1)

    print(f"\nTotal chunks: {len(all_chunks)}")
    print("Computing embeddings (this may take a few minutes)...")

    try:
        from sentence_transformers import SentenceTransformer
    except ImportError:
        print("sentence-transformers is required. Install it with: pip install sentence-transformers")
        sys.exit(1)

    model      = SentenceTransformer("all-MiniLM-L6-v2")
    embeddings = model.encode(all_chunks, show_progress_bar=True, batch_size=64)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "wb") as f:
        pickle.dump({"chunks": all_chunks, "embeddings": embeddings}, f)

    size_mb = output_path.stat().st_size / 1_048_576
    print(f"\nKnowledge base saved to: {output_path}")
    print(f"  Chunks    : {len(all_chunks)}")
    print(f"  File size : {size_mb:.1f} MB")
    print("\nRestart the MCP server to load the new knowledge base.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build AUTOSAR knowledge base for autosarfactory MCP")
    parser.add_argument("--docs", required=True, type=pathlib.Path,
                        help="Directory containing AUTOSAR spec documents (PDF/TXT)")
    parser.add_argument("--output", type=str, default="autosar_kb.pkl",
                        help="Output .pkl filename (placed in autosarfactory_mcp/kb/). "
                             "Default: autosar_kb.pkl. "
                             "Use distinct names for separate topic areas, e.g. autosar_com_kb.pkl")
    args = parser.parse_args()

    if not args.docs.is_dir():
        print(f"Error: {args.docs} is not a directory.")
        sys.exit(1)

    output_path = _KB_DIR / args.output
    if not output_path.suffix == ".pkl":
        print("Error: --output must end with .pkl")
        sys.exit(1)

    build(args.docs, output_path)
