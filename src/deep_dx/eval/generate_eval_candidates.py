#!/usr/bin/env python3
"""
Deep-Dx Evaluation Candidate Generator

Generates candidate queries from your neurosurgical PDF library using Claude.
These are CANDIDATES - you must review and curate them before using as gold standard.

Usage:
    python generate_eval_candidates.py --num-queries 150
    # Review generated_candidates.json
    # Keep best 100, edit as needed
    # Rename to gold_standard_eval.json
"""

import argparse
import json
import random
from datetime import datetime
from pathlib import Path
from typing import Dict, List

try:
    from anthropic import Anthropic
except ImportError:
    print("❌ Error: anthropic package not installed")
    print("   Run: pip install anthropic")
    exit(1)

from neurosynth.config import get_settings

# Query generation prompt
QUERY_GENERATION_PROMPT = """You are a senior neurosurgeon creating evaluation questions for a clinical retrieval system.

Read the following text chunk from a neurosurgical reference:

---
TEXT CHUNK:
{text}
---

TASK:
Generate ONE high-quality clinical question based STRICTLY on this text.

REQUIREMENTS:
1. The question must be answerable from the text provided
2. It should be a question you would actually ask in clinical practice
3. The answer should require specific details (not just yes/no)
4. Use natural language (how a surgeon would ask, not academic style)

QUESTION CATEGORIES (choose the most appropriate):
- Spatial: "What is the position of X relative to Y?"
- Factual: "What is the blood supply of X?"
- Procedural: "How do you identify X during Y approach?"
- Contraindication: "When should you NOT use X?"
- Comparative: "X vs Y for Z?"

OUTPUT FORMAT (JSON only, no markdown):
{{
    "query": "The question text",
    "ground_truth": "The precise answer from the text (4-8 sentences with specific details)",
    "query_type": "spatial|factual|procedural|contraindication|comparative",
    "difficulty": "easy|medium|hard",
    "safety_critical": true|false,
    "source_excerpt": "Exact quote from text that supports the answer",
    "reasoning": "Brief explanation of why this is a good evaluation question"
}}

IMPORTANT:
- Make the ground_truth answer DETAILED with specific measurements, percentages, criteria
- Mark safety_critical=true if wrong answer could lead to patient harm
- difficulty=easy if answer is explicit in one place, medium if requires synthesis, hard if requires inference
"""


def load_pdf_chunks(pdf_path: Path, num_chunks: int = 10) -> list[dict[str, str]]:
    """
    Extract text chunks from PDF using PyMuPDF.

    Args:
        pdf_path: Path to PDF file
        num_chunks: Number of chunks to extract

    Returns:
        List of dicts with 'text' and 'source' keys
    """
    try:
        import fitz  # PyMuPDF
    except ImportError:
        print("❌ Error: PyMuPDF not installed")
        print("   Run: pip install PyMuPDF")
        exit(1)

    chunks = []
    try:
        doc = fitz.open(pdf_path)
        total_pages = len(doc)

        # Sample pages evenly across the document
        sample_pages = sorted(
            random.sample(range(total_pages), min(num_chunks, total_pages))
        )

        for page_num in sample_pages:
            page = doc[page_num]
            text = page.get_text()

            # Skip if page has very little text
            if len(text.strip()) < 200:
                continue

            # Take first ~500 words
            words = text.split()[:500]
            chunk_text = " ".join(words)

            chunks.append(
                {
                    "text": chunk_text,
                    "source": f"{pdf_path.name}:p{page_num + 1}",
                    "page": page_num + 1,
                }
            )

        doc.close()
        return chunks

    except Exception as e:
        print(f"⚠️  Error reading {pdf_path.name}: {e}")
        return []


def generate_query_from_chunk(
    client: Anthropic, chunk: dict[str, str], model: str
) -> dict | None:
    """
    Generate a candidate evaluation query from a text chunk using Claude.

    Args:
        client: Anthropic client
        chunk: Dict with 'text' and 'source' keys
        model: Claude model to use

    Returns:
        Query dict or None if generation fails
    """
    try:
        prompt = QUERY_GENERATION_PROMPT.format(text=chunk["text"])

        response = client.messages.create(
            model=model,
            max_tokens=1500,
            temperature=0.7,  # Some creativity for diverse questions
            messages=[{"role": "user", "content": prompt}],
        )

        # Extract JSON from response
        content = response.content[0].text

        # Parse JSON (Claude might wrap it in ```json blocks)
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]

        query_data = json.loads(content.strip())

        # Add metadata
        query_data["source_file"] = chunk["source"]
        query_data["source_page"] = chunk.get("page", 0)
        query_data["generated_date"] = datetime.now().isoformat()
        query_data["negation_query"] = any(
            word in query_data["query"].lower()
            for word in ["not", "avoid", "contraindication", "never"]
        )
        query_data["spatial_query"] = any(
            word in query_data["query"].lower()
            for word in [
                "anterior",
                "posterior",
                "medial",
                "lateral",
                "superior",
                "inferior",
                "above",
                "below",
            ]
        )

        return query_data

    except json.JSONDecodeError:
        print(f"⚠️  Failed to parse JSON from response for {chunk['source']}")
        return None
    except Exception as e:
        print(f"⚠️  Error generating query: {e}")
        return None


