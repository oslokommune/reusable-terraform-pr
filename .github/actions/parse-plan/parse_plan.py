"""Classify a Terraform plan into a changes value.

Reads the JSON representation of a plan (`terraform show -json <planfile>`)
and prints the most severe kind of change it contains. Covers resource and
output changes. Unrankable verbs are treated as "any-changes", the most
severe value. An unloadable plan or unsupported plan format exits non-zero:
those mean the pipeline is broken, not that the plan is dangerous.

Usage:
  python3 parse_plan.py --plan-json-path <path>

Output: prints the changes value to stdout.
"""

import argparse
import json
import sys

def classify(
    plan: dict,
    resource_verbs: frozenset[str] = frozenset(
        {"no-op", "read", "create", "update", "delete", "forget"}
    ),
    output_verbs: frozenset[str] = frozenset({"no-op", "create", "update", "delete"}),
) -> str:
    """Checked in severity order, first match wins:
    any-changes -> no-destroy -> additive -> no-changes
    """
    # Every action verb in the plan; a replace contributes both "delete" and "create"
    actions = {
        verb
        for change in plan.get("resource_changes") or []
        for verb in change["change"]["actions"]
    }
    output_actions = {
        verb
        for change in (plan.get("output_changes") or {}).values()
        for verb in change["actions"]
    }

    # Resource: unrankable verb (e.g. forget) -> any-changes
    if actions - resource_verbs:
        print(
            f"Treating unrankable resource verbs as any-changes: {sorted(actions - resource_verbs)}",
            file=sys.stderr,
        )
        return "any-changes"

    # Output: unrankable verb -> any-changes
    if output_actions - output_verbs:
        print(
            f"Treating unrankable output verbs as any-changes: {sorted(output_actions - output_verbs)}",
            file=sys.stderr,
        )
        return "any-changes"

    if {"delete", "forget"} & actions or "delete" in output_actions:
        return "any-changes"

    if "update" in actions or "update" in output_actions:
        return "no-destroy"

    if "create" in actions or "create" in output_actions:
        return "additive"

    # Only no-op/read verbs and untouched outputs remain -> no-changes
    if actions <= {"no-op", "read"} and output_actions <= {"no-op"}:
        return "no-changes"

    # Fail safe: anything unmatched is treated as the most severe value
    print("Treating unclassified changes as any-changes", file=sys.stderr)
    return "any-changes"

def verify_version(plan: dict, supported_major: str = "1") -> bool:
    # format_version is "MAJOR.MINOR"; minor will not change json structure, see
    # https://developer.hashicorp.com/terraform/internals/json-format#format-summary
    return str(plan.get("format_version", "")).split(".")[0] == supported_major


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Classify a Terraform plan JSON into a changes value"
    )
    parser.add_argument(
        "--plan-json-path",
        required=True,
        help="Path to the output of `terraform show -json <planfile>`",
    )
    args = parser.parse_args()

    # An unloadable plan means the pipeline is broken: fail instead of guessing
    try:
        with open(args.plan_json_path) as f:
            plan = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        sys.exit(f"Could not read plan: {e}")

    # An unsupported plan format means this parser is outdated: fail instead of guessing
    if not verify_version(plan):
        sys.exit(f"Unsupported format_version {plan.get('format_version')!r}, update parse-plan")

    print(classify(plan))
