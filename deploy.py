import os
import subprocess
import json

def read_tfvars(filepath):
    vars = {}
    with open(filepath) as f:
        for line in f:
            if '=' in line:
                name, value = line.split('=', 1)
                vars[name.strip()] = value.strip().strip('"')
    return vars

def check_disk_exists():
    result = subprocess.run(['gcloud', 'compute', 'disks', 'list', '--filter=name=jenkins-disk', '--format=json'], capture_output=True, text=True)
    disks = json.loads(result.stdout)
    return bool(disks)

def check_cluster_exists():
    result = subprocess.run(['gcloud', 'container', 'clusters', 'list', '--filter=name=my-gke-cluster', '--format=json'], capture_output=True, text=True)
    clusters = json.loads(result.stdout)
    return bool(clusters)

def check_pvc_exists(namespace, pvc_name):
    result = subprocess.run(['kubectl', 'get', 'pvc', pvc_name, '-n', namespace, '-o', 'json'], capture_output=True, text=True)
    if result.returncode == 0:
        return True
    else:
        return False

def install_ansible():
    try:
        result = subprocess.run(['which', 'ansible-playbook'], capture_output=True, text=True)
        if result.returncode != 0:
            print("Ansible is not installed. Installing Ansible...")
            subprocess.run(['pip3', 'install', 'ansible'])
            os.environ["PATH"] += os.pathsep + os.path.expanduser("~/.local/bin")
    except Exception as e:
        print(f"Error during Ansible installation: {e}")

def install_kubernetes_library():
    try:
        subprocess.run(['pip3', 'install', 'kubernetes'])
    except Exception as e:
        print(f"Error installing Kubernetes library: {e}")

def create_disk():
    os.chdir('terraform')
    subprocess.run(['terraform', 'init'])
    subprocess.run(['terraform', 'apply', '-auto-approve', '-var-file=variables.tfvars', '-target=google_compute_disk.jenkins_disk'])
    os.chdir('..')

def create_cluster():
    os.chdir('terraform')
    subprocess.run(['terraform', 'apply', '-auto-approve', '-var-file=variables.tfvars', '-target=google_container_cluster.primary'])
    os.chdir('..')

def create_pvc():
    subprocess.run(['kubectl', 'apply', '-f', 'ansible/jenkins_pvc.yaml'])

def create_role_binding():
    subprocess.run(['kubectl', 'apply', '-f', 'ansible/jenkins-role-binding.yaml'])

def run_ansible(vars):
    install_ansible()
    install_kubernetes_library()
    try:
        env_vars = os.environ.copy()
        subprocess.run([
            'ansible-playbook',
            'ansible/deploy_jenkins.yml',
            '--extra-vars', f"project={vars['project']} zone={vars['zone']} cluster_name={vars['cluster_name']}"
        ], env=env_vars)
    except FileNotFoundError as e:
        print(f"Ansible playbook not found: {e}")
    except Exception as e:
        print(f"Error running Ansible playbook: {e}")

def main():
    vars = read_tfvars('terraform/variables.tfvars')
    disk_exists = check_disk_exists()
    cluster_exists = check_cluster_exists()
    pvc_exists = check_pvc_exists('jenkins', 'jenkins-pvc')

    if not disk_exists:
        print("Creating disk...")
        create_disk()
    else:
        print("Disk 'jenkins-disk' already exists. Skipping disk creation.")

    if not cluster_exists:
        print("Creating GKE cluster...")
        create_cluster()
    else:
        print("GKE cluster 'my-gke-cluster' already exists. Skipping cluster creation.")

    if not pvc_exists:
        print("Creating PVC...")
        create_pvc()
    else:
        print("PVC 'jenkins-pvc' already exists. Skipping PVC creation.")

    print("Creating ClusterRoleBinding for Jenkins...")
    create_role_binding()

    print("Deploying Jenkins...")
    run_ansible(vars)

if __name__ == "__main__":
    main()
