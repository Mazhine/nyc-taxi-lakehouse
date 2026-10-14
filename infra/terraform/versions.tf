terraform {
  required_version = ">= 1.16.5"
  required_providers {
    kind = {
      source  = "tehcyx/kind"
      version = "0.9.0"
    }
  }
}

provider "kind" {}
