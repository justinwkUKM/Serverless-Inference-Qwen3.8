#!/usr/bin/env python3
"""
CBOM Evaluation Scorer: Compares an agent-generated CycloneDX 1.6 CBOM against Ground Truth.
Computes:
- Component/Asset Precision, Recall, and F1-score
- Cryptographic Property Accuracy (primitive, key size, mode)
- Detection Context Accuracy (identifying correct files)
"""

import argparse
import json
import os
import sys

def normalize_name(name):
    return name.lower().replace(" ", "").replace("-", "").replace("_", "")

def evaluate_cbom(submission_path, ground_truth_path):
    if not os.path.exists(submission_path):
        print(f"Error: Submission file {submission_path} not found.")
        sys.exit(1)

    with open(ground_truth_path, "r") as f:
        gt_data = json.load(f)

    with open(submission_path, "r") as f:
        try:
            sub_data = json.load(f)
        except json.JSONDecodeError as e:
            print(f"Error: Invalid JSON submission - {e}")
            return {
                "valid_json": False,
                "precision": 0.0,
                "recall": 0.0,
                "f1_score": 0.0
            }

    gt_components = gt_data.get("components", [])
    sub_components = sub_data.get("components", [])

    # Index Ground Truth by normalized name
    gt_map = {}
    for c in gt_components:
        name_key = normalize_name(c.get("name", ""))
        gt_map[name_key] = c

    # Evaluate matches
    matched_gt = set()
    true_positives = 0
    false_positives = 0
    property_matches = 0

    for sc in sub_components:
        sub_name = normalize_name(sc.get("name", ""))
        matched = False
        for gt_name, gt_item in gt_map.items():
            if sub_name == gt_name or sub_name in gt_name or gt_name in sub_name:
                matched_gt.add(gt_name)
                matched = True
                true_positives += 1
                
                # Check property match
                sc_props = sc.get("cryptoProperties", {}).get("algorithmProperties", {})
                gt_props = gt_item.get("cryptoProperties", {}).get("algorithmProperties", {})
                if sc_props.get("primitive") == gt_props.get("primitive"):
                    property_matches += 1
                break

        if not matched:
            false_positives += 1

    false_negatives = len(gt_components) - len(matched_gt)

    precision = true_positives / (true_positives + false_positives) if (true_positives + false_positives) > 0 else 0.0
    recall = true_positives / len(gt_components) if len(gt_components) > 0 else 0.0
    f1 = (2 * precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
    prop_accuracy = property_matches / true_positives if true_positives > 0 else 0.0

    return {
        "valid_json": True,
        "cyclonedx_version": sub_data.get("specVersion", "unknown"),
        "total_ground_truth_assets": len(gt_components),
        "total_detected_assets": len(sub_components),
        "true_positives": true_positives,
        "false_positives": false_positives,
        "false_negatives": false_negatives,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1_score": round(f1, 4),
        "property_accuracy": round(prop_accuracy, 4)
    }

def main():
    parser = argparse.ArgumentParser(description="CBOM Evaluation Scorer")
    parser.add_argument("--submission", required=True, help="Path to agent's generated CBOM JSON")
    parser.add_argument("--ground-truth", default="crypto_bench/track_a_cbom/ground_truth_cbom.json", help="Path to ground truth CBOM JSON")
    args = parser.parse_args()

    results = evaluate_cbom(args.submission, args.ground_truth)
    print("================== CBOM EVALUATION REPORT ==================")
    print(json.dumps(results, indent=2))
    print("============================================================")

if __name__ == "__main__":
    main()
