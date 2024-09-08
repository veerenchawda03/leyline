# Project Title

This project demonstrates the use of Docker, Docker Compose and Helm for deploying and managing a containerized application.
It is divided into 2 types basic and advanced.
Basic is hosted on master branch and advanced is hosted on develop branch. 

## Features of basic project

- ✅ **App**: The application is written with Python3 and Flask.
- ✅ **Dockerfile**: A `Dockerfile` is included to build a Docker image of the application.
- ✅ **Docker Compose**: A `docker-compose.yml` file is provided to manage multi-container Docker applications.
- ✅ **Docker Hub**: The pre-built Docker image is available on [Docker Hub](https://hub.docker.com/r/veeren03/veeren-leyline).
- ✅ **Helm Chart**: A Helm chart is available for deploying the application in Kubernetes.
- ✅ **Jenkinsfile**: Jenkinsfile is added to deploy the app to AWS EKS cluster via Helm chart.



## How to install and run the application on Mac/Linux. Windows installation steps may differ.

- Git clone the repo and navigate to the directory
- Install and open Docker on local machine
- Run this command to check if any other app is using port 3000 ` netstat -vanp tcp | grep 3000`. Kill that process since our app is also going to run on port 3000
- You will require my AWS credentials, as the database is AWS DynamoDB. I am sharing with you on email and steps to use it as env variables.
- Run `docker-compose up -d --build `. This will run the docker image with tag `latest`. I have pushed the latest code inside the docker from my local machine for you to test.
- Run `docker ps` to check if container has started.

- Navigate to localhost:3000 to access the application
- List of API endpoints available are:
    - /home - It is created to generate metrics for prometheus. Hitting this endpoint will increase a counter, which can be accessed at the /metrics endpoint
    - /metrics - Created for Prometheus to scrape
    - /health - Returns health status of app
    - / (root) - Returns version of the app along with time and if hosted on kubernetes
    - /v1/tools/validate - Checks if the parameter passed is a valid IPV4 adddress 
    - /v1/tools/lookup - Fetches IP address pertaining to domain name passed in the parameter and if so, stores it in AWS DynamoDB. Basically does a `dig` command
    - /v1/history - Returns the last 20 entries in Database using `queryID` as index.
    - /shutdown will reject all new incoming requests, wait for all ongoing requests to complete and then kill the server process.

- Once testing is done, run `docker-compose down`


## How to install and run the application on Kubernetes.
- You will require a Kubernetes cluster in any cloud/docker desktop. I have assumed a cluster AWS EKSnamed `my-cluster` in region `us-east-1` for Jenkinsfile sake.
- Configure your own cluster credentials on local if not AWS. If using docker desktop, simply enable Kubernetes from the docker desktop settings. Reference https://docs.docker.com/desktop/kubernetes/
- If AWS, Download the kubeconfig on local machine using example command `eksctl utils write-kubeconfig --cluster <cluster-name> --region <region>`
- cd into the git directory, outside the helm chart named  `veeren-leyline`
- Execute this command --- ``` helm install release1 veeren-leyline \
                    --set secrets.awsAccessKeyId="`echo -n $AWS_ACCESS_KEY_ID`" \
                    --set secrets.awsSecretAccessKey="`echo -n $AWS_SECRET_ACCESS_KEY`" ```


 

    
## Features of Advanced project

- Terraform for EC2 for Jenkins and EKS 
- FluxCD

####  Since I have used CI/CD tool as Jenkins, we will require a EC2 machine. I have provided a terraform configuration inside `/veeren-leyline/terraform/ec2` for it.

#### Since we will also require a kubernetes cluster, I have provided a sample terraform file for creating a AWS EKS cluster. The terraform configuration is inside `/veeren-leyline/terraform/eks`

#### Along with EKS cluster provisioning, we will also install FluxCD in the cluster, as I prefer GitOps with FluxCD for Kubernetes related deployment. 

#### Please note that I have simply installed the Flux Operators on the clusters and the Source definitions and configurations are pending as this is a good to have in an assignment limited by time.



