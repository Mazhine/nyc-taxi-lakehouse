# Local Kubernetes cluster for the lakehouse (kind, driven by Terraform).
# Terraform gives us a declarative, idempotent cluster definition: `apply`
# creates it, `destroy` removes it, and the same config can be re-applied.
resource "kind_cluster" "lakehouse" {
  name           = var.cluster_name
  wait_for_ready = true # block until the API server answers

  kind_config {
    kind        = "Cluster"
    api_version = "kind.x-k8s.io/v1alpha4"

    # Single node: on Docker Desktop/WSL2 a multi-node kind cluster would not
    # fit the 20 GB memory budget alongside MinIO/Spark/Trino.
    node {
      role = "control-plane"

      # Reserve 2 GiB for the system so the kubelet does not over-commit the VM.
      kubeadm_config_patches = [
        <<-EOT
        kind: InitConfiguration
        nodeRegistration:
          kubeletExtraArgs:
            system-reserved: memory=2Gi
        EOT
      ]

      # Publish NodePorts on the host. Host ports stay identical to the
      # in-cluster service ports so all scripts can use localhost:PORT.
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
