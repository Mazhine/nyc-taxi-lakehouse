# Provider + Terraform version constraints (pinned, checked by CI).

terraform {
  required_version = ">= 1.16.5"
  required_providers {
    kind = {
      source  = "tehcyx/kind"
      version = "0.9.0"
    }
  }
}

# No provider arguments: the kind provider reads the standard kube context.
provider "kind" {}
