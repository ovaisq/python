# Kubernetes Deployment Guide

Complete guide for deploying the OTP Management Service to Kubernetes.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Quick Start](#quick-start)
3. [Configuration](#configuration)
4. [Deployment Methods](#deployment-methods)
5. [Environment-Specific Deployments](#environment-specific-deployments)
6. [Scaling Considerations](#scaling-considerations)
7. [Monitoring and Alerts](#monitoring-and-alerts)
8. [Backup and Disaster Recovery](#backup-and-disaster-recovery)
9. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### Required Tools

```bash
# kubectl
curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
sudo install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl

# kustomize
curl -s "https://raw.githubusercontent.com/kubernetes-sigs/kustomize/master/hack/install_kustomize.sh" | bash
sudo mv kustomize /usr/local/bin/

# helm (optional)
curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash
```

### Cluster Requirements

- Kubernetes 1.21+
- Storage class for PersistentVolumes
- Ingress controller (nginx-ingress, traefik, or ALB)
- (Optional) Cert-manager for TLS certificates
- (Optional) Prometheus Operator for monitoring

### Install Cluster Dependencies

**Nginx Ingress Controller:**
```bash
kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/controller-v1.8.2/deploy/static/provider/cloud/deploy.yaml
```

**Cert-Manager (for TLS):**
```bash
kubectl apply -f https://github.com/cert-manager/cert-manager/releases/download/v1.13.0/cert-manager.yaml
```

**Prometheus Operator (for monitoring):**
```bash
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm install prometheus prometheus-community/kube-prometheus-stack -n monitoring --create-namespace
```

---

## Quick Start

### 1. Build and Push Docker Image

```bash
# Build image
docker build -t your-registry/otp-service:v1.0.0 .

# Push to registry
docker push your-registry/otp-service:v1.0.0
```

### 2. Update Secrets

```bash
# Generate secrets
JWT_SECRET=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
API_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")

# Create secret
kubectl create namespace otp-service

kubectl create secret generic otp-service-secrets \
  --namespace=otp-service \
  --from-literal=JWT_SECRET="$JWT_SECRET" \
  --from-literal=API_KEY="$API_KEY"
```

### 3. Deploy Using Kustomize

```bash
# Deploy base configuration
kubectl apply -k k8s/base/

# Or deploy environment-specific configuration
kubectl apply -k k8s/overlays/production/
```

### 4. Verify Deployment

```bash
# Check pods
kubectl get pods -n otp-service

# Check services
kubectl get svc -n otp-service

# Check ingress
kubectl get ingress -n otp-service

# View logs
kubectl logs -n otp-service -l app=otp-service -f
```

---

## Configuration

### Update Secrets in Production

**Option 1: kubectl**
```bash
kubectl create secret generic otp-service-secrets \
  --namespace=otp-service \
  --from-literal=JWT_SECRET="your-secure-jwt-secret" \
  --from-literal=API_KEY="your-secure-api-key" \
  --dry-run=client -o yaml | kubectl apply -f -
```

**Option 2: Sealed Secrets (Recommended)**
```bash
# Install sealed-secrets controller
kubectl apply -f https://github.com/bitnami-labs/sealed-secrets/releases/download/v0.24.0/controller.yaml

# Create sealed secret
echo -n "your-jwt-secret" | kubectl create secret generic otp-service-secrets \
  --namespace=otp-service \
  --from-file=JWT_SECRET=/dev/stdin \
  --dry-run=client -o yaml | \
  kubeseal -o yaml > k8s/base/sealed-secret.yaml

kubectl apply -f k8s/base/sealed-secret.yaml
```

**Option 3: External Secrets Operator**
```bash
# Install External Secrets Operator
helm repo add external-secrets https://charts.external-secrets.io
helm install external-secrets external-secrets/external-secrets -n external-secrets-system --create-namespace

# Create SecretStore (example for AWS Secrets Manager)
cat <<EOF | kubectl apply -f -
apiVersion: external-secrets.io/v1beta1
kind: SecretStore
metadata:
  name: aws-secrets
  namespace: otp-service
spec:
  provider:
    aws:
      service: SecretsManager
      region: us-west-2
      auth:
        jwt:
          serviceAccountRef:
            name: external-secrets-sa
EOF

# Create ExternalSecret
cat <<EOF | kubectl apply -f -
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: otp-service-secrets
  namespace: otp-service
spec:
  secretStoreRef:
    name: aws-secrets
    kind: SecretStore
  target:
    name: otp-service-secrets
  data:
  - secretKey: JWT_SECRET
    remoteRef:
      key: otp-service/jwt-secret
  - secretKey: API_KEY
    remoteRef:
      key: otp-service/api-key
EOF
```

### Update ConfigMap

```bash
kubectl create configmap otp-service-config \
  --namespace=otp-service \
  --from-literal=RATE_LIMIT_REQUESTS=50 \
  --from-literal=RATE_LIMIT_WINDOW=60 \
  --from-literal=DEBUG=false \
  --dry-run=client -o yaml | kubectl apply -f -

# Restart deployment to pick up changes
kubectl rollout restart deployment/otp-service -n otp-service
```

### Update Ingress Host

Edit `k8s/base/ingress.yaml` or use kustomize overlay:

```bash
# In overlays/production/kustomization.yaml
patches:
  - target:
      kind: Ingress
      name: otp-service-ingress
    patch: |-
      - op: replace
        path: /spec/rules/0/host
        value: otp.yourdomain.com
```

---

## Deployment Methods

### Method 1: Using Kustomize (Recommended)

```bash
# Base deployment
kubectl apply -k k8s/base/

# Development environment
kubectl apply -k k8s/overlays/dev/

# Staging environment
kubectl apply -k k8s/overlays/staging/

# Production environment
kubectl apply -k k8s/overlays/production/
```

### Method 2: Using kubectl

```bash
# Create namespace
kubectl apply -f k8s/base/namespace.yaml

# Create secrets (do this first!)
kubectl apply -f k8s/base/secret.yaml

# Apply all manifests
kubectl apply -f k8s/base/
```

### Method 3: Using Helm (Create Chart First)

```bash
# Create helm chart
helm create otp-service-chart

# Install
helm install otp-service ./otp-service-chart \
  --namespace otp-service \
  --create-namespace \
  --set image.tag=v1.0.0 \
  --set secrets.jwtSecret="$JWT_SECRET" \
  --set secrets.apiKey="$API_KEY"
```

### Method 4: ArgoCD (GitOps)

```yaml
# argocd-application.yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: otp-service
  namespace: argocd
spec:
  project: default
  source:
    repoURL: https://github.com/yourorg/otp-service
    targetRevision: HEAD
    path: k8s/overlays/production
  destination:
    server: https://kubernetes.default.svc
    namespace: otp-service
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
    syncOptions:
    - CreateNamespace=true
```

```bash
kubectl apply -f argocd-application.yaml
```

---

## Environment-Specific Deployments

### Development

```bash
# Deploy to dev
kubectl apply -k k8s/overlays/dev/

# Port forward for local testing
kubectl port-forward -n otp-service-dev svc/otp-service-dev 8000:80

# Test
curl http://localhost:8000/health
```

### Staging

```bash
# Deploy to staging
kubectl apply -k k8s/overlays/staging/

# Get ingress URL
kubectl get ingress -n otp-service-staging
```

### Production

```bash
# Deploy to production
kubectl apply -k k8s/overlays/production/

# Verify deployment
kubectl rollout status deployment/otp-service -n otp-service

# Check pods
kubectl get pods -n otp-service -w
```

---

## Scaling Considerations

### ⚠️ Important: SQLite Limitations

The default deployment uses SQLite, which **does NOT support concurrent writes**. This means:

- **DO NOT scale replicas > 1 with SQLite**
- Multiple pods will cause database locks and errors
- Data corruption may occur

### Options for Scaling

**Option 1: Migrate to PostgreSQL (Recommended)**

1. Deploy PostgreSQL:
```bash
helm install postgresql bitnami/postgresql \
  --namespace otp-service \
  --set auth.username=otpuser \
  --set auth.password=secure-password \
  --set auth.database=otpdb
```

2. Update application to use PostgreSQL (modify `app.py`)

3. Scale deployment:
```bash
kubectl scale deployment otp-service --replicas=3 -n otp-service
```

**Option 2: Use ReadWriteMany PVC with NFS**

1. Setup NFS storage class
2. Update PVC to use `ReadWriteMany`
3. Implement file locking in application
4. Scale with caution

**Option 3: Keep Single Replica with High Availability**

- Use `maxUnavailable: 0` in PodDisruptionBudget
- Deploy on multiple availability zones with node affinity
- Use cluster autoscaling for node-level HA

### Horizontal Pod Autoscaling (HPA)

Only enable after migrating from SQLite:

```bash
# Ensure metrics-server is installed
kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml

# HPA is already configured in k8s/base/hpa.yaml
# Update minReplicas and maxReplicas after migration
kubectl edit hpa otp-service-hpa -n otp-service
```

---

## Monitoring and Alerts

### View Logs

```bash
# Real-time logs
kubectl logs -n otp-service -l app=otp-service -f

# Previous pod logs
kubectl logs -n otp-service -l app=otp-service --previous

# All pods
kubectl logs -n otp-service --all-containers=true -f
```

### Prometheus Metrics

Access Prometheus:
```bash
kubectl port-forward -n monitoring svc/prometheus-kube-prometheus-prometheus 9090:9090
```

Visit: http://localhost:9090

Query examples:
```promql
# Request rate
rate(http_requests_total{namespace="otp-service"}[5m])

# Error rate
rate(http_requests_total{namespace="otp-service",status=~"5.."}[5m])

# Pod restarts
kube_pod_container_status_restarts_total{namespace="otp-service"}
```

### Grafana Dashboards

Access Grafana:
```bash
kubectl port-forward -n monitoring svc/prometheus-grafana 3000:80
```

Default credentials: admin/prom-operator

Import dashboards:
- Kubernetes Cluster Monitoring (ID: 7249)
- Kubernetes Pod Monitoring (ID: 6417)

### Alerts

Alerts are configured in `k8s/base/monitoring.yaml`:

- Service Down
- High Error Rate
- High Latency
- Pod Restarting
- High Memory/CPU Usage

View alerts:
```bash
kubectl port-forward -n monitoring svc/prometheus-kube-prometheus-alertmanager 9093:9093
```

---

## Backup and Disaster Recovery

### Database Backup

**Create Backup CronJob:**

```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: otp-backup
  namespace: otp-service
spec:
  schedule: "0 2 * * *"  # Daily at 2 AM
  jobTemplate:
    spec:
      template:
        spec:
          containers:
          - name: backup
            image: alpine
            command:
            - /bin/sh
            - -c
            - |
              apk add --no-cache sqlite
              DATE=$(date +%Y%m%d_%H%M%S)
              sqlite3 /data/otp_manager.db ".backup /backup/otp_manager_$DATE.db"
              find /backup -name "*.db" -mtime +30 -delete
            volumeMounts:
            - name: data
              mountPath: /data
            - name: backup
              mountPath: /backup
          volumes:
          - name: data
            persistentVolumeClaim:
              claimName: otp-service-pvc
          - name: backup
            persistentVolumeClaim:
              claimName: otp-backup-pvc
          restartPolicy: OnFailure
```

**Create Backup PVC:**

```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: otp-backup-pvc
  namespace: otp-service
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 50Gi
```

### Restore from Backup

```bash
# Find backup pod
kubectl get pods -n otp-service

# Copy backup to local
kubectl cp otp-service/otp-service-xxx:/data/otp_manager.db ./backup.db

# Scale down deployment
kubectl scale deployment otp-service --replicas=0 -n otp-service

# Copy backup to pod
kubectl cp ./backup.db otp-service/otp-service-xxx:/data/otp_manager.db

# Scale up deployment
kubectl scale deployment otp-service --replicas=1 -n otp-service
```

### Disaster Recovery

**Option 1: Velero (Full Cluster Backup)**

```bash
# Install Velero
velero install \
  --provider aws \
  --plugins velero/velero-plugin-for-aws:v1.8.0 \
  --bucket velero-backups \
  --secret-file ./credentials-velero

# Backup namespace
velero backup create otp-service-backup --include-namespaces otp-service

# Restore
velero restore create --from-backup otp-service-backup
```

**Option 2: Manual PVC Snapshot**

```bash
# Create VolumeSnapshot
kubectl apply -f - <<EOF
apiVersion: snapshot.storage.k8s.io/v1
kind: VolumeSnapshot
metadata:
  name: otp-data-snapshot
  namespace: otp-service
spec:
  volumeSnapshotClassName: csi-snapclass
  source:
    persistentVolumeClaimName: otp-service-pvc
EOF

# Restore from snapshot
kubectl apply -f - <<EOF
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: otp-service-pvc-restored
  namespace: otp-service
spec:
  dataSource:
    name: otp-data-snapshot
    kind: VolumeSnapshot
    apiGroup: snapshot.storage.k8s.io
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 10Gi
EOF
```

---

## Troubleshooting

### Pod Won't Start

```bash
# Check pod status
kubectl describe pod -n otp-service -l app=otp-service

# Check events
kubectl get events -n otp-service --sort-by='.lastTimestamp'

# Check logs
kubectl logs -n otp-service -l app=otp-service

# Common issues:
# 1. Image pull errors - check image name and registry credentials
# 2. Missing secrets - ensure secrets are created
# 3. Resource limits - check if cluster has enough resources
```

### Service Not Accessible

```bash
# Check service
kubectl get svc -n otp-service

# Check endpoints
kubectl get endpoints -n otp-service

# Check ingress
kubectl describe ingress -n otp-service otp-service-ingress

# Test service internally
kubectl run -it --rm debug --image=alpine --restart=Never -n otp-service -- sh
# Inside pod:
apk add curl
curl http://otp-service/health
```

### Database Locked Errors

```bash
# Check number of replicas
kubectl get deployment -n otp-service

# If replicas > 1 with SQLite, scale down
kubectl scale deployment otp-service --replicas=1 -n otp-service

# Check for stuck pods
kubectl get pods -n otp-service
kubectl delete pod <stuck-pod> -n otp-service
```

### High Memory Usage

```bash
# Check memory usage
kubectl top pods -n otp-service

# Increase memory limits
kubectl patch deployment otp-service -n otp-service --type='json' -p='[
  {"op": "replace", "path": "/spec/template/spec/containers/0/resources/limits/memory", "value": "1Gi"}
]'
```

### Certificate Issues

```bash
# Check certificate
kubectl describe certificate -n otp-service

# Check cert-manager logs
kubectl logs -n cert-manager -l app=cert-manager -f

# Manually trigger certificate renewal
kubectl delete secret otp-service-tls -n otp-service
kubectl delete certificate otp-service-tls -n otp-service
```

### Rate Limiting Issues

```bash
# Check rate limit configuration
kubectl get configmap otp-service-config -n otp-service -o yaml

# Adjust rate limits
kubectl edit configmap otp-service-config -n otp-service

# Restart pods
kubectl rollout restart deployment/otp-service -n otp-service
```

---

## Useful Commands

```bash
# Get all resources in namespace
kubectl get all -n otp-service

# Delete deployment
kubectl delete -k k8s/base/

# Force delete stuck pod
kubectl delete pod <pod-name> -n otp-service --grace-period=0 --force

# Execute command in pod
kubectl exec -it -n otp-service <pod-name> -- /bin/sh

# Copy files to/from pod
kubectl cp <local-file> otp-service/<pod-name>:/path/to/file
kubectl cp otp-service/<pod-name>:/path/to/file <local-file>

# View resource usage
kubectl top nodes
kubectl top pods -n otp-service

# Get YAML of running resource
kubectl get deployment otp-service -n otp-service -o yaml
```

---

## Next Steps

1. **Configure TLS:** Set up cert-manager and update ingress with your domain
2. **Setup Monitoring:** Install Prometheus and Grafana
3. **Configure Backups:** Set up automated backups with Velero or CronJobs
4. **Migrate Database:** Consider migrating to PostgreSQL for production scale
5. **CI/CD Integration:** Set up automated deployments with ArgoCD or Flux
