import asyncio
import json
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent.parent.parent))

from ai.client import AIClient
from deep_dx.config import get_deepdx_settings
from deep_dx.critic.critic import DeepDxCritic
from deep_dx.engine.synthesizer import DeepDxSynthesizer
from index.database import Database
from index.precision_search import PrecisionSearchEngine


async def run_target_test():
    print("🎯 Running Targeted Refinement Test (Q011, Q031, Q061)")

    db = Database(db_path=Path("neurosynth.db"))
    ai_client = AIClient()
    critic = None
    try:
        critic = DeepDxCritic()
    except:
        pass

    search_engine = PrecisionSearchEngine(db, colbert_enabled=True)
    synthesizer = DeepDxSynthesizer(search_engine, ai_client, critic=critic)

    # Load Ground Truths
    eval_path = Path("src/deep_dx/eval/gold_standard_eval.json")
    with open(eval_path) as f:
        data = json.load(f)
        all_queries = {q["id"]: q for q in data["queries"]}

    targets = ["Q011", "Q031", "Q061"]

    for q_id in targets:
        q_data = all_queries.get(q_id)
        if not q_data:
            continue

        print(f"\n🧪 Testing {q_id}: {q_data['query'][:50]}...")

        # Configure search (force global settings check)
        # run eval
        response = synthesizer.generate_answer(q_data["query"])

        # Grade it
        grade_prompt = f"""Compare Generated vs Ground Truth.
Query: {q_data['query']}
Ground Truth: {q_data['ground_truth']}
Generated: {response['answer']}
Grade (0-10) and justification."""

        grade = ai_client.synthesize(grade_prompt, max_tokens=200)
        print(f"📝 Answer: {response['answer'][:200]}...")
        print(f"⚖️  Grade Feedback:\n{grade}")
        print("-" * 50)


if __name__ == "__main__":
    asyncio.run(run_target_test())
