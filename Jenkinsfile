
pipeline {
    agent any

    options {
        timestamps ()
        timeout(time: 1, unit: 'HOURS')
    }
    stages {
        stage('Pull Latest Code') {
            steps {
                script {
                    git \
                        branch: "${ghprbSourceBranch}",  
                        credentialsId: 'jenkins_github_readonly',
                        url: "https://github.com/veerenchawda03/leyline"
                }
            }
        }

        stage('Docker build and push') {
            steps {
                script {
                    def app_version = params.app_version
                    sh '''
                    
                    cd veeren-leyline
                    ls
                    docker build . -t veeren03/veeren-leylein:$app_version
                    docker push veeren03/veeren-leyline:$app_version
                    
                    '''
                }
            }
        }

        stage('Helm lint and template') {
            steps {
                script {
                    sh '''
                    cd veeren-leyline
                    ls
                    helm lint veeren-leyline
                    helm template release1 veeren-leyline 

                    '''
                }
            }
        }
        stage('Get kubeconfig and Helm apply') {
            steps {
                script {
                    def app_version = params.app_version

                    sh '''
                    cd veeren-leyline
                    ls
                    SECRET=$(aws secretsmanager get-secret-value --secret-id leyline --region ap-south-1 --query SecretString --output text)
                    export AWS_ACCESS_KEY_ID=$(echo $SECRET | jq -r '.AWS_ACCESS_KEY_ID')
                    export AWS_SECRET_ACCESS_KEY=$(echo $SECRET | jq -r '.AWS_SECRET_ACCESS_KEY')
                    eksctl utils write-kubeconfig --cluster my-cluster --region us-east-1

                    helm upgrade release1 veeren-leyline \
                    --set secrets.awsAccessKeyId="`echo -n $AWS_ACCESS_KEY_ID`" \
                    --set secrets.awsSecretAccessKey="`echo -n $AWS_SECRET_ACCESS_KEY`" \
                    --set image.tag=$app_version \
                    --set version=$app_version

                    '''
                }
            }
        }


      
    }

}

