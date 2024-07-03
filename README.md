Hey everyone :)

This is a basic python based orchestration, here is what it does : 
It will check for pre existing resources to handle exceptions,
spin them up in the google cloud cli using terraform,
then it will install ansible and configure the resources using it.

To deploy : 

Clone the repo to your gcloud shell,fill out the variables.tfvars in terraform dir,chmod +x the deploy.py and execute it.
Hopefully, afterwards you will have a working instance of jenkins that will only be visible to your public IP (via a firewall rule)
