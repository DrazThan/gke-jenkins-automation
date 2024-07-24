Hey everyone :)

This is a basic python based orchestration, here is what it does : 
Copies relevant files from repo into timestamped dir, to seperate environment from source code.
** Important - it will wipe the intialized terraform state file if a new cluster is set, for example if you want to run the same script twice (from different gcp projects for example)
It will check for pre existing resources to handle exceptions,
spin them up in the google cloud cli using terraform,
then it will install ansible and configure the resources using it.
All with extensive error handling and logging

To deploy : 

Clone the repo to your gcloud shell,fill out the variables.tfvars in terraform dir,chmod +x the deploy.py and execute it.
Hopefully, afterwards you will have a working instance of jenkins that will only be visible to your public IP (via a firewall rule)

Helm functionality has been added to the helm branch, and will be merged after testing in my lab.
(I added a deploy_jenkins_helm.yml file that uses a chart)
to chose between the methods please follow : 

python deploy.py --method kubectl  # For the original method (default)
python deploy.py --method helm     # For the new Helm-based method
