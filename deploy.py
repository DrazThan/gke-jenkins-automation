import os
import subprocess
import json
import sys
import tempfile
import yaml
import shutil
import logging
from datetime import datetime
from contextlib import contextmanager

# Set up logging
logging.basicConfig(level=logging.DEBUG)

# Context manager for changing directories safely
@contextmanager
def change_directory(path):
    original_dir = os.getcwd()
    try:
        os.chdir(path)
        yield
    finally:
        os.chdir(original_dir)

# Function to run shell commands with error handling
def run_command(command, error_message, env=None):
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=True, env=env)
        logging.debug(f"Command output: {result.stdout}")
        return result.stdout
    except subprocess.CalledProcessError as e:
        logging.error(f"{error_message}: {e}")
        logging.error(f"Error output: {e.stderr}")
        return None

# Function to parse JSON output safely
def parse_json(json_string, error_message):
    try:
        return json.loads(json_string)
    except json.JSONDecodeError:
        logging.error(f"{error_message}. This might indicate no resources exist.")
        return None

# Function to read Terraform variables
def read_tfvars(filepath):
    vars = {}
    try:
        with open(filepath, 'r') as f:
            for line in f:
                if '=' in line:
                    name, value = line.split('=', 1)
                    vars[name.strip()] = value.strip().strip('"')
    except IOError as e:
        logging.error(f"Error reading tfvars file: {e}")
        sys.exit(1)
    return vars

# Function to create repo into working directory
def prepare_running_directory():
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = f"/tmp/deployment_{timestamp}"
    
    # Create the main running directory
    os.makedirs(run_dir, exist_ok=True)

    # Clear Terraform cache
    terraform_cache = os.path.expanduser('~/.terraform.d/plugin-cache')
    if os.path.exists(terraform_cache):
        shutil.rmtree(terraform_cache)
    
    # Create subdirectories and copy files
    for subdir in ['terraform', 'ansible']:
        os.makedirs(f"{run_dir}/{subdir}", exist_ok=True)
        for item in os.listdir(subdir):
            s = os.path.join(subdir, item)
            d = os.path.join(run_dir, subdir, item)
            if os.path.isdir(s):
                shutil.copytree(s, d, symlinks=False, ignore=shutil.ignore_patterns('.terraform', '*.tfstate*'))
            else:
                shutil.copy2(s, d)
    
    return run_dir

# Set the google cloud project ID
def set_gcp_project(project_id):
    run_command(['gcloud', 'config', 'set', 'project', project_id], "Error setting GCP project")

# Function to check if a resource exists
def check_resource_exists(command, resource_name):
    output = run_command(command, f"Error checking {resource_name} existence")
    if output is None:
        return False
    parsed = parse_json(output, f"No valid JSON returned when checking {resource_name} existence")
    return bool(parsed)

# Function to check if disk exists
def check_disk_exists():
    return check_resource_exists(
        ['gcloud', 'compute', 'disks', 'list', '--filter=name=jenkins-disk', '--format=json'],
        'disk'
    )

# Function to check if cluster exists
def check_cluster_exists(cluster_name):
    return check_resource_exists(
        ['gcloud', 'container', 'clusters', 'list', f'--filter=name={cluster_name}', '--format=json'],
        'cluster'
    )

# Function to create a temporary Kubernetes config file
def create_temp_kube_config():
    fd, path = tempfile.mkstemp(prefix='kube', suffix='.config')
    os.close(fd)
    return path

# Global variable for Kubernetes config
kube_config = create_temp_kube_config()

# Function to run kubectl commands
def run_kubectl_command(command, error_message):
    full_command = [
        'kubectl',
        f'--kubeconfig={kube_config}',
    ] + command
    return run_command(full_command, error_message)

# Function to check if PVC exists
def check_pvc_exists(project, zone, cluster_name, namespace, pvc_name):
    # Get cluster credentials
    run_command(['gcloud', 'container', 'clusters', 'get-credentials', cluster_name, '--zone', zone, '--project', project], "Error getting cluster credentials")
    
    output = run_kubectl_command(['get', 'pvc', pvc_name, '-n', namespace, '-o', 'json'], "Error checking PVC existence")
    return output is not None

