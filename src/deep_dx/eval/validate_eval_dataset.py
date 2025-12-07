#!/usr/bin/env python3
"""
Deep-Dx Evaluation Dataset Validator

Validates structure, distribution, and quality of evaluation dataset.

Usage:
    python validate_eval_dataset.py gold_standard_eval.json
"""

import json
import sys
from collections import Counter
from pathlib import Path


def validate_dataset(filepath: Path) -> bool:
    """Validate evaluation dataset structure and distribution"""

    # Load dataset
    try:
        with open(filepath, 'r') as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"❌ Error: File not found: {filepath}")
        return False
    except json.JSONDecodeError as e:
        print(f"❌ Error: Invalid JSON: {e}")
        return False

    # Check required top-level fields
    if 'queries' not in data:
        print("❌ Error: Missing 'queries' field")
        return False

    queries = data['queries']
    total = len(queries)

    # Print header
    print(f"\n{'='*60}")
    print(f"DEEP-DX EVALUATION DATASET VALIDATION")
    print(f"{'='*60}\n")
    print(f"File: {filepath}")
    print(f"Total queries: {total}")
    print(f"Target: 100 (you have {total - 100:+d})\n")

    # Query type distribution
    print("QUERY TYPE DISTRIBUTION")
    print("-" * 40)
    type_counts = Counter(q.get('query_type', 'MISSING') for q in queries)
    targets = {
        'factual': 20,
        'procedural': 20,
        'contraindication': 15,
        'spatial': 15,
        'comparative': 10
    }

    all_types_ok = True
    for qtype, target in targets.items():
        actual = type_counts.get(qtype, 0)
        delta = actual - target
        status = "✓" if abs(delta) <= 2 else "⚠️"
        if abs(delta) > 5:
            all_types_ok = False
            status = "❌"
        print(f"  {qtype:20s}: {actual:3d} / {target:3d} ({delta:+3d}) {status}")

    if 'MISSING' in type_counts:
        print(f"  {'MISSING TYPE':20s}: {type_counts['MISSING']:3d}        ❌")
        all_types_ok = False

    # Difficulty distribution
    print("\nDIFFICULTY DISTRIBUTION")
    print("-" * 40)
    diff_counts = Counter(q.get('difficulty', 'MISSING') for q in queries)
    easy_target = int(total * 0.3)
    medium_target = int(total * 0.5)
    hard_target = int(total * 0.2)

    print(f"  Easy:   {diff_counts.get('easy', 0):3d} (target: ~{easy_target})")
    print(f"  Medium: {diff_counts.get('medium', 0):3d} (target: ~{medium_target})")
    print(f"  Hard:   {diff_counts.get('hard', 0):3d} (target: ~{hard_target})")

    if 'MISSING' in diff_counts:
        print(f"  MISSING: {diff_counts['MISSING']:3d} ❌")

    # Safety-critical count
    safety_count = sum(1 for q in queries if q.get('safety_critical', False))
    safety_pct = (safety_count / total * 100) if total > 0 else 0
    safety_status = "✓" if safety_pct >= 30 else "⚠️" if safety_pct >= 25 else "❌"

    print(f"\nSAFETY-CRITICAL QUERIES")
    print("-" * 40)
    print(f"  Count: {safety_count} ({safety_pct:.1f}%) {safety_status}")
    print(f"  Target: ≥30%")

    # Special query flags
    negation_count = sum(1 for q in queries if q.get('negation_query', False))
    spatial_count = sum(1 for q in queries if q.get('spatial_query', False))
    adversarial_count = sum(1 for q in queries if q.get('adversarial', False))

    adversarial_status = "✓" if adversarial_count >= 10 else "⚠️"

    print(f"\nSPECIAL QUERY TYPES")
    print("-" * 40)
    print(f"  Negation queries:    {negation_count}")
    print(f"  Spatial queries:     {spatial_count}")
    print(f"  Adversarial queries: {adversarial_count} (target: ≥10) {adversarial_status}")

    # Quality checks
    print(f"\nQUALITY CHECKS")
    print("-" * 40)

    issues = []

    # Check for required fields
    missing_fields = {}
    required_fields = ['id', 'query', 'ground_truth', 'query_type', 'difficulty',
                      'safety_critical']

    for q in queries:
        q_id = q.get('id', 'UNKNOWN')
        for field in required_fields:
            if field not in q:
                if field not in missing_fields:
                    missing_fields[field] = []
                missing_fields[field].append(q_id)

    if missing_fields:
        for field, ids in missing_fields.items():
            print(f"  ❌ Missing '{field}' in: {', '.join(ids[:5])}")
            if len(ids) > 5:
                print(f"     ... and {len(ids) - 5} more")
            issues.append(f"missing_{field}")
    else:
        print(f"  ✓  All required fields present")

    # Check ground truth length
    short_ground_truth = [q['id'] for q in queries
                          if len(q.get('ground_truth', '')) < 100]
    if short_ground_truth:
        print(f"  ⚠️  Short ground truth (<100 chars): {', '.join(short_ground_truth[:5])}")
        if len(short_ground_truth) > 5:
            print(f"     ... and {len(short_ground_truth) - 5} more")
        issues.append("short_ground_truth")
    else:
        print(f"  ✓  All ground truth answers are detailed")

    # Check query length
    vague_queries = [q['id'] for q in queries
                     if len(q.get('query', '')) < 20]
    if vague_queries:
        print(f"  ⚠️  Vague queries (<20 chars): {', '.join(vague_queries)}")
        issues.append("vague_queries")
    else:
        print(f"  ✓  All queries are specific")

    # ID uniqueness
    ids = [q.get('id', f'MISSING_{i}') for i, q in enumerate(queries)]
    duplicate_ids = list(set([id for id in ids if ids.count(id) > 1]))
    if duplicate_ids:
        print(f"  ❌ Duplicate IDs: {', '.join(duplicate_ids)}")
        issues.append("duplicate_ids")
    else:
        print(f"  ✓  All IDs are unique")

    # Check ID format (Q001, Q002, etc.)
    import re
    invalid_ids = [id for id in ids if not re.match(r'^Q\d{3}$', id)]
    if invalid_ids:
        print(f"  ⚠️  Invalid ID format (should be Q001, Q002, ...): {', '.join(invalid_ids[:5])}")
        if len(invalid_ids) > 5:
            print(f"     ... and {len(invalid_ids) - 5} more")
    else:
        print(f"  ✓  All IDs follow Q### format")

    print(f"\n{'='*60}\n")

    # Final verdict
    critical_issues = (
        'duplicate_ids' in issues or
        'missing_id' in issues or
        'missing_query' in issues or
        'missing_ground_truth' in issues or
        safety_pct < 25 or
        total < 80 or
        not all_types_ok
    )

    minor_issues = (
        'short_ground_truth' in issues or
        adversarial_count < 10 or
        abs(total - 100) > 10
    )

    if critical_issues:
        print("❌ CRITICAL ISSUES FOUND")
        print("\nFix these issues before proceeding:")
        if 'duplicate_ids' in issues:
            print("  • Fix duplicate IDs")
        if any(f'missing_{field}' in issues for field in required_fields):
            print("  • Add missing required fields")
        if safety_pct < 25:
            print(f"  • Increase safety-critical queries (currently {safety_pct:.1f}%, need ≥30%)")
        if total < 80:
            print(f"  • Add more queries (currently {total}, need ≥80)")
        if not all_types_ok:
            print("  • Rebalance query type distribution")
        return False

    elif minor_issues:
        print("⚠️  MINOR ISSUES FOUND")
        print("\nDataset is usable but could be improved:")
        if 'short_ground_truth' in issues:
            print(f"  • Expand ground truth answers for {len(short_ground_truth)} queries")
        if adversarial_count < 10:
            print(f"  • Add more adversarial queries (currently {adversarial_count}, target ≥10)")
        if abs(total - 100) > 10:
            print(f"  • Adjust total to ~100 queries (currently {total})")
        print("\n✓ You can proceed to Phase 1, but consider addressing these issues")
        return True

    else:
        print("✅ DATASET READY")
        print("\nNo issues found. Proceed to Phase 1 (ColBERT indexing)")
        return True


def main():
    if len(sys.argv) < 2:
        print("Usage: python validate_eval_dataset.py <path_to_dataset.json>")
        print("\nExample:")
        print("  python validate_eval_dataset.py gold_standard_eval.json")
        sys.exit(1)

    filepath = Path(sys.argv[1])

    if not filepath.exists():
        print(f"❌ Error: File not found: {filepath}")
        sys.exit(1)

    success = validate_dataset(filepath)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
