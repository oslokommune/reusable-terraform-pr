# Hermetic test fixture stack for the reusable workflow's *failure* self-test.
#
# See ../no-change/main.tf for why the string  backend "s3"  appears in a
# comment (the determine-stacks discovery heuristic) while the stack uses the
# default local backend — no AWS required:
#
#     backend "s3"
#
# The failing precondition makes `terraform plan` error out (exit 1) with no
# cloud access, so we can assert the workflow correctly reports a failed plan.

terraform {
  required_version = ">= 1.4"
}

resource "terraform_data" "fails" {
  lifecycle {
    precondition {
      condition     = false
      error_message = "This fixture stack fails on purpose for the self-test."
    }
  }
}
