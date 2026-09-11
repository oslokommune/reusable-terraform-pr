"""Classify a Terraform plan into a change severity.

Reads the JSON representation of a plan (`terraform show -json <planfile>`)
and prints the most severe kind of change it contains. Covers resource and
output changes. Unrankable verbs are treated as "any-changes", the most
severe value. An unloadable plan or unsupported plan format exits non-zero:
those mean the pipeline is broken, not that the plan is dangerous.

Usage:
  python3 parse_plan.py --plan-json-path <path>

Output: prints the change severity to stdout.
"""

import argparse
import json
import sys

# The verbs each classification tolerates, for resource and output changes
NO_CHANGES = {
    "actions": ("no-op", "read"),
    "output_actions": ("no-op",),
}
ADDITIVE = {
    "actions": ("no-op", "read", "create"),
    "output_actions": ("no-op", "create"),
}
NON_DESTRUCTIVE = {
    "actions": ("no-op", "read", "create", "update"),
    "output_actions": ("no-op", "create", "update"),
}


def only_allowed_actions(actions: dict, output_actions: dict, allowed: dict) -> bool:
    resources_allowed = all(verb in allowed["actions"] for verb in actions)
    outputs_allowed = all(verb in allowed["output_actions"] for verb in output_actions)
    return resources_allowed and outputs_allowed

def classify(plan: dict) -> str:
    """Checks least severe first: a plan classifies as the first category
    that tolerates every verb in it. Anything else is the catch-all
    "any-changes".
    """
    # Every action verb in the plan and how many changes carry it;
    # a replace contributes both "delete" and "create"
    actions: dict[str, int] = {}
    for change in plan.get("resource_changes") or []:
        for verb in change["change"]["actions"]:
            actions[verb] = actions.get(verb, 0) + 1

    output_actions: dict[str, int] = {}
    for change in (plan.get("output_changes") or {}).values():
        for verb in change["actions"]:
            output_actions[verb] = output_actions.get(verb, 0) + 1

    # NOTE: Order matters: least severe first
    if only_allowed_actions(actions, output_actions, NO_CHANGES):
        return "no-changes"

    if only_allowed_actions(actions, output_actions, ADDITIVE):
        return "additive"

    if only_allowed_actions(actions, output_actions, NON_DESTRUCTIVE):
        return "non-destructive"

    # Single Catch all: deletes, forgets, and any verb we do not know
    return "any-changes"

def verify_version(plan: dict, supported_major: str = "1") -> bool:
    # format_version is "MAJOR.MINOR", see
    # https://developer.hashicorp.com/terraform/internals/json-format#format-summary
    return str(plan.get("format_version", "")).split(".")[0] == supported_major


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Classify a Terraform plan JSON into a change severity"
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
