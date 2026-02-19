# reusable-terraform-pr-plan

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
    uses: oslokommune/reusable-terraform-pr-plan/.github/workflows/reusable-terraform-pr-plan.yml@v1
    secrets:
      ssh-private-key: ${{ secrets.GOLDEN_PATH_IAC_PRIVATE_DEPLOY_KEY }}
```

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
    uses: oslokommune/reusable-terraform-pr-plan/.github/workflows/reusable-terraform-pr-plan.yml@v1
    with:
      selected-stacks: ${{ inputs.selected-stacks }}
    secrets:
      ssh-private-key: ${{ secrets.GOLDEN_PATH_IAC_PRIVATE_DEPLOY_KEY }}
```

### With automerge

The `pr-automerge` input controls whether the `automerge` label is added, which Renovate picks up to perform the actual merge.

The `pr-automerge-rules` input maps update types (major/minor/patch) to rules:
- `never` - never automerge this update type
- `no-changes` - only automerge if plans have no changes (default)
- `any-changes` - automerge regardless of plan changes

The example below enables automerge for Renovate PRs targeting dev, allowing changes for minor/patch updates but requiring no changes for major updates.

```yaml
name: "Terraform PR"

on:
  pull_request:
  issue_comment:
    types: [edited]

jobs:
  plan:
    uses: oslokommune/reusable-terraform-pr-plan/.github/workflows/reusable-terraform-pr-plan.yml@v1
    with:
      pr-automerge: ${{ contains(github.event.pull_request.labels.*.name, 'env/dev') }}
      pr-automerge-rules: '{"minor": "any-changes", "patch": "any-changes"}'
    secrets:
      ssh-private-key: ${{ secrets.GOLDEN_PATH_IAC_PRIVATE_DEPLOY_KEY }}
```
