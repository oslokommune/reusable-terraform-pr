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

Add a `schedule` trigger to detect drift between the Terraform code on the default branch and the infrastructure it describes. Requires `>= v2.0.0`.

Use a separate caller workflow for this. Scheduled runs have different failure semantics than PR runs: on a PR, a plan with changes is the expected outcome, while on a schedule it means the infrastructure no longer matches the code.

Stack discovery is diff-based, and a scheduled run has no diff to compare against. On `schedule` and `workflow_dispatch` events, an empty `selected-stacks` therefore means every stack in the repository, so the caller does not have to list them. Set `selected-stacks` to narrow the run to a subset.

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
    uses: oslokommune/reusable-terraform-pr/.github/workflows/reusable-terraform-pr.yml@v2
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
        env:
          STACK_RESULTS: ${{ needs.plan.outputs.stack-results }}
        run: |
          drifted="$(echo "$STACK_RESULTS" | jq -r 'to_entries[] | select(.value.hasChanges) | .key' | paste -sd ' ' -)"
          failed="$(echo "$STACK_RESULTS" | jq -r 'to_entries[] | select(.value.success | not) | .key' | paste -sd ' ' -)"
          echo "::error title=Drift detected::Stacks with changes: ${drifted}. Stacks that failed to plan: ${failed:-none}. See the summary of the plan jobs."
          exit 1
```

Failing the `notify` job makes the scheduled run show up as red, which GitHub notifies watchers of. The error annotation names the drifted stacks, so the run page says what changed without opening the job summary. No Slack integration and no extra secrets are needed.

Things worth knowing:

- **Requires `>= v2.0.0`.** Earlier versions ignore `schedule` events: every job is skipped, nothing is planned, and the run still reports success. Pin the caller accordingly, so that a green run means "no drift" rather than "never ran".
- **A failed plan is not drift.** It means drift is unknown for that stack. `has-changes` only counts stacks whose plan succeeded, so the `notify` job still alerts on drift in the other stacks. `stack-results` names the failed stacks separately, with `success: false`. Do not guard it with `needs.plan.result == 'success'`: one permanently broken stack would then suppress every drift alert. The `plan` job fails on its own when a plan fails, so the run is red either way.
- **Use `ignored-stacks` for stacks that always fail or always differ.** Some stacks fail to plan for reasons unrelated to drift, such as a provider that no longer runs. Others show a diff on every plan, such as a `null_resource` with a timestamp trigger. Either kind makes the scheduled run red forever. Exclude them until they are fixed:

  ```yaml
      with:
        ignored-stacks: |
          stacks/dev/slackbot
          stacks/*/legacy-*
  ```

- **Alerts repeat.** The run fails every night until the drift is either applied or removed from the code. A red run that is the normal state stops getting attention, so deal with drift quickly or ignore the stack explicitly.

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
