variable "cluster_name" {
  description = "kind cluster name"
  type        = string
  default     = "lakehouse"
}

variable "kubeconfig_path" {
  description = "Where kind writes the kubeconfig"
  type        = string
  default     = "~/.kube/config"
}
