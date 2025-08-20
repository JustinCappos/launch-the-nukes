#!/bin/bash
# GCP deployment script for Launch the Nukes

set -e

# Configuration
PROJECT_ID="${GOOGLE_CLOUD_PROJECT:-launch-the-nukes}"
REGION="${REGION:-us-central1}"
REDIS_INSTANCE_NAME="launch-nukes-redis"
SERVICE_NAME="launch-the-nukes-frontend"
JOB_NAME="launch-the-nukes-worker"
CI_MODE="${CI:-false}"  # Set to true in CI environments

echo "🚀 Deploying Launch the Nukes to GCP..."
echo "Project: $PROJECT_ID"
echo "Region: $REGION"

# Check if gcloud is installed and authenticated
if ! command -v gcloud &> /dev/null; then
    echo "❌ gcloud CLI not found. Please install it first."
    exit 1
fi

# Set project
gcloud config set project $PROJECT_ID

# Enable required APIs
echo "� Enabling required APIs..."
echo "Project: $PROJECT_ID"
echo "Region: $REGION"

# Check if gcloud is installed and authenticated
if ! command -v gcloud &> /dev/null; then
    echo "❌ gcloud CLI not found. Please install it first."
    exit 1
fi

# Set project
gcloud config set project $PROJECT_ID

# Enable required APIs
echo "📡 Enabling required APIs..."
gcloud services enable \
    cloudbuild.googleapis.com \
    run.googleapis.com \
    redis.googleapis.com \
    compute.googleapis.com \
    container.googleapis.com \
    aiplatform.googleapis.com \
    vpcaccess.googleapis.com \
    iam.googleapis.com

# Create service accounts for secure service-to-service communication
echo "🔐 Creating service accounts..."
FRONTEND_SA="launch-nukes-frontend"
WORKER_SA="launch-nukes-worker"
OLLAMA_SA="launch-nukes-ollama"

# Create service accounts if they don't exist
for SA in $FRONTEND_SA $WORKER_SA $OLLAMA_SA; do
    if ! gcloud iam service-accounts describe "$SA@$PROJECT_ID.iam.gserviceaccount.com" &> /dev/null; then
        gcloud iam service-accounts create $SA \
            --display-name="$SA service account"
        echo "✅ Created service account: $SA"
    else
        echo "✅ Service account already exists: $SA"
    fi
done

# Grant permissions for frontend to call internal services
echo "🔗 Setting up service-to-service permissions..."
gcloud run services add-iam-policy-binding launch-nukes-ollama \
    --member="serviceAccount:$FRONTEND_SA@$PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/run.invoker" \
    --region=$REGION || echo "Will set after Ollama deployment"

gcloud run services add-iam-policy-binding launch-the-nukes-worker \
    --member="serviceAccount:$FRONTEND_SA@$PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/run.invoker" \
    --region=$REGION || echo "Will set after worker deployment"

# Create Redis instance (Cloud Memorystore)
echo "🔴 Creating Redis instance..."
if ! gcloud redis instances describe $REDIS_INSTANCE_NAME --region=$REGION &> /dev/null; then
    gcloud redis instances create $REDIS_INSTANCE_NAME \
        --size=1 \
        --region=$REGION \
        --redis-version=redis_6_x \
        --tier=basic
    
    echo "⏳ Waiting for Redis instance to be ready..."
    gcloud redis instances describe $REDIS_INSTANCE_NAME --region=$REGION --format="value(state)" | grep -q "READY"
else
    echo "✅ Redis instance already exists"
fi

# Get Redis host IP
REDIS_HOST=$(gcloud redis instances describe $REDIS_INSTANCE_NAME --region=$REGION --format="value(host)")
echo "📍 Redis host: $REDIS_HOST"

# Get Redis network details for debugging
REDIS_NETWORK=$(gcloud redis instances describe $REDIS_INSTANCE_NAME --region=$REGION --format="value(authorizedNetwork)" 2>/dev/null || echo "default")
echo "🔗 Redis network: $REDIS_NETWORK"

