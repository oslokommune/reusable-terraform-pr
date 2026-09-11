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


def classify(plan: dict) -> str:
    """Checks least severe first; the first tier that covers every verb in
    the plan wins. Anything not covered is the catch-all "any-changes".
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

    # NOTE: Order matters: tiers are nested, least severe tier is checked first
    if actions <= {"no-op", "read"} and output_actions <= {"no-op"}:
        return "no-changes"

    if actions <= {"no-op", "read", "create"} and output_actions <= {"no-op", "create"}:
        return "additive"

    if actions <= {"no-op", "read", "create", "update"} and output_actions <= {"no-op", "create", "update"}:
        return "non-destructive"

    # Single Catch all: deletes, forgets, and any verb we do not know
    return "any-changes"

def verify_version(plan: dict, supported_major: str = "1") -> bool:
    # format_version is "MAJOR.MINOR", see
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
