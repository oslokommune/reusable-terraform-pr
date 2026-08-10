terraform {
  required_version = ">= 1.9.0"

  backend "s3" {
    bucket = "test-tfstate"
    key    = "null-stack.tfstate"
    region = "us-east-1"
    # moto on localhost has no virtual-host DNS, so force path-style.
    # Endpoint + credentials come from AWS_ENDPOINT_URL /
    # AWS_ACCESS_KEY_ID env vars set by the test harness.
    use_path_style = true
  }
}

output "ok" {
  value = "ok"
}