def main():
    parser = argparse.ArgumentParser(description="Generate evaluation query candidates")
    parser.add_argument(
        "--num-queries",
        type=int,
        default=150,
        help="Number of candidate queries to generate (default: 150)",
    )
    parser.add_argument(
        "--pdf-dir",
        type=Path,
        help="Directory containing PDFs (default: from NeuroSynth config)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("generated_candidates.json"),
        help="Output file for generated candidates",
    )
    parser.add_argument(
        "--model",
        type=str,
        default="claude-sonnet-4-20250514",
        help="Claude model to use",
    )
    args = parser.parse_args()

    # Get PDF directory from NeuroSynth config if not specified
    if args.pdf_dir is None:
        settings = get_settings()
        args.pdf_dir = settings.sources_dir

    # Check if PDF directory exists
    if not args.pdf_dir.exists():
        print(f"❌ PDF directory not found: {args.pdf_dir}")
        print("\nOptions:")
        print("  1. Add PDFs to the NeuroSynth sources directory:")
        print(f"     cp your_pdfs/*.pdf {args.pdf_dir}/")
        print("  2. Specify a different directory:")
        print("     python generate_eval_candidates.py --pdf-dir /path/to/pdfs")
        exit(1)

    # Find all PDFs
    pdf_files = list(args.pdf_dir.glob("*.pdf"))
    if not pdf_files:
        print(f"❌ No PDF files found in {args.pdf_dir}")
        exit(1)

    print(f"📚 Found {len(pdf_files)} PDF files")
    print(f"🎯 Target: {args.num_queries} candidate queries\n")

    # Initialize Anthropic client
    settings = get_settings()
    if not settings.anthropic_api_key:
        print("❌ Error: ANTHROPIC_API_KEY not set")
        print("   Set it in your .env file or environment")
        exit(1)

    client = Anthropic(api_key=settings.anthropic_api_key)

    # Generate queries
    candidates = []
    chunks_per_pdf = max(1, args.num_queries // len(pdf_files))

    for pdf_idx, pdf_path in enumerate(pdf_files, 1):
        print(f"[{pdf_idx}/{len(pdf_files)}] Processing {pdf_path.name}...")

        # Extract chunks from this PDF
        chunks = load_pdf_chunks(pdf_path, num_chunks=chunks_per_pdf)
        if not chunks:
            continue

        # Generate queries from chunks
        for chunk in chunks:
            if len(candidates) >= args.num_queries:
                break

            query_data = generate_query_from_chunk(client, chunk, args.model)
            if query_data:
                # Add ID
                query_data["id"] = f"Q{len(candidates) + 1:03d}"
                candidates.append(query_data)
                print(f"  ✓ Generated: {query_data['query'][:60]}...")

        if len(candidates) >= args.num_queries:
            break

    # Create output structure
    output = {
        "version": "1.0.0-candidates",
        "metadata": {
            "generated_date": datetime.now().isoformat(),
            "total_queries": len(candidates),
            "source_directory": str(args.pdf_dir),
            "model_used": args.model,
            "notes": "THESE ARE CANDIDATES - Review and curate before using as gold standard",
        },
        "queries": candidates,
    }

    # Save
    args.output.write_text(json.dumps(output, indent=2))

    print(f"\n✅ Generated {len(candidates)} candidate queries")
    print(f"📄 Saved to: {args.output}")
    print("\n🔍 NEXT STEPS:")
    print("  1. Review generated_candidates.json")
    print("  2. Edit/fix any incorrect queries")
    print("  3. Select best 100 queries")
    print("  4. Rename to gold_standard_eval.json")
    print(
        "  5. Run validation: python validate_eval_dataset.py gold_standard_eval.json"
    )

    # Print distribution
    print("\n📊 Query Type Distribution:")
    type_counts = {}
    for q in candidates:
        qtype = q["query_type"]
        type_counts[qtype] = type_counts.get(qtype, 0) + 1

    for qtype, count in sorted(type_counts.items()):
        print(f"  {qtype:20s}: {count}")


if __name__ == "__main__":
    main()
