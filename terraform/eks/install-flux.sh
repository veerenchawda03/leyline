curl -s https://fluxcd.io/install.sh | sudo bash
export GITHUB_TOKEN=$GITHUB_PAT_TOKEN
export GITHUB_USER=veerenchawda03
flux check --pre
flux bootstrap github \
  --owner=$GITHUB_USER \
  --repository=veeren-leyline \
  --branch=main \
  --path=./clusters/my-cluster \
  --components source-controller,kustomize-controller,helm-controller,notification-controller

  