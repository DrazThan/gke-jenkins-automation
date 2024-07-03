provider "google" {
  project = var.project
  region  = var.region
  zone    = var.zone
}

resource "google_container_cluster" "primary" {
  name               = var.cluster_name
  location           = var.zone
  initial_node_count = 3
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
