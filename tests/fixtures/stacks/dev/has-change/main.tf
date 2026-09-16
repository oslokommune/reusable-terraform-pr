# Hermetic test fixture stack for the reusable workflow's self-test.
#
# See ../no-change/main.tf for why the string  backend "s3"  appears in this
# comment: it makes determine-stacks discover the directory while the stack
# uses the default *local* backend (no AWS required). Do NOT make it a real
# backend block:
#
#     backend "s3"
#
# This stack declares one resource using the registry-only `random` provider,
# so a fresh `terraform plan` always reports "Plan: 1 to add, 0 to change,
# 0 to destroy." — exercising the "has changes" path.

terraform {
  required_version = ">= 1.0"
  required_providers {
    random = {
      source  = "hashicorp/random"
      version = "~> 3.0"
    }
  }
}

resource "random_pet" "this" {}
