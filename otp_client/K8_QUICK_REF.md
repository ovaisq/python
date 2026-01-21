# Kubernetes Quick Reference

Quick commands for managing the OTP Service on Kubernetes.

## Deployment

```bash
# Deploy to production
./k8s/deploy.sh deploy --environment production

# Deploy to staging
./k8s/deploy.sh deploy --environment staging

# Deploy to dev
./k8s/deploy.sh deploy --environment dev

# Deploy with custom image
./k8s/deploy.sh deploy --registry docker.io/myorg --tag v1.0.0
```

## Manual Deployment

```bash
# Create namespace and secrets first
kubectl create namespace otp-service
kubectl create secret generic otp-service-secrets \
  --namespace=otp-service \
  --from-literal=JWT_SECRET="your-secret" \
  --from-literal=API_KEY="your-key"

# Deploy using kustomize
kubectl apply -k k8s/overlays/production/

# Or deploy base
kubectl apply -k k8s/base/
```

## Monitoring

```bash
# Watch pods
kubectl get pods -n otp-service -w

# View logs
kubectl logs -n otp-service -l app=otp-service -f

# View previous logs
kubectl logs -n otp-service -l app=otp-service --previous

# Describe pod
kubectl describe pod -n otp-service <pod-name>

# Get events
kubectl get events -n otp-service --sort-by='.lastTimestamp'
```

## Debugging

```bash
# Port forward to service
kubectl port-forward -n otp-service svc/otp-service 8000:80

# Execute shell in pod
kubectl exec -it -n otp-service <pod-name> -- /bin/sh

# Check service endpoints
kubectl get endpoints -n otp-service

# Test service internally
kubectl run -it --rm debug --image=alpine --restart=Never -n otp-service -- sh
```

## Updates

```bash
# Update image
kubectl set image deployment/otp-service -n otp-service \
  otp-service=your-registry/otp-service:v1.0.1

# Rollout status
kubectl rollout status deployment/otp-service -n otp-service

# Rollout history
kubectl rollout history deployment/otp-service -n otp-service

# Rollback
kubectl rollout undo deployment/otp-service -n otp-service

# Restart deployment
kubectl rollout restart deployment/otp-service -n otp-service
```

## Scaling

```bash
# Scale deployment (WARNING: only with PostgreSQL, not SQLite!)
kubectl scale deployment otp-service --replicas=3 -n otp-service

# Autoscaling
kubectl autoscale deployment otp-service \
  --min=2 --max=10 --cpu-percent=70 -n otp-service

# Check HPA
kubectl get hpa -n otp-service
```

## Configuration

```bash
# Update ConfigMap
kubectl edit configmap otp-service-config -n otp-service

# Update Secret
kubectl edit secret otp-service-secrets -n otp-service

# View ConfigMap
kubectl get configmap otp-service-config -n otp-service -o yaml

# View Secret (base64 decoded)
kubectl get secret otp-service-secrets -n otp-service -o jsonpath='{.data.API_KEY}' | base64 -d
```

## Resource Management

```bash
# View resource usage
kubectl top pods -n otp-service
kubectl top nodes

# Describe resources
kubectl describe deployment otp-service -n otp-service
kubectl describe svc otp-service -n otp-service
kubectl describe ingress -n otp-service

# Get all resources
kubectl get all -n otp-service
```

## Backup & Restore

```bash
# Backup database (copy from pod)
kubectl cp otp-service/<pod-name>:/data/otp_manager.db ./backup.db

# Restore database
# 1. Scale down
kubectl scale deployment otp-service --replicas=0 -n otp-service
# 2. Copy backup
kubectl cp ./backup.db otp-service/<pod-name>:/data/otp_manager.db
# 3. Scale up
kubectl scale deployment otp-service --replicas=1 -n otp-service
```

## Cleanup

```bash
# Delete deployment
kubectl delete -k k8s/overlays/production/

# Delete namespace (deletes everything)
kubectl delete namespace otp-service

# Delete specific resource
kubectl delete deployment otp-service -n otp-service
kubectl delete svc otp-service -n otp-service
```

## Troubleshooting

```bash
# Pod crash looping
kubectl describe pod -n otp-service <pod-name>
kubectl logs -n otp-service <pod-name> --previous

# Image pull errors
kubectl describe pod -n otp-service <pod-name> | grep -A 10 Events

# Service not accessible
kubectl get endpoints -n otp-service
kubectl describe ingress -n otp-service

# Certificate issues
kubectl describe certificate -n otp-service
kubectl logs -n cert-manager -l app=cert-manager

# Force delete stuck pod
kubectl delete pod <pod-name> -n otp-service --grace-period=0 --force
```

## Testing

```bash
# Port forward
kubectl port-forward -n otp-service svc/otp-service 8000:80

# Health check
curl http://localhost:8000/health

# Get token
curl -X POST http://localhost:8000/api/v1/token \
  -H "Content-Type: application/json" \
  -d '{"api_key": "your-api-key"}'

# Create client
curl -X POST http://localhost:8000/api/v1/clients \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "TestClient"}'
```

## Useful Aliases

Add to your `~/.bashrc` or `~/.zshrc`:

```bash
alias k='kubectl'
alias kns='kubectl config set-context --current --namespace'
alias kgp='kubectl get pods'
alias kgs='kubectl get svc'
alias kgd='kubectl get deploy'
alias kl='kubectl logs'
alias kd='kubectl describe'
alias ke='kubectl exec -it'

# OTP Service specific
alias otp-logs='kubectl logs -n otp-service -l app=otp-service -f'
alias otp-pods='kubectl get pods -n otp-service'
alias otp-restart='kubectl rollout restart deployment/otp-service -n otp-service'
```

## Common Issues

**Issue: Pod won't start**
```bash
# Check for missing secrets
kubectl get secret -n otp-service

# Check for image pull errors
kubectl describe pod -n otp-service <pod-name> | grep Image
```

**Issue: Service not accessible**
```bash
# Check if pods are ready
kubectl get pods -n otp-service

# Check service endpoints
kubectl get endpoints -n otp-service otp-service

# Check ingress
kubectl describe ingress -n otp-service
```

**Issue: Database locked**
```bash
# Check replicas (should be 1 for SQLite)
kubectl get deployment -n otp-service

# Scale to 1
kubectl scale deployment otp-service --replicas=1 -n otp-service
```
