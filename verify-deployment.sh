#!/bin/bash
# Deployment verification script for Launch the Nukes

set -e

# Configuration
PROJECT_ID="${GOOGLE_CLOUD_PROJECT:-launch-the-nukes}"
REGION="${REGION:-us-central1}"
SERVICE_NAME="launch-the-nukes-frontend"
JOB_NAME="launch-the-nukes-worker"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check if gcloud is available and authenticated
check_gcloud() {
    print_status "Checking gcloud setup..."
    
    if ! command -v gcloud &> /dev/null; then
        print_error "gcloud CLI not found. Please install it first."
        return 1
    fi
    
    if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" | head -1 > /dev/null; then
        print_error "No active gcloud authentication found. Run: gcloud auth login"
        return 1
    fi
    
    print_success "gcloud is available and authenticated"
    return 0
}

# Function to check project configuration
check_project() {
    print_status "Checking project configuration..."
    
    current_project=$(gcloud config get-value project 2>/dev/null)
    if [[ "$current_project" != "$PROJECT_ID" ]]; then
        print_warning "Current project ($current_project) differs from expected ($PROJECT_ID)"
        gcloud config set project "$PROJECT_ID"
    fi
    
    print_success "Project set to: $PROJECT_ID"
}

# Function to check Redis instance
check_redis() {
    print_status "Checking Redis instance..."
    
    if gcloud redis instances describe launch-nukes-redis --region="$REGION" &> /dev/null; then
        redis_state=$(gcloud redis instances describe launch-nukes-redis --region="$REGION" --format="value(state)")
        redis_host=$(gcloud redis instances describe launch-nukes-redis --region="$REGION" --format="value(host)")
        
        if [[ "$redis_state" == "READY" ]]; then
            print_success "Redis instance is ready at $redis_host"
        else
            print_warning "Redis instance state: $redis_state"
        fi
    else
        print_error "Redis instance not found"
        return 1
    fi
}

# Function to check GPU quota
check_gpu_quota() {
    print_status "Checking GPU quota..."
    
    # Check if we have GPU quota in the region
    gpu_quota=$(gcloud compute project-info describe --format="value(quotas[].limit)" --filter="quotas.metric:NVIDIA_L4_GPUS AND quotas.region:$REGION" 2>/dev/null || echo "0")
    
    if [[ "$gpu_quota" == "0" || -z "$gpu_quota" ]]; then
        print_warning "No NVIDIA L4 GPU quota found in $REGION. You may need to request quota increase."
        print_warning "Visit: https://console.cloud.google.com/iam-admin/quotas"
        return 1
    else
        print_success "GPU quota available: $gpu_quota NVIDIA L4 GPUs"
        return 0
    fi
}

# Function to check Ollama service
check_ollama_service() {
    print_status "Checking Ollama AI service..."
    
    if gcloud run services describe launch-nukes-ollama --region="$REGION" &> /dev/null; then
        ollama_url=$(gcloud run services describe launch-nukes-ollama --region="$REGION" --format="value(status.url)")
        print_success "Ollama service is deployed at: $ollama_url"
        
        # Test the Ollama API
        print_status "Testing Ollama API..."
        if curl -s -f "$ollama_url/api/tags" > /dev/null; then
            print_success "Ollama API is responding"
        else
            print_warning "Ollama API is not responding (may be starting up)"
        fi
        
        return 0
    else
        print_error "Ollama service not found"
        return 1
    fi
}
check_service() {
    print_status "Checking Cloud Run service..."
    
    if gcloud run services describe "$SERVICE_NAME" --region="$REGION" &> /dev/null; then
        service_url=$(gcloud run services describe "$SERVICE_NAME" --region="$REGION" --format="value(status.url)")
        print_success "Service is deployed at: $service_url"
        
        # Test the health endpoint
        print_status "Testing health endpoint..."
        if curl -s -f "$service_url/health" > /dev/null; then
            print_success "Health endpoint is responding"
        else
            print_warning "Health endpoint is not responding"
        fi
        
        return 0
    else
        print_error "Cloud Run service not found"
        return 1
    fi
}

# Function to check Cloud Run worker service
check_worker_service() {
    print_status "Checking Cloud Run worker service..."
    
    if gcloud run services describe "launch-the-nukes-worker" --region="$REGION" &> /dev/null; then
        worker_url=$(gcloud run services describe "launch-the-nukes-worker" --region="$REGION" --format="value(status.url)")
        print_success "Worker service is deployed at: $worker_url"
        
        # Test the worker health endpoint
        print_status "Testing worker health endpoint..."
        if curl -s -f "$worker_url/health" > /dev/null 2>&1; then
            print_success "Worker health endpoint is responding"
        elif curl -s -f "$worker_url/stats" > /dev/null 2>&1; then
            print_success "Worker stats endpoint is responding"
        else
            print_warning "Worker endpoints are not responding (may be starting up)"
        fi
        
        return 0
    else
        print_error "Cloud Run worker service not found"
        return 1
    fi
}

