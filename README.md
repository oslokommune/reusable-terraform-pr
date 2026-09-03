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
    uses: oslokommune/reusable-terraform-pr/.github/workflows/reusable-terraform-pr.yml@v1
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
| `selected-stacks`    | string  | `""`            | Comma/newline-delimited list of stack patterns to plan (e.g., `stacks/dev/{dns,iam}`, `stacks/dev/app-*`). By default, only stacks with changed files are planned. Required on `schedule` events. |
| `ignored-stacks`     | string  | `""`            | Comma/newline-delimited list of stack patterns to always ignore.                                                                                                   |
| `pr-automerge`       | boolean | `false`         | Whether to evaluate Renovate PRs for automerge eligibility based on upgrade type and Terraform plan results.                                                       |
| `pr-automerge-rules` | string  | `[]`            | JSON array of rules with pattern matching and per-update-type policies. Only used when `pr-automerge` is enabled. See [automerge](#with-automerge) for details.    |

### Outputs

| Name            | Type                 | Description                                                                                                          |
|-----------------|----------------------|----------------------------------------------------------------------------------------------------------------------|
| `success`       | boolean              | Whether all Terraform plans succeeded                                                                                |
| `has-changes`   | boolean              | Whether any stack had changes                                                                                        |
| `stacks`        | string (JSON array)  | JSON array of all stacks that were planned                                                                           |
| `stack-changes` | string (JSON object) | Maps each stack whose plan succeeded to whether it had changes, e.g. `{"stacks/dev/app": true, "stacks/prod/app": false}` |

### With manual trigger

Add `workflow_dispatch` to allow manually running plans for specific stacks.

```yaml
name: "Terraform PR"

on:
  pull_request:
  issue_comment:
    types: [edited]
  workflow_dispatch:
    inputs:
      selected-stacks:
        description: 'Stacks to plan (e.g., "stacks/dev/{dns,iam}", "stacks/dev/app-*", "stacks/**")'
        required: true
        type: string

jobs:
  plan:
    uses: oslokommune/reusable-terraform-pr/.github/workflows/reusable-terraform-pr.yml@v1
    with:
      selected-stacks: ${{ inputs.selected-stacks }}
    secrets:
      ssh-private-key: ${{ secrets.GOLDEN_PATH_IAC_PRIVATE_DEPLOY_KEY }}
```

### Scheduled drift detection

Add a `schedule` trigger to detect drift between the Terraform code on the default branch and the infrastructure it describes. Requires `>= v1.7.0`.

Use a separate caller workflow for this. Scheduled runs have different failure semantics than PR runs: on a PR, a plan with changes is the expected outcome, while on a schedule it means the infrastructure no longer matches the code.

`selected-stacks` is required on `schedule` events. Stack discovery is diff-based, and a scheduled run has no diff to compare against, so the workflow fails instead of silently planning nothing. Adapt the glob to the layout of your repository.

`.github/workflows/terraform-drift.yml`:

```yaml
name: "Terraform drift"

on:
  schedule:
    # 03:00 UTC, Monday through Friday. Cron schedules are always UTC.
    - cron: "0 3 * * 1-5"
  workflow_dispatch:

jobs:
  plan:
    uses: oslokommune/reusable-terraform-pr/.github/workflows/reusable-terraform-pr.yml@v1
    with:
      selected-stacks: "stacks/**"
    secrets:
      ssh-private-key: ${{ secrets.GOLDEN_PATH_IAC_PRIVATE_DEPLOY_KEY }}

  notify:
    name: Notify on drift
    needs: plan
    # Alert on drift even when some other stack failed to plan. has-changes only
    # counts stacks whose plan succeeded. A failed plan fails the run on its own.
    if: ${{ !cancelled() && needs.plan.outputs.has-changes == 'true' }}
    runs-on: ubuntu-24.04
    steps:
      - name: Fail the run to report drift
        run: |
          echo "::error title=Drift detected::One or more stacks have changes. See the summary of the plan jobs."
          exit 1
```

Failing the `notify` job makes the scheduled run show up as red, which GitHub notifies watchers of. No Slack integration and no extra secrets are needed.

Things worth knowing:

- **Requires `>= v1.7.0`.** Earlier versions ignore `schedule` events: every job is skipped, nothing is planned, and the run still reports success. Pin the caller accordingly, so that a green run means "no drift" rather than "never ran".
- **A failed plan is not drift.** It means drift is unknown for that stack. `has-changes` only counts stacks whose plan succeeded, so the `notify` job still alerts on drift in the other stacks. Do not guard it with `needs.plan.result == 'success'`: one permanently broken stack would then suppress every drift alert. The `plan` job fails on its own when a plan fails, so the run is red either way.
- **Alerts repeat.** The run fails every night until the drift is either applied or removed from the code.

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
    uses: oslokommune/reusable-terraform-pr/.github/workflows/reusable-terraform-pr.yml@v1
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
