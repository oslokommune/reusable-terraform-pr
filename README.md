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
| `selected-stacks`    | string  | `""`            | Comma/newline-delimited list of stack patterns to plan (e.g., `stacks/dev/{dns,iam}`, `stacks/dev/app-*`). By default, only stacks with changed files are planned. |
| `ignored-stacks`     | string  | `""`            | Comma/newline-delimited list of stack patterns to always ignore.                                                                                                   |
| `pr-automerge`       | boolean | `false`         | Whether to evaluate Renovate PRs for automerge eligibility based on upgrade type and Terraform plan results.                                                       |
| `pr-automerge-rules` | string  | `[]`            | JSON array of rules with pattern matching and per-update-type policies. Only used when `pr-automerge` is enabled. See [automerge](#with-automerge) for details.    |

### Outputs

| Name          | Type                | Description                                |
|---------------|---------------------|--------------------------------------------|
| `success`     | boolean             | Whether all Terraform plans succeeded      |
| `has-changes` | boolean             | Whether any stack had changes              |
| `stacks`      | string (JSON array) | JSON array of all stacks that were planned |

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
