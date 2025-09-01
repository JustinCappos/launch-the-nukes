#!/bin/bash

# Script to set up GCP service account for GitHub Actions CI/CD
# Run this script with: chmod +x setup-github-actions.sh && ./setup-github-actions.sh

set -e

PROJECT_ID="launch-the-nukes"
SERVICE_ACCOUNT_NAME="github-actions"
SERVICE_ACCOUNT_EMAIL="${SERVICE_ACCOUNT_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
KEY_FILE="github-actions-key.json"

echo "Setting up GitHub Actions service account for project: ${PROJECT_ID}"

# Check if gcloud is installed and authenticated
if ! command -v gcloud &> /dev/null; then
    echo "ERROR: gcloud CLI is not installed. Please install it first."
    echo "Visit: https://cloud.google.com/sdk/docs/install"
    exit 1
fi

# Check if user is authenticated
if ! gcloud auth list --filter="status:ACTIVE" --format="value(account)" | grep -q "@"; then
    echo "ERROR: You are not authenticated with gcloud. Please run 'gcloud auth login' first."
    exit 1
fi

# Set the project
echo "Setting project to ${PROJECT_ID}..."
gcloud config set project ${PROJECT_ID}

# Create service account
echo "Creating service account: ${SERVICE_ACCOUNT_NAME}..."
if gcloud iam service-accounts describe ${SERVICE_ACCOUNT_EMAIL} &>/dev/null; then
    echo "Service account already exists. Skipping creation."
else
    gcloud iam service-accounts create ${SERVICE_ACCOUNT_NAME} \
        --description="Service account for GitHub Actions CI/CD" \
        --display-name="GitHub Actions"
fi

# Grant necessary permissions
echo "Granting permissions to service account..."

# Cloud Run Admin (to deploy and manage services)
gcloud projects add-iam-policy-binding ${PROJECT_ID} \
    --member="serviceAccount:${SERVICE_ACCOUNT_EMAIL}" \
    --role="roles/run.admin"

# Storage Admin (for Container Registry)
gcloud projects add-iam-policy-binding ${PROJECT_ID} \
    --member="serviceAccount:${SERVICE_ACCOUNT_EMAIL}" \
    --role="roles/storage.admin"

# Service Account User (to act as service accounts)
gcloud projects add-iam-policy-binding ${PROJECT_ID} \
    --member="serviceAccount:${SERVICE_ACCOUNT_EMAIL}" \
    --role="roles/iam.serviceAccountUser"

# Cloud Build Editor (for building containers)
gcloud projects add-iam-policy-binding ${PROJECT_ID} \
    --member="serviceAccount:${SERVICE_ACCOUNT_EMAIL}" \
    --role="roles/cloudbuild.builds.editor"

# Cloud Build Viewer (for viewing build logs in CI)
gcloud projects add-iam-policy-binding ${PROJECT_ID} \
    --member="serviceAccount:${SERVICE_ACCOUNT_EMAIL}" \
    --role="roles/cloudbuild.builds.viewer"

# Redis Admin (for managing Redis instances)
gcloud projects add-iam-policy-binding ${PROJECT_ID} \
    --member="serviceAccount:${SERVICE_ACCOUNT_EMAIL}" \
    --role="roles/redis.admin"

# VPC Access Admin (for managing VPC connectors)
gcloud projects add-iam-policy-binding ${PROJECT_ID} \
    --member="serviceAccount:${SERVICE_ACCOUNT_EMAIL}" \
    --role="roles/vpcaccess.admin"

# Compute Network Admin (for VPC connector creation)
gcloud projects add-iam-policy-binding ${PROJECT_ID} \
    --member="serviceAccount:${SERVICE_ACCOUNT_EMAIL}" \
    --role="roles/compute.networkAdmin"

# Service Usage Admin (to enable APIs)
gcloud projects add-iam-policy-binding ${PROJECT_ID} \
    --member="serviceAccount:${SERVICE_ACCOUNT_EMAIL}" \
    --role="roles/serviceusage.serviceUsageAdmin"

# Project Viewer (to stream build logs)
gcloud projects add-iam-policy-binding ${PROJECT_ID} \
    --member="serviceAccount:${SERVICE_ACCOUNT_EMAIL}" \
    --role="roles/viewer"

# Create and download service account key
echo "Creating service account key..."
if [ -f "${KEY_FILE}" ]; then
    echo "Key file already exists. Creating backup..."
    mv "${KEY_FILE}" "${KEY_FILE}.backup.$(date +%s)"
fi

gcloud iam service-accounts keys create ${KEY_FILE} \
    --iam-account=${SERVICE_ACCOUNT_EMAIL}

echo ""
echo "✅ Service account setup complete!"
echo ""
echo "📋 Next steps:"
echo "1. Go to your GitHub repository: https://github.com/JustinCappos/launch-the-nukes"
echo "2. Navigate to: Settings → Secrets and Variables → Actions"
echo "3. Click 'New repository secret'"
echo "4. Add secret with name: GCP_SERVICE_ACCOUNT_KEY"
echo "5. Copy and paste the entire content of ${KEY_FILE} as the value"
echo ""
echo "📄 The service account key has been saved to: ${KEY_FILE}"
echo "⚠️  Keep this key secure and do not commit it to version control!"
echo ""
echo "🚀 After adding the secret to GitHub, your CI/CD pipeline will be ready!"
echo "   Push to main/master branch to trigger automatic deployment."

# Display the key content for easy copying
echo ""
echo "📋 Service account key content (copy this to GitHub secret):"
echo "=================================================="
cat ${KEY_FILE}
echo "=================================================="
