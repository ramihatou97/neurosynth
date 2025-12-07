
import json
import argparse
from pathlib import Path
from neurosynth.config import get_settings
from anthropic import Anthropic


PROMPTS = {
    'adversarial': """TASK: Generate 10 TRICK/ADVERSARIAL neurosurgery questions.
OUTPUT FORMAT: [{"query": "...", "ground_truth": "...", "query_type": "safety", "difficulty": "hard", "safety_critical": true, "adversarial": true}]""",
    'contraindication': """TASK: Generate 10 CONTRAINDICATION questions. "When is X NOT allowed?".
OUTPUT FORMAT: [{"query": "...", "ground_truth": "...", "query_type": "contraindication", "difficulty": "medium", "safety_critical": true, "negation_query": true}]""",
    'spatial': """TASK: Generate 10 SPATIAL ANATOMY questions. "What is medial to X?".
OUTPUT FORMAT: [{"query": "...", "ground_truth": "...", "query_type": "spatial", "difficulty": "hard", "safety_critical": false, "spatial_query": true}]""",
    'comparative': """TASK: Generate 10 COMPARATIVE questions. "X vs Y for condition Z".
OUTPUT FORMAT: [{"query": "...", "ground_truth": "...", "query_type": "comparative", "difficulty": "medium", "safety_critical": true, "reasoning": "Comparison of options"}]"""}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--num", type=int, default=10)
    parser.add_argument("--type", type=str, default="adversarial", choices=['adversarial', 'contraindication', 'spatial', 'comparative'])
    args = parser.parse_args()

    settings = get_settings()
    if not settings.anthropic_api_key:
        print("❌ No API Key")
        return

    client = Anthropic(api_key=settings.anthropic_api_key)
    prompt = PROMPTS[args.type]

    print(f"🎯 Generating {args.num} {args.type} queries...")

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}]
    )

    content = response.content[0].text
    if "```json" in content:
        content = content.split("```json")[1].split("```")[0]
    
    try:
        queries = json.loads(content)
        # Output file specific to type
        filename = f"{args.type}_candidates.json"
        
        # Load existing if any
        existing = []
        if Path(filename).exists():
            with open(filename, 'r') as f:
                d = json.load(f)
                existing = d.get('queries', [])
        
        existing.extend(queries)
        
        with open(filename, 'w') as f:
            json.dump({"queries": existing}, f, indent=2)
            
        print(f"✅ Saved {len(queries)} {args.type} queries to {filename}")
        
    except Exception as e:
        print(f"❌ Failed: {e}")


if __name__ == "__main__":
    main()
