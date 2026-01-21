# Kubernetes Deployment - Complete Setup

This document provides a complete overview of the Kubernetes deployment for the OTP Management Service.

## 📁 Directory Structure

```
k8s/
├── README.md                       # Comprehensive deployment guide
├── QUICKREF.md                     # Quick reference commands
├── deploy.sh                       # Automated deployment script
├── kustomization-example.yaml      # Example kustomization file
│
├── base/                           # Base Kubernetes manifests
│   ├── namespace.yaml              # Namespace definition
│   ├── secret.yaml                 # Secrets (JWT_SECRET, API_KEY)
│   ├── configmap.yaml              # Configuration
│   ├── pvc.yaml                    # Persistent Volume Claim
│   ├── deployment.yaml             # Main deployment
│   ├── service.yaml                # Service definition
│   ├── ingress.yaml                # Ingress with TLS
│   ├── hpa.yaml                    # Horizontal Pod Autoscaler
│   ├── pdb.yaml                    # Pod Disruption Budget
│   ├── networkpolicy.yaml          # Network policies
│   ├── monitoring.yaml             # ServiceMonitor & Alerts
│   └── kustomization.yaml          # Base kustomization
│
└── overlays/                       # Environment-specific configs
    ├── dev/
    │   └── kustomization.yaml      # Dev environment overrides
    ├── staging/
    │   └── kustomization.yaml      # Staging environment overrides
    └── production/
        └── kustomization.yaml      # Production environment overrides
```

## 🚀 Quick Start

### Option 1: Automated Deployment (Recommended)

```bash
# Deploy to production
cd k8s
./deploy.sh deploy --environment production

# Deploy to staging
./deploy.sh deploy --environment staging --registry docker.io/myorg --tag v1.0.0

# Deploy to dev
./deploy.sh deploy --environment dev
```

### Option 2: Manual Deployment

```bash
# 1. Generate secrets
JWT_SECRET=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
API_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")

# 2. Create namespace and secrets
kubectl create namespace otp-service
kubectl create secret generic otp-service-secrets \
  --namespace=otp-service \
  --from-literal=JWT_SECRET="$JWT_SECRET" \
  --from-literal=API_KEY="$API_KEY"

# 3. Deploy using kustomize
kubectl apply -k k8s/overlays/production/

# 4. Verify deployment
kubectl rollout status deployment/otp-service -n otp-service
kubectl get pods -n otp-service
```

## 📋 What's Included

### Base Manifests

1. **Namespace** (`namespace.yaml`)
   - Creates isolated namespace for the service
   - Labels for organization

2. **Secrets** (`secret.yaml`)
   - JWT_SECRET for token signing
   - API_KEY for authentication
   - ⚠️ Replace with secure values before deploying!

3. **ConfigMap** (`configmap.yaml`)
   - Application configuration
   - Rate limiting settings
   - CORS configuration
   - Debug mode toggle

4. **PersistentVolumeClaim** (`pvc.yaml`)
   - 10Gi storage for SQLite database
   - ReadWriteOnce access mode
   - Configurable storage class

5. **Deployment** (`deployment.yaml`)
   - Single replica (SQLite limitation)
   - Security context (non-root user)
   - Resource limits and requests
   - Liveness and readiness probes
   - Environment variables from ConfigMap/Secret

6. **Service** (`service.yaml`)
   - ClusterIP service (internal)
   - Port 80 → 8000 mapping
   - Optional LoadBalancer configuration

7. **Ingress** (`ingress.yaml`)
   - Nginx ingress controller support
   - TLS/SSL with cert-manager
   - Rate limiting annotations
   - Security headers
   - CORS configuration
   - Alternative configurations for Traefik and AWS ALB