# Function to check container images
check_images() {
    print_status "Checking container images..."
    
    frontend_image="gcr.io/$PROJECT_ID/$SERVICE_NAME:latest"
    worker_image="gcr.io/$PROJECT_ID/$JOB_NAME:latest"
    
    if gcloud container images describe "$frontend_image" &> /dev/null; then
        print_success "Frontend image exists: $frontend_image"
    else
        print_error "Frontend image not found: $frontend_image"
    fi
    
    if gcloud container images describe "$worker_image" &> /dev/null; then
        print_success "Worker image exists: $worker_image"
    else
        print_error "Worker image not found: $worker_image"
    fi
}



# Function to show service logs
show_logs() {
    print_status "Recent service logs:"
    gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=$SERVICE_NAME" \
        --limit=10 \
        --format="table(timestamp,severity,textPayload)" \
        --sort-by="~timestamp" \
        2>/dev/null || print_warning "Could not retrieve logs"
}

# Function to display summary
show_summary() {
    print_status "Deployment Summary:"
    echo "===================="
    echo "Project: $PROJECT_ID"
    echo "Region: $REGION"
    echo "Service: $SERVICE_NAME"
    echo "Job: $JOB_NAME"
    echo ""
    
    if gcloud run services describe "$SERVICE_NAME" --region="$REGION" &> /dev/null; then
        service_url=$(gcloud run services describe "$SERVICE_NAME" --region="$REGION" --format="value(status.url)")
        echo "🌐 Frontend URL: $service_url"
    fi
    
    if gcloud redis instances describe launch-nukes-redis --region="$REGION" &> /dev/null; then
        redis_host=$(gcloud redis instances describe launch-nukes-redis --region="$REGION" --format="value(host)")
        echo "🔴 Redis Host: $redis_host"
    fi
    
    if gcloud run services describe launch-nukes-ollama --region="$REGION" &> /dev/null; then
        ollama_url=$(gcloud run services describe launch-nukes-ollama --region="$REGION" --format="value(status.url)")
        echo "🧠 Ollama AI: $ollama_url"
    fi
    
    if gcloud run services describe launch-the-nukes-worker --region="$REGION" &> /dev/null; then
        worker_url=$(gcloud run services describe launch-the-nukes-worker --region="$REGION" --format="value(status.url)")
        echo "⚙️ Worker Service: $worker_url"
    fi
    
    echo ""
    echo "Useful commands:"
    echo "  View logs: gcloud logging read \"resource.type=cloud_run_revision\" --limit=50"
    echo "  Check worker stats: curl \$WORKER_URL/stats"
    echo "  Update service: gcloud run services replace cloudrun-frontend.yaml --region=$REGION"
    echo "  Update worker: gcloud run services replace cloudrun-worker.yaml --region=$REGION"
}

# Main function
main() {
    echo "🔍 Launch the Nukes - Deployment Verification"
    echo "============================================="
    
    check_gcloud || exit 1
    check_project
    
    print_status "Running deployment checks..."
    
    # Run all checks
    local all_passed=true
    
    check_gpu_quota || print_warning "GPU quota check failed (not critical)"
    check_redis || all_passed=false
    check_images || all_passed=false
    check_service || all_passed=false
    check_ollama_service || all_passed=false
    check_worker_service || all_passed=false
    
    # Optional: test worker service
    if [[ "${1:-}" == "--test-worker" ]]; then
        print_status "Testing worker service..."
        if gcloud run services describe launch-the-nukes-worker --region="$REGION" &> /dev/null; then
            worker_url=$(gcloud run services describe launch-the-nukes-worker --region="$REGION" --format="value(status.url)")
            if curl -s "$worker_url/stats" > /dev/null 2>&1; then
                print_success "Worker service test passed"
            else
                print_warning "Worker service test failed"
            fi
        fi
    fi
    
    # Show logs if requested
    if [[ "${1:-}" == "--logs" ]]; then
        show_logs
    fi
    
    echo ""
    show_summary
    
    if $all_passed; then
        print_success "✅ All checks passed! Deployment appears to be working correctly."
        exit 0
    else
        print_error "❌ Some checks failed. Please review the output above."
        exit 1
    fi
}

# Help function
show_help() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  --test-worker Test worker service connectivity"
    echo "  --logs        Show recent service logs"
    echo "  --help        Show this help message"
    echo ""
    echo "Environment variables:"
    echo "  GOOGLE_CLOUD_PROJECT    GCP project ID (default: launch-the-nukes)"
    echo "  REGION                  GCP region (default: us-central1)"
}

# Parse command line arguments
case "${1:-}" in
    "--help")
        show_help
        exit 0
        ;;
    *)
        main "$@"
        ;;
esac
