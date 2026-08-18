Enterprise RAG System (Kubernetes + CI/CD)An enterprise-grade Retrieval-Augmented Generation (RAG) application deployed on Azure Kubernetes Service (AKS) with automated testing, Docker container packaging via GitHub Container Registry (GHCR), and dynamic rolling deployments using GitHub Actions.🏗️ Architecture OverviewFrontend: Streamlit App (Dockerfile.streamlit)Backend: FastAPI REST API (Dockerfile)Database: Neon Serverless PostgreSQL (Managed)Storage: Azure Disk via PersistentVolumeClaim (RWX / RWO K8s storage for FAISS/Uploads)Ingress & SSL: NGINX Ingress Controller with Let's Encrypt / Cert-ManagerOrchestration: Azure Kubernetes Service (AKS)CI/CD: GitHub Actions + GHCR🛠️ Repository StructurePlaintext.
├── .github/workflows/
│   └── ci-cd.yaml              # Complete CI/CD Pipeline
├── app/                        # FastAPI Application Code
├── tests/                      # Automated PyTest Test Suite
├── k8s/                        # Kubernetes Deployment Manifests
│   ├── 01-namespace.yaml
│   ├── 02-configmap.yaml
│   ├── 03-pvc.yaml
│   ├── 04-fastapi-deployment.yaml
│   ├── 05-fastapi-service.yaml
│   ├── 06-ingress.yaml
│   ├── 07-frontend-deployment.yaml
│   └── 08-frontend-service.yaml
├── Dockerfile                  # Backend Image
├── Dockerfile.streamlit        # Frontend Image
├── requirements.txt            # Python Dependencies
└── streamlit.py                # Streamlit UI Application
🔄 CI/CD Automation FlowEvery git push or merge to the main branch automatically triggers the pipeline:Test Phase: Spins up an isolated PostgreSQL container service and runs pytest -v across the codebase.Build & Push Phase: Builds both Backend and Frontend Docker images and pushes them to GHCR tagged with :latest and :${{ github.sha }}.Deploy Phase: Authenticates with Azure via Service Principal credentials, points kubectl to the AKS Cluster, and executes rolling updates using kubectl set image.🔐 Required GitHub Secrets SetupTo enable automated deployments to AKS, configure the following secret in GitHub Repo $\rightarrow$ Settings $\rightarrow$ Secrets and variables $\rightarrow$ Actions:AZURE_CREDENTIALS: Output JSON from the Azure Service Principal creation command.Generate Azure Credentials JSONRun this command in Azure CLI / Cloud Shell:Bashaz ad sp create-for-rbac \
  --name "github-actions-rag" \
  --role contributor \
  --scopes /subscriptions/<YOUR_SUBSCRIPTION_ID>/resourceGroups/<YOUR_RESOURCE_GROUP> \
  --sdk-auth
🚀 Manual Local & Kubernetes Commands1. Create GHCR Secret in AKS ClusterTo allow AKS to pull private images from GHCR:Bashkubectl create secret docker-registry ghcr-secret \
  --docker-server=https://ghcr.io \
  --docker-username=<YOUR_GITHUB_USERNAME> \
  --docker-password=<YOUR_GITHUB_PAT> \
  --docker-email=<YOUR_EMAIL>
2. Apply Manifests Manually (First Time Deployment)Bashkubectl apply -f k8s/
3. Check Rollout & Pod StatusBashkubectl get pods -w
kubectl get ingress
🔒 Environment & ConfigurationProduction secrets (Database URLs, API Keys) are stored directly inside Kubernetes Secrets (rag-secrets), while non-sensitive runtime parameters are managed via the Kubernetes ConfigMap (rag-config).