# Function to install dependencies
def install_dependency(dependency, install_command):
    if run_command(['which', dependency], f"Checking {dependency} installation") is None:
        logging.info(f"{dependency} is not installed. Installing {dependency}...")
        if run_command(install_command, f"Error during {dependency} installation") is None:
            sys.exit(1)
        if dependency == 'ansible-playbook':
            os.environ["PATH"] += os.pathsep + os.path.expanduser("~/.local/bin")

# Function to create or configure a resource
def create_or_configure_resource(exists, create_func, resource_name):
    if not exists:
        logging.info(f"Creating {resource_name}...")
        create_func()
    else:
        logging.info(f"{resource_name} already exists. Skipping creation.")

# Function to create disk
def create_disk():
    with change_directory('terraform'):
        run_command(['terraform', 'init'], "Error initializing Terraform")
        run_command(['terraform', 'apply', '-auto-approve', '-var-file=variables.tfvars', '-target=google_compute_disk.jenkins_disk'], "Error creating disk")

# Function to create cluster
def create_cluster(run_dir, vars):
    with change_directory(f"{run_dir}/terraform"):
        logging.debug(f"Current working directory: {os.getcwd()}")
        logging.debug(f"Contents of current directory: {os.listdir()}")
        
        with open('variables.tfvars', 'r') as f:
            logging.debug(f"Contents of variables.tfvars:\n{f.read()}")

        # Initialize Terraform
        init_result = run_command(['terraform', 'init'], "Error initializing Terraform")
        logging.debug(f"Terraform init result: {init_result}")
        
        # Check Terraform state
        show_result = run_command(['terraform', 'show'], "Error showing Terraform state")
        if 'google_container_cluster' in show_result:
            logging.info("Existing cluster found in Terraform state. Removing it.")
            run_command(['terraform', 'state', 'rm', 'google_container_cluster.primary'], "Error removing cluster from Terraform state")
        
        # Apply Terraform changes
        apply_command = [
            'terraform', 'apply',
            '-auto-approve',
            '-var-file=variables.tfvars',
            '-state=terraform.tfstate',
            '-target=google_container_cluster.primary'
        ]
        logging.debug(f"Running Terraform apply command: {' '.join(apply_command)}")
        result = run_command(apply_command, "Error creating/updating cluster")
        logging.debug(f"Terraform apply result: {result}")
    return result

# Function to create PVC
def create_pvc(run_dir):
    run_kubectl_command(['apply', '-f', f'{run_dir}/ansible/jenkins_pvc.yaml'], "Error creating PVC")

# Function to create role binding
def create_role_binding(run_dir):
    run_kubectl_command(['apply', '-f', f'{run_dir}/ansible/jenkins-role-binding.yaml'], "Error creating role binding")

def create_temp_ansible_inventory(project, zone):
    inventory = {
        'all': {
            'hosts': ['localhost'],
            'vars': {
                'ansible_connection': 'local',
                'gcp_project': project,
                'gcp_zone': zone,
            }
        }
    }
    
    fd, path = tempfile.mkstemp(prefix='ansible_inventory_', suffix='.yml')
    with os.fdopen(fd, 'w') as f:
        yaml.dump(inventory, f)
    
    return path

# Function to run Ansible playbook
def run_ansible(vars, run_dir):
    env_vars = os.environ.copy()
    
    # Create temporary Ansible inventory
    inventory_path = create_temp_ansible_inventory(vars['project'], vars['zone'])
    
    try:
        run_command([
            'ansible-playbook',
            '-i', inventory_path,
            f'{run_dir}/ansible/deploy_jenkins.yml',
            '--extra-vars', f"project={vars['project']} zone={vars['zone']} cluster_name={vars['cluster_name']}"
        ], "Error running Ansible playbook", env=env_vars)
    finally:
        # Clean up the temporary inventory file
        os.remove(inventory_path)

