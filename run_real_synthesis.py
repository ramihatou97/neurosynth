TEMP_LIB_DIR = OUTPUT_DIR / "temp_library"
ENTIRE_BOOKS_DIR = TEMP_LIB_DIR / "Entire books"
SOURCES_DIR = OUTPUT_DIR / "sources"
MANIFEST_PATH = OUTPUT_DIR / "manifest.json"
SYNTHESIS_DIR = OUTPUT_DIR / "synthesis"

# Override paths for this run
LIBRARY_PATH = TEMP_LIB_DIR
DATABASE_PATH = OUTPUT_DIR / "temp_library.db"
ORIGINAL_SOURCES = project_root / "test_pipeline/sources"


def setup():
    if OUTPUT_DIR.exists():
        shutil.rmtree(OUTPUT_DIR)
    OUTPUT_DIR.mkdir(parents=True)
    ENTIRE_BOOKS_DIR.mkdir(parents=True)
    SOURCES_DIR.mkdir(parents=True)

    print(f"📂 Setup complete. Output dir: {OUTPUT_DIR}")

    # Copy PDFs to temp library (symlinks resolve to outside path, causing validation error)
    print(f"Copying PDFs from {ORIGINAL_SOURCES} to {ENTIRE_BOOKS_DIR}...")
    for pdf in ORIGINAL_SOURCES.glob("*.pdf"):
        dest = ENTIRE_BOOKS_DIR / pdf.name
        shutil.copy2(pdf, dest)
        print(f"  Copied {pdf.name}")


import fitz


def index_library(db):
    print("\nIndexing library...")
    print(f"Scanning {LIBRARY_PATH}...")

    # Scan recursively
    pdfs = list(LIBRARY_PATH.rglob("*.pdf"))
    print(f"Found {len(pdfs)} PDFs.")

    # Initialize Scanner for figure extraction
    from src.utils.library_scanner import LibraryScanner

    scanner = LibraryScanner(LIBRARY_PATH, db)

    for pdf_path in pdfs:
        print(f"  Indexing {pdf_path.name}...")
        try:
            # Track file in DB
            file_size = pdf_path.stat().st_size
            # Use MD5 checksum to match what PDFSearcher expects
            checksum = db.get_file_checksum(pdf_path)

            # Extract text
            doc = fitz.open(pdf_path)
            page_count = len(doc)

            db.track_file(
                pdf_path=pdf_path,
                checksum=checksum,
                file_size=file_size,
                book_series="Test Series",
                chapter_title=pdf_path.stem,
                page_count=page_count,
            )

            for i, page in enumerate(doc):
                text = page.get_text()
                if text.strip():
                    db.cache_pdf_text(pdf_path, i, text, checksum)

            doc.close()

            # Extract figures
            print(f"    Extracting figures...")
            scanner.extract_figures(pdf_path, force=True)

        except Exception as e:
            print(f"  Error indexing {pdf_path.name}: {e}")


