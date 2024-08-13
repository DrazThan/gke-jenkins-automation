

## Overview

This project provides a Python-based orchestration system to automate the deployment of Jenkins on Google Kubernetes Engine (GKE). It streamlines the process of setting up a Jenkins instance, handling everything from infrastructure provisioning to application deployment.

## Features

- Automated deployment of Jenkins on GKE
- Infrastructure as Code using Terraform
- Configuration management with Ansible
- Support for both kubectl and Helm deployment methods
- Dynamic creation of isolated deployment environments
- Extensive error handling and logging
- Automatic cleanup of old deployment runs
- Firewall rule creation to limit access to specified IP

## Prerequisites

- Google Cloud Platform account
- Google Cloud SDK (gcloud) installed and configured
- Python 3.x
- GCP GKE API is enabled on the account

## Quick Start

1. Clone this repository to your Google Cloud Shell:
	`git clone [https://github.com/your-username/your-repo-name.git](https://github.com/your-username/your-repo-name.git) cd your-repo-name`
2. Fill out the `variables.tfvars` file in the `terraform` directory with your GCP project details and desired configuration.

4. Make the deployment script executable:
	`chmod +x deploy.py`

4. Run the deployment script:
	python3 deploy.py
	To use Helm for deployment instead of kubectl:
	`python deploy.py --method helm`

5. Wait for the deployment to complete. The script will provide logs of the process.

## Components

- `deploy.py`: Main orchestration script
- `terraform/`: Contains Terraform files for infrastructure provisioning
- `ansible/`: Contains Ansible playbooks and Kubernetes manifests
- `README.md`: This file

## How It Works

1. The script creates a timestamped directory for the current run.
2. It checks and installs necessary dependencies (Ansible, kubectl, Terraform, Helm).
3. Terraform is used to provision GKE cluster and other GCP resources.
4. Kubernetes context is set up and verified.
5. Ansible is used to deploy Jenkins using either kubectl or Helm.
6. Old deployment runs are cleaned up automatically.

## Customization

You can customize the deployment by modifying the following files:
- `terraform/variables.tfvars`: GCP project settings
- `ansible/deploy_jenkins.yml` or `ansible/deploy_jenkins_helm.yml`: Jenkins deployment configuration
- Kubernetes manifests in the `ansible/` directory

## Troubleshooting

If you encounter any issues, please check the logs provided by the script. Common problems can often be resolved by ensuring your GCP credentials are correctly set up and you have the necessary permissions.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