8. **HorizontalPodAutoscaler** (`hpa.yaml`)
   - ⚠️ Disabled by default (SQLite doesn't support multiple writers)
   - CPU and memory based scaling
   - Configuration for PostgreSQL migration

9. **PodDisruptionBudget** (`pdb.yaml`)
   - Prevents pod eviction during node drains
   - maxUnavailable: 0 for single replica

10. **NetworkPolicy** (`networkpolicy.yaml`)
    - Ingress: Only from ingress controller
    - Egress: DNS and external APIs
    - Enhanced security

11. **Monitoring** (`monitoring.yaml`)
    - ServiceMonitor for Prometheus
    - PrometheusRule with alerts:
      - Service down
      - High error rate
      - High latency
      - Pod restarts
      - Resource usage

### Environment Overlays

**Development (`overlays/dev/`)**
- Reduced resource limits
- Debug mode enabled
- NodePort service
- CORS open to all origins

**Staging (`overlays/staging/`)**
- Moderate resource limits
- Debug disabled
- Custom ingress host
- Specific CORS origins

**Production (`overlays/production/`)**
- Full resource allocation
- Strict rate limiting
- Pod anti-affinity
- Larger PVC (50Gi)
- Version-tagged images

## ⚙️ Configuration

### Secrets Management

**Option 1: kubectl (Development)**
```bash
kubectl create secret generic otp-service-secrets \
  --namespace=otp-service \
  --from-literal=JWT_SECRET="..." \
  --from-literal=API_KEY="..."
```

**Option 2: Sealed Secrets (Recommended)**
```bash
kubeseal -o yaml < secret.yaml > sealed-secret.yaml
kubectl apply -f sealed-secret.yaml
```

**Option 3: External Secrets Operator (Enterprise)**
- Integrate with AWS Secrets Manager
- Azure Key Vault
- HashiCorp Vault
- Google Secret Manager

### Customization

Edit overlays or create new ones:

```yaml
# overlays/custom/kustomization.yaml
bases:
  - ../../base

patches:
  - target:
      kind: Deployment
    patch: |-
      - op: replace
        path: /spec/replicas
        value: 2
```

## 🔍 Monitoring

### Prometheus Metrics

Access Prometheus:
```bash
kubectl port-forward -n monitoring svc/prometheus-kube-prometheus-prometheus 9090:9090
```

Key metrics:
- `up{job="otp-service"}` - Service availability
- `http_requests_total` - Request count
- `http_request_duration_seconds` - Latency

### Grafana Dashboards

Access Grafana:
```bash
kubectl port-forward -n monitoring svc/prometheus-grafana 3000:80
```

### Alerts

Configured alerts:
- ✅ Service down for 5+ minutes
- ✅ Error rate > 5%
- ✅ 95th percentile latency > 1s
- ✅ Frequent pod restarts
- ✅ High memory usage (>90%)
- ✅ High CPU usage (>90%)

## 🔒 Security Features

1. **Network Policies**
   - Restrict ingress to ingress controller only
   - Allow DNS and necessary egress only

2. **Pod Security**
   - Non-root user (UID 1000)
   - Read-only root filesystem option
   - Drop all capabilities
   - No privilege escalation

3. **Secret Management**
   - Kubernetes secrets with RBAC
   - Support for sealed-secrets
   - External secrets integration

4. **TLS/SSL**
   - Automatic certificate management with cert-manager
   - Force HTTPS redirect
   - Security headers

5. **Rate Limiting**
   - Application-level (in code)
   - Ingress-level (nginx annotations)
   - Per-IP tracking

## ⚠️ Important Considerations

### SQLite Limitations

The default deployment uses SQLite, which has important limitations:

1. **Single Writer**: Only 1 replica supported
2. **No Horizontal Scaling**: Cannot use HPA with SQLite
3. **Storage**: Requires ReadWriteOnce PVC

**Solutions:**
- Migrate to PostgreSQL for production scale
- Use cloud-managed databases (RDS, Cloud SQL)
- Implement application-level caching

### Storage

- Default: 10Gi PVC
- Production: 50Gi recommended
- Backup strategy required
- Consider volume snapshots

### High Availability

With SQLite (current):
- Single pod with PDB to prevent eviction
- Multi-AZ node placement
- Fast pod recovery

With PostgreSQL (future):
- Multiple replicas with HPA
- Database replication
- True high availability

## 📊 Scaling

### Current (SQLite)
```bash
# Keep at 1 replica
kubectl scale deployment otp-service --replicas=1 -n otp-service
```

### Future (PostgreSQL)
```bash
# Scale horizontally
kubectl scale deployment otp-service --replicas=3 -n otp-service

# Enable HPA
kubectl autoscale deployment otp-service \
  --min=2 --max=10 --cpu-percent=70 -n otp-service
```

## 🔧 Troubleshooting

See `QUICKREF.md` for common commands and `README.md` for detailed troubleshooting.

**Common Issues:**

1. **Pods not starting**
   - Check secrets exist
   - Verify image pull
   - Check resource availability

2. **Service not accessible**
   - Verify ingress controller
   - Check DNS/TLS certificates
   - Test service internally

3. **Database locked errors**
   - Ensure only 1 replica
   - Check for zombie pods

## 📚 Additional Resources

- `README.md` - Comprehensive deployment guide
- `QUICKREF.md` - Quick command reference
- `deploy.sh` - Automated deployment script
- Main `../README.md` - Application documentation

## 🎯 Next Steps

1. **Configure Secrets**: Generate secure JWT_SECRET and API_KEY
2. **Setup Domain**: Update ingress with your domain
3. **Configure TLS**: Install cert-manager and configure certificates
4. **Setup Monitoring**: Install Prometheus and Grafana
5. **Configure Backups**: Set up backup CronJob or Velero
6. **Plan Migration**: Consider PostgreSQL for production scale

## 📝 Deployment Checklist

- [ ] Prerequisites installed (kubectl, kustomize)
- [ ] Cluster access configured
- [ ] Secrets generated and configured
- [ ] Docker image built and pushed
- [ ] Ingress controller installed
- [ ] Cert-manager installed (for TLS)
- [ ] Storage class available
- [ ] Monitoring stack installed (optional)
- [ ] Domain DNS configured
- [ ] Backup strategy defined
- [ ] Deployed and verified
- [ ] Monitoring configured
- [ ] Alerts tested

---

For detailed information, see:
- Full deployment guide: `README.md`
- Quick reference: `QUICKREF.md`
- Automated deployment: `./deploy.sh help`
