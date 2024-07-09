import os
import subprocess
import json
import sys
from contextlib import contextmanager

@contextmanager
def change_directory(path):
    original_dir = os.getcwd()
    try:
        os.chdir(path)
        yield
    finally:
        os.chdir(original_dir)

def run_command(command, error_message, env=None):
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=True, env=env)
        return result.stdout
    except subprocess.CalledProcessError as e:
        print(f"{error_message}: {e}")
        print(f"Error output: {e.stderr}")
        return None

def parse_json(json_string, error_message):
    try:
        return json.loads(json_string)
    except json.JSONDecodeError:
        print(f"{error_message}. This might indicate no resources exist.")
        return None

def read_tfvars(filepath):
    vars = {}
    try:
        with open(filepath, 'r') as f:
            for line in f:
                if '=' in line:
                    name, value = line.split('=', 1)
                    vars[name.strip()] = value.strip().strip('"')
    except IOError as e:
        print(f"Error reading tfvars file: {e}")
        sys.exit(1)
    return vars

def check_resource_exists(command, resource_name):
    output = run_command(command, f"Error checking {resource_name} existence")
    if output is None:
        return False
    parsed = parse_json(output, f"No valid JSON returned when checking {resource_name} existence")
    return bool(parsed)

def check_disk_exists():
    return check_resource_exists(
        ['gcloud', 'compute', 'disks', 'list', '--filter=name=jenkins-disk', '--format=json'],
        'disk'
    )

def check_cluster_exists(cluster_name):
    return check_resource_exists(
        ['gcloud', 'container', 'clusters', 'list', f'--filter=name={cluster_name}', '--format=json'],
        'cluster'
    )

def check_pvc_exists(namespace, pvc_name):
    output = run_command(['kubectl', 'get', 'pvc', pvc_name, '-n', namespace, '-o', 'json'], "Error checking PVC existence")
    return output is not None

def install_dependency(dependency, install_command):
    if run_command(['which', dependency], f"Checking {dependency} installation") is None:
        print(f"{dependency} is not installed. Installing {dependency}...")
        if run_command(install_command, f"Error during {dependency} installation") is None:
            sys.exit(1)
        if dependency == 'ansible-playbook':
            os.environ["PATH"] += os.pathsep + os.path.expanduser("~/.local/bin")

def create_or_configure_resource(exists, create_func, resource_name):
    if not exists:
        print(f"Creating {resource_name}...")
        create_func()
    else:
        print(f"{resource_name} already exists. Skipping creation.")

def create_disk():
    with change_directory('terraform'):
        run_command(['terraform', 'init'], "Error initializing Terraform")
        run_command(['terraform', 'apply', '-auto-approve', '-var-file=variables.tfvars', '-target=google_compute_disk.jenkins_disk'], "Error creating disk")

def create_cluster():
    with change_directory('terraform'):
        run_command(['terraform', 'apply', '-auto-approve', '-var-file=variables.tfvars', '-target=google_container_cluster.primary'], "Error creating cluster")

def create_pvc():
    run_command(['kubectl', 'apply', '-f', 'ansible/jenkins_pvc.yaml'], "Error creating PVC")

def create_role_binding():
    run_command(['kubectl', 'apply', '-f', 'ansible/jenkins-role-binding.yaml'], "Error creating role binding")

def run_ansible(vars):
    env_vars = os.environ.copy()
    run_command([
        'ansible-playbook',
        'ansible/deploy_jenkins.yml',
        '--extra-vars', f"project={vars['project']} zone={vars['zone']} cluster_name={vars['cluster_name']}"
    ], "Error running Ansible playbook", env=env_vars)

def main():
    # Check and install dependencies
    install_dependency('ansible-playbook', ['pip3', 'install', 'ansible'])
    install_dependency('kubectl', ['gcloud', 'components', 'install', 'kubectl'])
    install_dependency('terraform', ['snap', 'install', 'terraform', '--classic'])
    run_command(['pip3', 'install', 'kubernetes'], "Error installing Kubernetes library")

    # Read variables
    vars = read_tfvars('terraform/variables.tfvars')

    # Check resource existence
    disk_exists = check_disk_exists()
    cluster_exists = check_cluster_exists(vars['cluster_name'])
    pvc_exists = check_pvc_exists('jenkins', 'jenkins-pvc')

    # Create or configure resources
    create_or_configure_resource(disk_exists, create_disk, "Disk 'jenkins-disk'")
    create_or_configure_resource(cluster_exists, create_cluster, f"GKE cluster '{vars['cluster_name']}'")
    create_or_configure_resource(pvc_exists, create_pvc, "PVC 'jenkins-pvc'")

    print("Creating ClusterRoleBinding for Jenkins...")
    create_role_binding()

    print("Deploying Jenkins...")
    run_ansible(vars)

if __name__ == "__main__":
    main()