# Hermetic test fixture stack for the reusable workflow's self-test.
#
# determine-stacks only treats a directory as a Terraform stack if one of its
# .tf files contains the literal string  backend "s3"  (a naive substring
# check). We satisfy that heuristic from this comment so the directory is
# discovered, while the stack itself uses Terraform's default *local* backend —
# so `terraform init/plan` needs no AWS account. Do NOT turn the line below into
# a real backend block:
#
#     backend "s3"
#
# This stack declares no resources, so `terraform plan` reports "No changes".

terraform {
  required_version = ">= 1.0"
}
