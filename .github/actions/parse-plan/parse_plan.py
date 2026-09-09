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

def has_unrankable_verbs(scope: str, verbs: set[str], known: frozenset[str]) -> bool:
    unrankable = verbs - known
    if unrankable:
        print(
            f"Treating unrankable {scope} verbs as any-changes: {sorted(unrankable)}",
            file=sys.stderr,
        )
    return bool(unrankable)


def classify(
    plan: dict,
    resource_verbs: frozenset[str] = frozenset(
        {"no-op", "read", "create", "update", "delete", "forget"}
    ),
    output_verbs: frozenset[str] = frozenset({"no-op", "create", "update", "delete"}),
) -> str:
    """Checked in severity order, first match wins:
    any-changes -> non-destructive -> additive -> no-changes
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

    # NOTE: Order of checks matters, we check the most severe first, an unknown verb. Then progress through
    # delete->update->create->no-op/read
    if has_unrankable_verbs("resource", actions, resource_verbs):
        return "any-changes"

    if has_unrankable_verbs("output", output_actions, output_verbs):
        return "any-changes"

    if {"delete", "forget"} & actions or "delete" in output_actions:
        return "any-changes"

    if "update" in actions or "update" in output_actions:
        return "non-destructive"

    if "create" in actions or "create" in output_actions:
        return "additive"

    # Only no-op/read verbs and untouched outputs remain
    return "no-changes"

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
