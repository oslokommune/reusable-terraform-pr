# reusable-terraform-pr

Reusable GitHub Actions workflow for running Terraform plan on pull requests.

## Usage

### Basic usage

```yaml
name: "Terraform PR"

on:
  pull_request:
  issue_comment:
    types: [edited]

jobs:
  plan:
    uses: oslokommune/reusable-terraform-pr/.github/workflows/reusable-terraform-pr.yml@v2
    secrets:
      ssh-private-key: ${{ secrets.GOLDEN_PATH_IAC_PRIVATE_DEPLOY_KEY }}
```

### Multiple SSH private keys

```yaml
    secrets:
      ssh-private-key: |
        ${{ secrets.GOLDEN_PATH_IAC_PRIVATE_DEPLOY_KEY }}
        ${{ secrets.SOME_OTHER_DEPLOY_KEY }}
```


### Inputs

| Name                 | Type    | Default         | Description                                                                                                                                                        |
|----------------------|---------|-----------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `config-file`        | string  | `.gp.cicd.json` | Path to CI/CD configuration file                                                                                                                                   |
| `selected-stacks`    | string  | `""`            | Comma/newline-delimited list of stack patterns to plan (e.g., `stacks/dev/{dns,iam}`, `stacks/dev/app-*`). By default, only stacks with changed files are planned. On `schedule` and `workflow_dispatch` events the default is every stack in the repository (`**`). |
| `ignored-stacks`     | string  | `""`            | Comma/newline-delimited list of stack patterns to always ignore.                                                                                                   |
| `pr-automerge`       | boolean | `false`         | Whether to evaluate Renovate PRs for automerge eligibility based on upgrade type and Terraform plan results.                                                       |
| `pr-automerge-rules` | string  | `[]`            | JSON array of rules with pattern matching and per-update-type policies. Only used when `pr-automerge` is enabled. See [automerge](#with-automerge) for details.    |

### Outputs

| Name            | Type                 | Description                                                                                                                                                              |
|-----------------|----------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `success`       | boolean              | Whether all Terraform plans succeeded                                                                                                                                    |
| `has-changes`   | boolean              | Whether any stack had changes                                                                                                                                            |
| `stack-results` | string (JSON object) | Maps each planned stack to `success` and `hasChanges`. `hasChanges` is `null` when the plan failed. See [stack results](#stack-results).                                 |

#### Stack results

`stack-results` is keyed by stack path. Each value has the same two fields:

```json
{
  "stacks/dev/app": { "success": true, "hasChanges": true },
  "stacks/prod/app": { "success": true, "hasChanges": false },
  "stacks/dev/slackbot": { "success": false, "hasChanges": null }
}
```

- `success`: whether `terraform plan` succeeded for the stack.
- `hasChanges`: whether the plan had changes. `null` when the plan failed, since drift is then unknown.

The keys are the planned stacks, so `keys` gives the full list.

Select stacks with `jq`, for example `to_entries[] | select(.value.hasChanges) | .key` for stacks with changes, or `select(.value.success | not)` for failed plans.

### With manual trigger

Add `workflow_dispatch` to allow manually running plans for specific stacks. Leave `selected-stacks` empty to plan every stack in the repository.

```yaml
name: "Terraform PR"

on:
  pull_request:
  issue_comment:
    types: [edited]
  workflow_dispatch:
    inputs:
      selected-stacks:
        description: 'Stacks to plan (e.g., "stacks/dev/{dns,iam}", "stacks/dev/app-*"). Empty plans every stack.'
        required: false
        type: string

jobs:
  plan:
    uses: oslokommune/reusable-terraform-pr/.github/workflows/reusable-terraform-pr.yml@v2
    with:
      selected-stacks: ${{ inputs.selected-stacks }}
    secrets:
      ssh-private-key: ${{ secrets.GOLDEN_PATH_IAC_PRIVATE_DEPLOY_KEY }}
```

### Scheduled drift detection

Add a `schedule` trigger to the workflow that runs on pull requests. On a schedule there is no diff to discover stacks from, so an empty `selected-stacks` plans every stack in the repository. A plan with changes then means the infrastructure no longer matches the code on the default branch.

```yaml
on:
  pull_request:
  issue_comment:
    types: [edited]
  schedule:
    # 03:00 UTC, Monday through Friday. Cron schedules are always UTC.
    - cron: "0 3 * * 1-5"
```

The reusable workflow only plans. A `report` job in the caller, run on `schedule` events only, reads `stack-results` and fails the run when:

- a stack has changes, which is drift
- a plan failed, which means drift is unknown for that stack

The report job does not depend on the plan job succeeding, so one broken stack does not hide drift in the others. Stacks that always have changes, such as a service scaled outside Terraform, are listed in the report job as expected changes and skipped. They are still planned and shown in the summary. Use `ignored-stacks` for stacks that should not be planned at all.

> [!TIP]
> [pirates-iac](https://github.com/oslokommune/pirates-iac/blob/main/.github/workflows/terraform-pr.yml) has a complete workflow with the `schedule` trigger and the report job. Copy it and adjust the list of expected changes, or let an agent do it with the [`terraform-drift-detection` skill](#agent-plugin).

### With automerge

When `pr-automerge` is enabled, Renovate PRs are evaluated for automerge eligibility. The workflow parses structured upgrade info from the commit message and checks it against per-stack rules and Terraform plan results. If eligible, the `automerge` label is added, which Renovate picks up to perform the actual merge.

`pr-automerge-rules` is a JSON array of rules. Each rule has a `pattern` (glob) and optional policies for `major`, `minor`, and `patch` update types. First matching pattern wins.

Policies:
- `never` - never automerge this update type
- `no-changes` - only automerge if the Terraform plan has no changes (default)
- `any-changes` - automerge regardless of plan changes

```yaml
name: "Terraform PR"

on:
  pull_request:
  issue_comment:
    types: [edited]

jobs:
  plan:
    uses: oslokommune/reusable-terraform-pr/.github/workflows/reusable-terraform-pr.yml@v2
    with:
      pr-automerge: true
      pr-automerge-rules: |
        [
          {"pattern": "**/prod/**", "major": "never",      "minor": "no-changes",  "patch": "any-changes"},
          {"pattern": "**",         "major": "no-changes", "minor": "any-changes", "patch": "any-changes"}
        ]
    secrets:
      ssh-private-key: ${{ secrets.GOLDEN_PATH_IAC_PRIVATE_DEPLOY_KEY }}
```

## Agent plugin

This repository is also an [Agent Plugins](https://agent-plugins.org/) plugin. The manifest is `plugin.json`, and `skills/` holds [Agent Skills](https://agentskills.io/) for repositories that call the workflow.

| Skill                       | What it does                                                                                                                                  |
|-----------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------|
| `terraform-drift-detection` | Adds the `schedule` trigger and the report job from [scheduled drift detection](#scheduled-drift-detection) to the workflow that calls this one. |

Install it in Claude Code with:

```
/plugin marketplace add oslokommune/reusable-terraform-pr
/plugin install reusable-terraform-pr@reusable-terraform-pr
```

Then open the repository that runs the plan workflow and ask it to "set up drift detection". Agents that read Agent Skills without a plugin manager can load `skills/terraform-drift-detection/SKILL.md` directly.
