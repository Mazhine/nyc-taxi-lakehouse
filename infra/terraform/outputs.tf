# Outputs used by scripts/up.ps1 (and handy for debugging).

output "cluster_name" {
  value = kind_cluster.lakehouse.name
}

# The generated kubeconfig contains credentials: mark it sensitive so Terraform
# never prints it in plain text (scripts/up.ps1 relies on the kind context).
output "kubeconfig" {
  value     = kind_cluster.lakehouse.kubeconfig
  sensitive = true
}
