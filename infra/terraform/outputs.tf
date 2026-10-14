output "cluster_name" {
  value = kind_cluster.lakehouse.name
}

output "kubeconfig" {
  value     = kind_cluster.lakehouse.kubeconfig
  sensitive = true
}
