#!/bin/bash
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NAMESPACE="${NAMESPACE:-otp-service}"
ENVIRONMENT="${ENVIRONMENT:-production}"
IMAGE_REGISTRY="${IMAGE_REGISTRY:-}"
IMAGE_TAG="${IMAGE_TAG:-latest}"

print_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_header() {
    echo ""
    echo "=================================="
    echo "$1"
    echo "=================================="
    echo ""
}

check_prerequisites() {
    print_header "Checking Prerequisites"
    
    # Check kubectl
    if ! command -v kubectl &> /dev/null; then
        print_error "kubectl is not installed"
        exit 1
    fi
    print_info "kubectl: $(kubectl version --client --short 2>/dev/null || kubectl version --client)"
    
    # Check kustomize
    if ! command -v kustomize &> /dev/null; then
        print_warn "kustomize not found, using kubectl kustomize"
        KUSTOMIZE_CMD="kubectl kustomize"
    else
        print_info "kustomize: $(kustomize version --short 2>/dev/null || kustomize version)"
        KUSTOMIZE_CMD="kustomize build"
    fi
    
    # Check cluster access
    if ! kubectl cluster-info &> /dev/null; then
        print_error "Cannot access Kubernetes cluster"
        exit 1
    fi
    print_info "Cluster: $(kubectl config current-context)"
}

generate_secrets() {
    print_header "Generating Secrets"
    
    # Check if secrets already exist
    if kubectl get secret otp-service-secrets -n "$NAMESPACE" &> /dev/null; then
        print_warn "Secrets already exist in namespace $NAMESPACE"
        read -p "Do you want to regenerate them? (y/N) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            print_info "Using existing secrets"
            return
        fi
    fi
    
    # Generate new secrets
    JWT_SECRET=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))" 2>/dev/null || openssl rand -base64 32)
    API_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))" 2>/dev/null || openssl rand -base64 32)
    
    print_info "Generated JWT_SECRET: ${JWT_SECRET:0:10}..."
    print_info "Generated API_KEY: ${API_KEY:0:10}..."
    
    # Create namespace if it doesn't exist
    kubectl create namespace "$NAMESPACE" --dry-run=client -o yaml | kubectl apply -f -
    
    # Create secret
    kubectl create secret generic otp-service-secrets \
        --namespace="$NAMESPACE" \
        --from-literal=JWT_SECRET="$JWT_SECRET" \
        --from-literal=API_KEY="$API_KEY" \
        --dry-run=client -o yaml | kubectl apply -f -
    
    print_info "Secrets created/updated"
    
    # Save to file for reference
    cat > "$SCRIPT_DIR/.secrets-$NAMESPACE" <<EOF
# OTP Service Secrets - $(date)
# Store these securely!
JWT_SECRET=$JWT_SECRET
API_KEY=$API_KEY
EOF
    chmod 600 "$SCRIPT_DIR/.secrets-$NAMESPACE"
    print_info "Secrets saved to .secrets-$NAMESPACE (keep this safe!)"
}

build_and_push_image() {
    print_header "Building and Pushing Docker Image"
    
    if [ -z "$IMAGE_REGISTRY" ]; then
        print_warn "IMAGE_REGISTRY not set, skipping image build"
        return
    fi
    
    IMAGE_NAME="$IMAGE_REGISTRY/otp-service:$IMAGE_TAG"
    print_info "Building image: $IMAGE_NAME"
    
    cd "$SCRIPT_DIR/.."
    docker build -t "$IMAGE_NAME" .
    
    print_info "Pushing image: $IMAGE_NAME"
    docker push "$IMAGE_NAME"
    
    print_info "Image built and pushed successfully"
}

deploy_application() {
    print_header "Deploying Application"
    
    OVERLAY_PATH="$SCRIPT_DIR/overlays/$ENVIRONMENT"
    
    if [ ! -d "$OVERLAY_PATH" ]; then
        print_error "Environment overlay not found: $OVERLAY_PATH"
        print_info "Available environments: $(ls -d $SCRIPT_DIR/overlays/*/ | xargs -n 1 basename)"
        exit 1
    fi
    
    print_info "Deploying environment: $ENVIRONMENT"
    print_info "Overlay path: $OVERLAY_PATH"
    
    # Apply kustomization
    if kubectl apply -k "$OVERLAY_PATH"; then
        print_info "Deployment successful"
    else
        print_error "Deployment failed"
        exit 1
    fi
}

wait_for_deployment() {
    print_header "Waiting for Deployment"
    
    print_info "Waiting for pods to be ready..."
    if kubectl wait --for=condition=ready pod -l app=otp-service -n "$NAMESPACE" --timeout=300s; then
        print_info "All pods are ready"
    else
        print_error "Pods did not become ready in time"
        print_info "Check pod status:"
        kubectl get pods -n "$NAMESPACE" -l app=otp-service
        exit 1
    fi
    
    print_info "Checking deployment rollout status..."
    kubectl rollout status deployment/otp-service -n "$NAMESPACE" --timeout=300s
}