def run_search_and_extract():
    print("\n" + "=" * 50)
    print("STEP 1: Search and Extract")
    print("=" * 50)

    print(f"Library Path: {LIBRARY_PATH}")
    print(f"Database Path: {DATABASE_PATH}")

    if not LIBRARY_PATH.exists():
        print(f"❌ Library path {LIBRARY_PATH} does not exist.")
        return None

    # Initialize Database
    db = Database(DATABASE_PATH)

    # Index the library manually
    index_library(db)

    # Initialize Searcher
    searcher = PDFSearcher(LIBRARY_PATH, db)

    query = "lumbar discectomy"
    print(f"Searching for: '{query}'...")

    # Collect results
    # Force inclusion of all files in the library
    # The user wants to ensure ALL sources are used if relevant.
    # Since we only have 5 files and they are all relevant to the topic, we will add them all.

    print("Forcing inclusion of all library files...")
    results = []
    all_pdfs = list(LIBRARY_PATH.rglob("*.pdf"))

    # Import SearchResult for manual construction
    from src.search.result_model import SearchResult

    for pdf_path in all_pdfs:
        # Create a dummy result for each file
        # We need to find at least one matching page to satisfy the extractor
        # We'll search for "lumbar" or "disc" or "spine" to find a relevant page

        # Use the searcher to find the best page in this specific file
        # Try specific query first
        file_matches = searcher.search_pdf(query, pdf_path)

        # Fallback to broader query if no matches
        if not file_matches:
            print(
                f"  ⚠️ Could not find query '{query}' in {pdf_path.name}. Trying 'lumbar'..."
            )
            file_matches = searcher.search_pdf("lumbar", pdf_path)

        if not file_matches:
            print(
                f"  ⚠️ Could not find query 'lumbar' in {pdf_path.name}. Trying 'spine'..."
            )
            file_matches = searcher.search_pdf("spine", pdf_path)

        if file_matches:
            # Add the best match from this file
            best_match = file_matches[0]

            # We need to convert PageMatch to SearchResult
            # Get metadata first
            metadata = searcher.scanner.get_pdf_metadata(pdf_path)

            search_result = SearchResult(
                pdf_path=pdf_path,
                book_series=metadata.book_series,
                book_title=metadata.book_title,
                chapter_number=metadata.chapter_number,
                chapter_title=metadata.chapter_title,
                page_number=best_match.page_number,
                match_text=best_match.match_text,
                context=best_match.context,
            )

            results.append(search_result)
            print(f"  Added: {pdf_path.name} (Page {best_match.page_number})")
        else:
            print(f"  ❌ Could not find ANY relevant content in {pdf_path.name}")

    print(f"\nFound {len(results)} results from {len(all_pdfs)} files.")

    if not results:
        print("❌ No results found.")
        return None

    # Extract pages
    print("\nExtracting relevant pages...")
    extracted_sources = extract_relevant_pages(
        results=results, output_dir=SOURCES_DIR, context_pages=1, database=db
    )

    print(f"✅ Extracted {len(extracted_sources)} source PDFs.")

    # Generate Manifest
    print("\nGenerating manifest...")
    generate_manifest(
        topic="Lumbar Microdiskectomy",
        sources=extracted_sources,
        output_path=MANIFEST_PATH,
        search_query=query,
        search_mode="keyword",
    )

    print(f"✅ Manifest created at {MANIFEST_PATH}")
    return extracted_sources


async def run_synthesis():
    print("\n" + "=" * 50)
    print("STEP 2: Synthesis")
    print("=" * 50)

    # Construct command
    # neurosynth run 'Lumbar Microdiskectomy' --sources ... --manifest ... --output ...

    python_exe = sys.executable

    # We need to ensure the python path includes the src directories
    env = os.environ.copy()
    env["PYTHONPATH"] = (
        f"{project_root}/src:{project_root}/reference-library:{env.get('PYTHONPATH', '')}"
    )

    cmd = [
        python_exe,
        "-m",
        "neurosynth.cli",
        "run",
        "Lumbar Microdiskectomy",
        "--sources",
        str(SOURCES_DIR),
        "--manifest",
        str(MANIFEST_PATH),
        "--output",
        str(SYNTHESIS_DIR),
    ]

    print(f"Running command: {' '.join(cmd)}")

    process = await asyncio.create_subprocess_exec(
        *cmd, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )

    # Stream output
    while True:
        line = await process.stdout.readline()
        if not line:
            break
        print(line.decode().strip())

    stderr_data = await process.stderr.read()
    if stderr_data:
        print("\nErrors:")
        print(stderr_data.decode())

    await process.wait()

    if process.returncode == 0:
        print("\n✅ Synthesis completed successfully")
    else:
        print("\n❌ Synthesis failed")


if __name__ == "__main__":
    setup()
    sources = run_search_and_extract()
    if sources:
        asyncio.run(run_synthesis())
