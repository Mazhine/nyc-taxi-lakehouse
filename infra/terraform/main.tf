resource "kind_cluster" "lakehouse" {
  name           = var.cluster_name
  wait_for_ready = true

  kind_config {
    kind        = "Cluster"
    api_version = "kind.x-k8s.io/v1alpha4"

    node {
      role = "control-plane"

      kubeadm_config_patches = [
        <<-EOT
        kind: InitConfiguration
        nodeRegistration:
          kubeletExtraArgs:
            system-reserved: memory=2Gi
        EOT
      ]

      extra_port_mappings {
        container_port = 30090
        host_port      = 9000 # MinIO API
      }
      extra_port_mappings {
        container_port = 30091
        host_port      = 9001 # MinIO console
      }
      extra_port_mappings {
        container_port = 30080
        host_port      = 8080 # Trino
      }
      extra_port_mappings {
        container_port = 30818
        host_port      = 8181 # Lakekeeper REST
      }
    }
  }
}
