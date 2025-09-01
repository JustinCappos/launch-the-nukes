#!/bin/bash
# Environment configuration script for Launch the Nukes

set -e

# Function to print colored output
print_info() {
    echo -e "\033[1;34m[INFO]\033[0m $1"
}

print_success() {
    echo -e "\033[1;32m[SUCCESS]\033[0m $1"
}

print_warning() {
    echo -e "\033[1;33m[WARNING]\033[0m $1"
}

print_error() {
    echo -e "\033[1;31m[ERROR]\033[0m $1"
}

# Function to check if running in Cloud Run
is_cloud_run() {
    [[ -n "${GOOGLE_CLOUD_PROJECT}" && -n "${K_SERVICE}" ]]
}

# Function to check if running locally
is_local() {
    [[ -z "${GOOGLE_CLOUD_PROJECT}" ]]
}

# Function to setup local environment
setup_local() {
    print_info "Setting up local development environment..."
    
    # Load .env file if it exists
    if [[ -f ".env" ]]; then
        print_info "Loading .env file..."
        export $(grep -v '^#' .env | xargs)
    fi
    
    # Set default values for local development
    export DEBUG=${DEBUG:-true}
    export SECRET_KEY=${SECRET_KEY:-launch-the-nukes-secret-key-2025-dev}
    export REDIS_URL=${REDIS_URL:-redis://localhost:6379/0}
    export NUM_WORKERS=${NUM_WORKERS:-2}
    export HOST=${HOST:-127.0.0.1}
    export PORT=${PORT:-8080}
    export OLLAMA_URL=${OLLAMA_URL:-http://localhost:11434}
    export MCP_CACHE_DURATION=${MCP_CACHE_DURATION:-300}
    export JOB_TIMEOUT=${JOB_TIMEOUT:-300}
    
    print_success "Local environment configured"
}

# Function to setup production environment
setup_production() {
    print_info "Setting up production environment..."
    
    # Validate required environment variables
    if [[ -z "${GOOGLE_CLOUD_PROJECT}" ]]; then
        print_error "GOOGLE_CLOUD_PROJECT must be set in production"
        exit 1
    fi
    
    if [[ -z "${REDIS_HOST}" ]]; then
        print_error "REDIS_HOST must be set in production"
        exit 1
    fi
    
    # Set production defaults
    export DEBUG=${DEBUG:-false}
    export NUM_WORKERS=${NUM_WORKERS:-0}  # Workers run separately
    export HOST=${HOST:-0.0.0.0}
    export PORT=${PORT:-8080}
    export REDIS_PORT=${REDIS_PORT:-6379}
    export REDIS_URL=${REDIS_URL:-redis://${REDIS_HOST}:${REDIS_PORT}/0}
    export MCP_CACHE_DURATION=${MCP_CACHE_DURATION:-300}
    export JOB_TIMEOUT=${JOB_TIMEOUT:-300}
    
    # Setup Cloud Logging if available
    if command -v gcloud &> /dev/null; then
        export GOOGLE_APPLICATION_CREDENTIALS="/tmp/gcp-key.json"
    fi
    
    print_success "Production environment configured"
}

# Function to validate environment
validate_environment() {
    print_info "Validating environment..."
    
    # Check Redis connectivity
    if command -v redis-cli &> /dev/null; then
        if redis-cli -u "${REDIS_URL}" ping > /dev/null 2>&1; then
            print_success "Redis connection successful"
        else
            print_warning "Redis connection failed - this may cause issues"
        fi
    fi
    
    # Check Python dependencies
    if python -c "import flask, redis, yaml" 2>/dev/null; then
        print_success "Required Python packages available"
    else
        print_error "Missing required Python packages. Run: pip install -r requirements.txt"
        exit 1
    fi
    
    print_success "Environment validation complete"
}

# Function to display environment info
show_environment() {
    print_info "Current environment configuration:"
    echo "  DEBUG: ${DEBUG:-not set}"
    echo "  REDIS_URL: ${REDIS_URL:-not set}"
    echo "  NUM_WORKERS: ${NUM_WORKERS:-not set}"
    echo "  HOST: ${HOST:-not set}"
    echo "  PORT: ${PORT:-not set}"
    echo "  GOOGLE_CLOUD_PROJECT: ${GOOGLE_CLOUD_PROJECT:-not set}"
    
    if is_cloud_run; then
        echo "  Environment: Cloud Run (Production)"
    elif is_local; then
        echo "  Environment: Local Development"
    else
        echo "  Environment: Unknown"
    fi
}

# Main function
main() {
    case "${1:-setup}" in
        "setup")
            if is_cloud_run; then
                setup_production
            else
                setup_local
            fi
            validate_environment
            ;;
        "validate")
            validate_environment
            ;;
        "show")
            show_environment
            ;;
        "help")
            echo "Usage: $0 [setup|validate|show|help]"
            echo ""
            echo "Commands:"
            echo "  setup    - Setup environment (default)"
            echo "  validate - Validate current environment"
            echo "  show     - Show current environment configuration"
            echo "  help     - Show this help message"
            ;;
        *)
            print_error "Unknown command: $1"
            $0 help
            exit 1
            ;;
    esac
}

# Run main function
main "$@"
