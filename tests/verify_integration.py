
import sys
import shutil
from pathlib import Path

# Add src to path
sys.path.append(str(Path(__file__).parent.parent / "reference-library"))
sys.path.append(str(Path(__file__).parent.parent))

from src.search.pdf_searcher import PDFSearcher
from src.utils.library_scanner import LibraryScanner
from src.search.semantic_searcher import SemanticSearcher
from src.search.master_index import get_master_index
from src.cache.database import Database
from src.integration.neurosynth_bridge import NeuroSynthBridge

def verify_integration():
    print("Starting Phase 2 Integration Verification...")

    # Setup paths
    library_path = Path("/Users/ramihatoum/neurosynth/real_synthesis_output/temp_library")
    db_path = Path("/Users/ramihatoum/neurosynth/neurosynth.db")
    
    # Initialize components
    print("Initializing components...")
    db = Database(db_path)
    scanner = LibraryScanner(library_path, db)
    semantic = SemanticSearcher(db)
    master_index = get_master_index()
    
    pdf_searcher = PDFSearcher(
        library_path=library_path,
        database=db
    )
    
    # Initialize Bridge
    bridge = NeuroSynthBridge(
        database=db,
        pdf_searcher=pdf_searcher
    )
    
    # Test Synthesis with Search
    topic = "Integration Test Lumbar"
    query = "lumbar discectomy technique"
    
    print(f"Testing synthesis for query: '{query}'")
    
    # Clean up previous test output
    output_dir = Path.home() / "Documents" / "NeuroSynth" / "projects" / "integration_test_lumbar"
    if output_dir.exists():
        shutil.rmtree(output_dir)
        
    # Run synthesize (passing NO results, so it must search)
    result = bridge.synthesize(
        topic=topic,
        results=[],  # Empty results -> trigger search
        search_query=query,
        search_mode="hybrid"
    )
    
    if result.success:
        print("Integration Test Passed!")
        print(f"Output: {result.output_path}")
    else:
        print(f"Integration Test Failed (Expected if CLI missing): {result.error}")
        
    # Verify manifest (Check regardless of CLI success)
    manifest_path = output_dir / "manifest.json"
    if manifest_path.exists():
        print("Manifest created successfully.")
        import json
        with open(manifest_path) as f:
            data = json.load(f)
            sources = data.get("sources", [])
            print(f"Extracted {len(sources)} sources.")
            
            # Check for enhanced metadata
            has_metadata = any(s.get("matched_sections") for s in sources)
            if has_metadata:
                print("Enhanced metadata (matched_sections) found in manifest.")
            else:
                print("No enhanced metadata found in manifest!")
    else:
        print("Manifest NOT found!")

if __name__ == "__main__":
    verify_integration()