# Create VPC Access Connector for Cloud Run to access Redis
CONNECTOR_NAME="launch-nukes-connector"
echo "🔗 Creating VPC Access Connector..."
if ! gcloud compute networks vpc-access connectors describe $CONNECTOR_NAME --region=$REGION &> /dev/null; then
    gcloud compute networks vpc-access connectors create $CONNECTOR_NAME \
        --region=$REGION \
        --network=default \
        --range=10.8.0.0/28 \
        --min-instances=2 \
        --max-instances=3
    
    echo "⏳ Waiting for VPC connector to be ready..."
    sleep 30
else
    echo "✅ VPC connector already exists"
fi

# Build and push frontend image
echo "🏗️  Building frontend image..."
gcloud builds submit --tag gcr.io/$PROJECT_ID/$SERVICE_NAME:latest .

# Build and push Ollama image
echo "🧠 Building Ollama AI service image..."
cat > ollama-build.yaml <<EOF
steps:
- name: 'gcr.io/cloud-builders/docker'
  args: ['build', '-f', 'Dockerfile.ollama', '-t', 'gcr.io/$PROJECT_ID/launch-nukes-ollama:latest', '.']
images: ['gcr.io/$PROJECT_ID/launch-nukes-ollama:latest']
EOF
gcloud builds submit --config=ollama-build.yaml .

# Build and push worker image
echo "🏗️  Building worker image..."
cat > worker-build.yaml <<EOF
steps:
- name: 'gcr.io/cloud-builders/docker'
  args: ['build', '-f', 'Dockerfile.worker', '-t', 'gcr.io/$PROJECT_ID/$JOB_NAME:latest', '.']
images: ['gcr.io/$PROJECT_ID/$JOB_NAME:latest']
EOF
gcloud builds submit --config=worker-build.yaml .

# Generate deployment nonce to force new revisions
DEPLOY_NONCE=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
echo "🕐 Deploy nonce: $DEPLOY_NONCE"

# Update Cloud Run service configuration with actual values
echo "📝 Updating service configuration..."
sed -e "s/PROJECT_ID/$PROJECT_ID/g" \
    -e "s/REDIS_HOST_IP/$REDIS_HOST/g" \
    -e "s/DEPLOY_NONCE/$DEPLOY_NONCE/g" \
    cloudrun-frontend.yaml > cloudrun-frontend-configured.yaml

# Deploy Cloud Run service with service account
echo "🚀 Deploying Cloud Run frontend service..."
gcloud run services replace cloudrun-frontend-configured.yaml --region=$REGION

# Allow unauthenticated access to frontend service ONLY
echo "🔓 Setting up public access for frontend service only..."
gcloud run services add-iam-policy-binding $SERVICE_NAME \
    --member="allUsers" \
    --role="roles/run.invoker" \
    --region=$REGION

# Deploy Ollama AI service with internal-only access
echo "🧠 Deploying Ollama AI service (internal access only)..."
sed -e "s/PROJECT_ID/$PROJECT_ID/g" \
    -e "s/DEPLOY_NONCE/$DEPLOY_NONCE/g" \
    cloudrun-ollama.yaml > cloudrun-ollama-configured.yaml

gcloud run services replace cloudrun-ollama-configured.yaml --region=$REGION

# Set service account for Ollama service
gcloud run services update launch-nukes-ollama \
    --service-account="$OLLAMA_SA@$PROJECT_ID.iam.gserviceaccount.com" \
    --region=$REGION

# DO NOT allow public access to Ollama - it's internal only
echo "� Ollama AI service configured for internal access only"

# Get Ollama service URL
OLLAMA_CLOUD_URL=$(gcloud run services describe launch-nukes-ollama --region=$REGION --format="value(status.url)")
echo "🧠 Ollama AI service URL: $OLLAMA_CLOUD_URL"

# Test Ollama service connectivity
echo "🔍 Testing Ollama service connectivity..."
if [ "$CI_MODE" = "true" ]; then
    echo "⏳ CI Mode: Quick connectivity test (max 3 attempts)..."
    MAX_ATTEMPTS=3
else
    echo "⏳ Waiting for Ollama to download model (this may take 5-10 minutes on first deployment)..."
    MAX_ATTEMPTS=60
fi

