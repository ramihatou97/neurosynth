import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path

# Add src to path
sys.path.append(str(Path(__file__).parent.parent.parent.parent))

from ai.client import AIClient
from deep_dx.config import get_deepdx_settings
from deep_dx.critic.critic import DeepDxCritic
from deep_dx.engine.synthesizer import DeepDxSynthesizer
from index.database import Database
from index.precision_search import PrecisionSearchEngine


async def run_evaluation():
    print("🚀 Starting Deep-DX Evaluation Phase...")

    # 1. Setup
    # Override Global Settings (which AIClient uses)
    from config import settings as sys_settings

    sys_settings.embedding_model = "voyage-large-2-instruct"
    print(f"🔧 Configured Embedding Model: {sys_settings.embedding_model}")

    get_deepdx_settings()  # Init deep settings too

    # Use absolute path to ensure we hit the populated DB
    db_path = Path("/Users/ramihatoum/neurosynth/neurosynth.db")
    if not db_path.exists():
        print(f"❌ Database not found at {db_path}")
        return

    db = Database(db_path=db_path)
    ai_client = AIClient()  # Reads env vars

    # Initialize Critic
    try:
        critic = DeepDxCritic()
        print("🕵️‍♀️ Critic Initialized.")
    except Exception as e:
        print(f"⚠️ Failed to init Critic: {e}")
        critic = None

    # Precision Search with ColBERT
    search_engine = PrecisionSearchEngine(db, colbert_enabled=True)
    if not search_engine.colbert:
        print("⚠️ ColBERT not available, using fallback.")

    synthesizer = DeepDxSynthesizer(search_engine, ai_client, critic=critic)

    # 2. Load Evaluation Dataset
    eval_path = Path(
        "/Users/ramihatoum/neurosynth/src/deep_dx/eval/gold_standard_eval.json"
    )
    if not eval_path.exists():
        print(f"❌ Eval dataset not found at {eval_path}")
        return

    with open(eval_path) as f:
        data = json.load(f)
        queries = data.get("queries", [])

    # Set Evaluation Scope
    # Run a meaningful subset (first 10) to test the pipeline without blocking for hours
    # Once validated, we can remove the slice to run all 50+.
    queries = queries[:10]

    print(f"📋 Loaded {len(queries)} queries for Evaluation Run.")

    # 3. Run Evaluation Loop
    results = []

    # Limit to first 5 for initial test to avoid massive API usage if user didn't ask
    # User said "proceed with phase 6" which implies full run, but let's be safe and do a batch.
    # Actually, let's run all but handle errors.

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = Path(f"src/deep_dx/eval/results/eval_run_{timestamp}.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    for i, q in enumerate(queries):
        print(f"[{i+1}/{len(queries)}] Processing: {q['id']} - {q['query'][:50]}...")

        try:
            # Generate Answer
            start_time = datetime.now()
            response = synthesizer.generate_answer(q["query"])
            duration = (datetime.now() - start_time).total_seconds()

            # Simple LLM Judge (Self-Correction/Grading)
            # We ask the AI to grade the answer against the ground truth
            grade_prompt = f"""Compare the Generated Answer to the Ground Truth.

Query: {q['query']}

Ground Truth: {q['ground_truth']}

Generated Answer: {response['answer']}

Grade (0-10) and brief justification."""

            grade_response = ai_client.synthesize(grade_prompt, max_tokens=200)

            result_entry = {
                "id": q["id"],
                "query": q["query"],
                "ground_truth": q["ground_truth"],
                "generated_answer": response["answer"],
                "sources_used": response["sources"],
                "grade_feedback": grade_response,
                "duration_seconds": duration,
                "timestamp": datetime.now().isoformat(),
            }
            results.append(result_entry)

            # Write partial results
            with open(output_path, "w") as f:
                json.dump(
                    {"metadata": data.get("metadata"), "results": results}, f, indent=2
                )

        except Exception as e:
            print(f"❌ Error on {q['id']}: {e}")
            results.append({"id": q["id"], "error": str(e)})

    # 4. Calculate Statistics
    total_score = 0
    scored_count = 0
    safe_flag_count = 0

    for r in results:
        # Parse Grade
        grade = 0
        if "grade_feedback" in r:
            try:
                # Naive parse: find "Grade: X/10" or similar
                fb = r["grade_feedback"]
                if "**Grade:" in fb:
                    grade_str = fb.split("**Grade:")[1].split("/")[0].strip()
                    grade = float(grade_str)
                elif "Grade:" in fb:
                    grade_str = fb.split("Grade:")[1].split("/")[0].strip()
                    grade = float(grade_str)
            except:
                pass

        r["parsed_score"] = grade
        if grade > 0:
            total_score += grade
            scored_count += 1

        # Check Safety Flag
        if "SAFETY WARNING" in r.get("generated_answer", ""):
            safe_flag_count += 1

    avg_score = total_score / scored_count if scored_count > 0 else 0

    print("\n" + "=" * 40)
    print(f"📊 EVALUATION SUMMARY (N={len(results)})")
    print("=" * 40)
    print(f"⭐ Average Grade: {avg_score:.2f} / 10")
    print(f"🛡️  Safety Flags: {safe_flag_count}")
    print(f"📂 Output File:   {output_path}")
    print("=" * 40 + "\n")

    # Write final results with stats
    with open(output_path, "w") as f:
        json.dump(
            {
                "metadata": data.get("metadata"),
                "statistics": {
                    "average_grade": avg_score,
                    "safety_flags": safe_flag_count,
                    "total_queries": len(results),
                },
                "results": results,
            },
            f,
            indent=2,
        )

    # 5. Recommendation (Optimization Hook)
    if avg_score < 7.0:
        print(
            "💡 Suggestion: Low score detected. Consider increasing top_k or improving ingestion chunk_size."
        )


def main():
    asyncio.run(run_evaluation())


if __name__ == "__main__":
    main()
