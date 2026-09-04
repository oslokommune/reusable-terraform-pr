---
name: terraform-drift-detection
description: Set up scheduled Terraform drift detection in a repository that plans with the oslokommune/reusable-terraform-pr workflow. Use when asked to detect drift or to add a nightly or scheduled plan that fails on unexpected infrastructure changes.
compatibility: Requires gh with access to github.com. Uses actionlint when installed.
metadata:
  author: oslokommune
---

# Terraform drift detection

Drift is a plan with changes when the code did not change. On a `schedule` the reusable workflow plans every stack in the repository. A `report` job in the caller workflow then fails the run when a stack has changes or a plan failed. This skill adds the schedule and the report job to the caller workflow.

## Steps

1. **Find the caller workflow.** Search `.github/workflows` for `oslokommune/reusable-terraform-pr`. With no match, stop and point the user to [basic usage](https://github.com/oslokommune/reusable-terraform-pr#basic-usage) in the README, since drift detection builds on the plan workflow. With several matches, ask which one to change, or apply the steps to each.

2. **Pin a version that has `stack-results`.** The report job reads the `stack-results` output, added in v1.7.0. Read the `uses:` line. When it pins a tag or SHA below v1.7.0, or a SHA without a version comment, resolve the latest release and pin it:

   ```sh
   tag="$(gh release view --repo oslokommune/reusable-terraform-pr --json tagName --jq .tagName)"
   gh api "repos/oslokommune/reusable-terraform-pr/commits/$tag" --jq .sha
   ```

   Write the line as `uses: oslokommune/reusable-terraform-pr/.github/workflows/reusable-terraform-pr.yml@<sha> # <tag>`. Renovate keeps SHA pins with a version comment up to date.

3. **Add the schedule trigger.** Add this under `on:`, keeping the other triggers. Use the cron the user gave, otherwise this one:

   ```yaml
     schedule:
       # 03:00 UTC, Monday through Friday. Cron schedules are always UTC.
       - cron: "0 3 * * 1-5"
   ```

   Leave `selected-stacks` as it is. On a `schedule` an empty value plans every stack. A caller that passes `${{ inputs.selected-stacks }}` from `workflow_dispatch` also works, since that input is empty on a schedule. Stacks that must never be planned go in `ignored-stacks`.

4. **Add the report job.** Copy [assets/report-job.yml](assets/report-job.yml) into `jobs:`. Set `needs:` and the `STACK_RESULTS` expression to the id of the job that calls the reusable workflow. Fill `EXPECTED_CHANGES` with the stacks the user names as always having changes, one glob per line with a comment saying why. When the user knows of none, leave the list empty. The first scheduled run lists the stacks with changes, and the user adds the expected ones then.

5. **Check the workflow.** Run `actionlint` on the file when it is installed. Confirm each of these in the file:
   - `on.schedule` has a cron entry.
   - The report job has `if: ${{ !cancelled() && github.event_name == 'schedule' }}`.
   - `needs` names the plan job, and `STACK_RESULTS` reads that job's `stack-results` output.
   - Every line in `EXPECTED_CHANGES` is a glob or a comment.

6. **Tell the user what happens next.**
   - Schedules run from the default branch, so the change takes effect once merged.
   - GitHub sends failure notifications for a scheduled run to the user who last changed the cron line.
   - In a public repository GitHub disables the schedule after 60 days without commits.
   - The report job runs only on `schedule`. To see stacks with changes before the first scheduled run, and the workflow has `workflow_dispatch`, run `gh workflow run <file>` and read the plan summary in the run.

## Reference

- [Scheduled drift detection](https://github.com/oslokommune/reusable-terraform-pr#scheduled-drift-detection) in the README describes the outputs the report job reads.
- [pirates-iac](https://github.com/oslokommune/pirates-iac/blob/main/.github/workflows/terraform-pr.yml) is a complete caller workflow with the schedule and the report job.