OLLAMA_READY=false
for i in $(seq 1 $MAX_ATTEMPTS); do
    if curl -s --max-time 10 "$OLLAMA_CLOUD_URL/api/tags" > /dev/null 2>&1; then
        echo "✅ Ollama service is responding"
        OLLAMA_READY=true
        break
    else
        echo "⏳ Attempt $i/$MAX_ATTEMPTS: Ollama still starting up..."
        sleep 10
    fi
done

if [ "$OLLAMA_READY" = false ]; then
    if [ "$CI_MODE" = "true" ]; then
        echo "⚠️ Ollama service not yet responding in CI mode. This is normal - the model download continues in background."
    else
        echo "⚠️ Ollama service may still be downloading the model. This can take up to 10 minutes."
        echo "   Check the logs: gcloud logging read \"resource.type=cloud_run_revision AND resource.labels.service_name=launch-nukes-ollama\" --limit=10"
    fi
fi

echo "✅ Services are now publicly accessible"

# Update Cloud Run job configuration with actual values
echo "📝 Updating worker service configuration..."
sed -e "s/PROJECT_ID/$PROJECT_ID/g" \
    -e "s/REDIS_HOST_IP/$REDIS_HOST/g" \
    -e "s|OLLAMA_URL_PLACEHOLDER|$OLLAMA_CLOUD_URL|g" \
    -e "s/DEPLOY_NONCE/$DEPLOY_NONCE/g" \
    cloudrun-worker.yaml > cloudrun-worker-configured.yaml

# Deploy Cloud Run worker service with internal-only access
echo "🔧 Deploying Cloud Run worker service (internal access only)..."
gcloud run services replace cloudrun-worker-configured.yaml --region=$REGION

# DO NOT allow public access to worker service - it's internal only
echo "🔒 Worker service configured for internal access only"

# Set up service-to-service permissions now that services exist
echo "� Finalizing service-to-service permissions..."
gcloud run services add-iam-policy-binding launch-nukes-ollama \
    --member="serviceAccount:$FRONTEND_SA@$PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/run.invoker" \
    --region=$REGION

gcloud run services add-iam-policy-binding launch-the-nukes-worker \
    --member="serviceAccount:$FRONTEND_SA@$PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/run.invoker" \
    --region=$REGION

# Allow worker to call Ollama
gcloud run services add-iam-policy-binding launch-nukes-ollama \
    --member="serviceAccount:$WORKER_SA@$PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/run.invoker" \
    --region=$REGION

# Get service URLs
SERVICE_URL=$(gcloud run services describe $SERVICE_NAME --region=$REGION --format="value(status.url)")
WORKER_URL=$(gcloud run services describe launch-the-nukes-worker --region=$REGION --format="value(status.url)")

echo ""
echo "✅ Deployment complete!"
echo "🕐 Deploy nonce: $DEPLOY_NONCE"
echo "🌐 Frontend URL (PUBLIC): $SERVICE_URL"
echo "🔴 Redis host (PRIVATE): $REDIS_HOST"
echo "🧠 Ollama AI service (INTERNAL ONLY): $OLLAMA_CLOUD_URL"
echo "⚙️ Worker service (INTERNAL ONLY): $WORKER_URL"
echo ""
echo "🔒 Security Configuration:"
echo "  ✅ Frontend: Public access (internet-facing)"
echo "  🔒 Ollama: Internal access only (VPC + service account auth)"
echo "  🔒 Worker: Internal access only (VPC + service account auth)"
echo "  🔒 Redis: Private VPC only"
echo ""
echo "To check worker status (internal):"
echo "gcloud run services proxy launch-the-nukes-worker --port=8080 &"
echo "curl http://localhost:8080/stats"
echo ""
echo "To view logs:"
echo "gcloud logging read \"resource.type=cloud_run_revision AND resource.labels.service_name=$SERVICE_NAME\" --limit=50 --format=\"table(timestamp,textPayload)\""

# Clean up temporary files
rm -f cloudrun-frontend-configured.yaml cloudrun-worker-configured.yaml cloudrun-ollama-configured.yaml
rm -f ollama-build.yaml worker-build.yaml