# Function to set Kubernetes context
def set_kubernetes_context(project, zone, cluster_name):
    command = [
        'gcloud', 'container', 'clusters', 'get-credentials',
        cluster_name,
        f'--zone={zone}',
        f'--project={project}'
    ]
    run_command(command, "Error setting Kubernetes context")

# Function to clear Kubernetes config
def clear_kubernetes_config():
    config_file = os.path.expanduser('~/.kube/config')
    if os.path.exists(config_file):
        os.rename(config_file, f"{config_file}.bak")

# Function to verify Kubernetes context
def verify_kubernetes_context(expected_project, expected_zone, expected_cluster):
    result = run_kubectl_command(['config', 'current-context'], "Error getting current context")
    if result:
        current_context = result.strip()
        expected_context = f"gke_{expected_project}_{expected_zone}_{expected_cluster}"
        if current_context != expected_context:
            logging.warning(f"Current Kubernetes context '{current_context}' does not match expected context '{expected_context}'")
            return False
    return True

# Main function
def main():
    # Prepare running directory
    run_dir = prepare_running_directory()
    # Set up environment to use temporary Kubernetes config
    kube_config = f"{run_dir}/kube_config"
    os.environ['KUBECONFIG'] = kube_config

    # Check and install dependencies
    install_dependency('ansible-playbook', ['pip3', 'install', 'ansible'])
    install_dependency('kubectl', ['gcloud', 'components', 'install', 'kubectl'])
    install_dependency('terraform', ['snap', 'install', 'terraform', '--classic'])
    run_command(['pip3', 'install', 'kubernetes'], "Error installing Kubernetes library")
    run_command(['pip3', 'install', 'PyYAML'], "Error installing PyYAML library")

    # Read variables
    vars = read_tfvars(f"{run_dir}/terraform/variables.tfvars")
    # setting cluster:
    set_gcp_project(vars['project'])

    # Create or configure cluster
    cluster_exists = check_cluster_exists(vars['cluster_name'])
    if not cluster_exists:
        logging.info(f"Creating GKE cluster '{vars['cluster_name']}'...")
        if create_cluster(run_dir, vars) is None:
            logging.error("Failed to create cluster. Exiting.")
            sys.exit(1)
    else:
        logging.info(f"GKE cluster '{vars['cluster_name']}' already exists.")

    # Set Kubernetes context
    if set_kubernetes_context(vars['project'], vars['zone'], vars['cluster_name']) is None:
        logging.error("Failed to set Kubernetes context. Exiting.")
        sys.exit(1)

    # Verify Kubernetes context
    if not verify_kubernetes_context(vars['project'], vars['zone'], vars['cluster_name']):
        logging.error("Kubernetes context mismatch. Exiting.")
        sys.exit(1)

    # Check resource existence
    disk_exists = check_disk_exists()
    pvc_exists = check_pvc_exists(vars['project'], vars['zone'], vars['cluster_name'], 'jenkins', 'jenkins-pvc')

    # Create or configure resources
    create_or_configure_resource(disk_exists, lambda: create_disk(), "Disk 'jenkins-disk'")
    create_or_configure_resource(pvc_exists, lambda: create_pvc(run_dir), "PVC 'jenkins-pvc'")

    logging.info("Creating ClusterRoleBinding for Jenkins...")
    if create_role_binding(run_dir) is None:
        logging.error("Failed to create ClusterRoleBinding. Exiting.")
        sys.exit(1)

    logging.info("Deploying Jenkins...")
    if run_ansible(vars, run_dir) is None:
        logging.error("Failed to deploy Jenkins. Exiting.")
        sys.exit(1)

    logging.info("Deployment completed successfully.")
    cleanup_old_runs()

def cleanup_old_runs(max_runs=5):
    runs = sorted([d for d in os.listdir('/tmp') if d.startswith('deployment_')], reverse=True)
    for old_run in runs[max_runs:]:
        shutil.rmtree(f"/tmp/{old_run}")

if __name__ == "__main__":
    main()