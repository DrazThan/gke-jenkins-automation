provider "google" {
  project = var.project
  region  = var.region
  zone    = var.zone
}

resource "google_container_cluster" "primary" {
  name               = var.cluster_name
  location           = var.zone
  initial_node_count = 3
  deletion_protection = false

  node_config {
    machine_type = "e2-medium"  # This is a balanced machine type, adjust as needed
    disk_type    = "pd-ssd"
    disk_size_gb = 30  # Reduce this value to fit within your quota

    oauth_scopes = [
      "https://www.googleapis.com/auth/cloud-platform"
    ]
  }
}

resource "google_compute_disk" "jenkins_disk" {
  name  = "jenkins-disk"
  type  = "pd-ssd"
  zone  = var.zone
  size  = 50
}

resource "google_compute_firewall" "jenkins_firewall" {
  name    = "allow-jenkins"
  network = "default"

  allow {
    protocol = "tcp"
    ports    = ["8080"]
  }

  source_ranges = [var.public_ip]
}