verify_deployment() {
    print_header "Verifying Deployment"
    
    # Check pods
    print_info "Pods:"
    kubectl get pods -n "$NAMESPACE" -l app=otp-service
    
    # Check service
    print_info "Services:"
    kubectl get svc -n "$NAMESPACE" -l app=otp-service
    
    # Check ingress
    print_info "Ingress:"
    kubectl get ingress -n "$NAMESPACE"
    
    # Test health endpoint
    print_info "Testing health endpoint..."
    POD_NAME=$(kubectl get pod -n "$NAMESPACE" -l app=otp-service -o jsonpath="{.items[0].metadata.name}")
    
    if kubectl exec -n "$NAMESPACE" "$POD_NAME" -- wget -q -O- http://localhost:8000/health | grep -q "healthy"; then
        print_info "Health check passed!"
    else
        print_warn "Health check may have issues"
    fi
}

show_access_info() {
    print_header "Access Information"
    
    # Get ingress host
    INGRESS_HOST=$(kubectl get ingress -n "$NAMESPACE" -o jsonpath='{.items[0].spec.rules[0].host}' 2>/dev/null)
    
    if [ -n "$INGRESS_HOST" ]; then
        print_info "Service URL: https://$INGRESS_HOST"
        print_info "Health check: https://$INGRESS_HOST/health"
    else
        print_warn "No ingress found"
        print_info "Use port-forward to access service:"
        echo "  kubectl port-forward -n $NAMESPACE svc/otp-service 8000:80"
    fi
    
    # Show API key
    if [ -f "$SCRIPT_DIR/.secrets-$NAMESPACE" ]; then
        API_KEY=$(grep API_KEY "$SCRIPT_DIR/.secrets-$NAMESPACE" | cut -d= -f2)
        print_info "API Key: $API_KEY"
        echo ""
        print_info "Get access token:"
        if [ -n "$INGRESS_HOST" ]; then
            echo "  curl -X POST https://$INGRESS_HOST/api/v1/token \\"
        else
            echo "  curl -X POST http://localhost:8000/api/v1/token \\"
        fi
        echo "    -H 'Content-Type: application/json' \\"
        echo "    -d '{\"api_key\": \"$API_KEY\"}'"
    fi
}

cleanup() {
    print_header "Cleanup"
    
    read -p "Are you sure you want to delete all resources in namespace $NAMESPACE? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        print_info "Cleanup cancelled"
        return
    fi
    
    print_warn "Deleting all resources..."
    kubectl delete namespace "$NAMESPACE"
    print_info "Cleanup complete"
}

show_logs() {
    print_header "Application Logs"
    
    print_info "Streaming logs from all pods..."
    kubectl logs -n "$NAMESPACE" -l app=otp-service --all-containers=true -f
}

show_usage() {
    cat << EOF
OTP Service Kubernetes Deployment Script

Usage: $0 [command] [options]

Commands:
    deploy          Deploy the application (default)
    secrets         Generate and apply secrets only
    build           Build and push Docker image
    verify          Verify deployment
    logs            Show application logs
    cleanup         Delete all resources
    help            Show this help message

Options:
    --environment   Deployment environment (dev|staging|production) [default: production]
    --namespace     Kubernetes namespace [default: otp-service]
    --registry      Docker registry for image
    --tag           Image tag [default: latest]

Examples:
    # Deploy to production
    $0 deploy --environment production

    # Deploy to dev with custom registry
    $0 deploy --environment dev --registry docker.io/myorg --tag v1.0.0

    # Only generate secrets
    $0 secrets --namespace otp-service

    # View logs
    $0 logs --namespace otp-service

Environment Variables:
    ENVIRONMENT     Deployment environment
    NAMESPACE       Kubernetes namespace
    IMAGE_REGISTRY  Docker registry
    IMAGE_TAG       Image tag

EOF
}

# Parse command line arguments
COMMAND="${1:-deploy}"
shift || true

while [[ $# -gt 0 ]]; do
    case $1 in
        --environment)
            ENVIRONMENT="$2"
            shift 2
            ;;
        --namespace)
            NAMESPACE="$2"
            shift 2
            ;;
        --registry)
            IMAGE_REGISTRY="$2"
            shift 2
            ;;
        --tag)
            IMAGE_TAG="$2"
            shift 2
            ;;
        *)
            print_error "Unknown option: $1"
            show_usage
            exit 1
            ;;
    esac
done

# Main execution
case $COMMAND in
    deploy)
        check_prerequisites
        generate_secrets
        build_and_push_image
        deploy_application
        wait_for_deployment
        verify_deployment
        show_access_info
        ;;
    secrets)
        check_prerequisites
        generate_secrets
        ;;
    build)
        build_and_push_image
        ;;
    verify)
        check_prerequisites
        verify_deployment
        show_access_info
        ;;
    logs)
        check_prerequisites
        show_logs
        ;;
    cleanup)
        check_prerequisites
        cleanup
        ;;
    help|--help|-h)
        show_usage
        ;;
    *)
        print_error "Unknown command: $COMMAND"
        show_usage
        exit 1
        ;;
esac

print_info "Done!"
