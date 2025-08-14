#!/bin/bash

# MCP Server Deployment Script for Google Cloud
# This script builds and deploys the MCP server to Google Cloud Run

set -e

# Configuration
PROJECT_ID=${PROJECT_ID:-$(gcloud config get-value project)}
REGION=${REGION:-"australia-southeast1"}
SERVICE_NAME=${SERVICE_NAME:-"crm-server"}
IMAGE_NAME="gcr.io/$PROJECT_ID/$SERVICE_NAME"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}🚀 Starting MCP Server deployment to Google Cloud...${NC}"
echo -e "${YELLOW}Project ID: $PROJECT_ID${NC}"
echo -e "${YELLOW}Region: $REGION${NC}"
echo -e "${YELLOW}Service Name: $SERVICE_NAME${NC}"

# Check if gcloud is installed and authenticated
if ! command -v gcloud &> /dev/null; then
    echo -e "${RED}❌ gcloud CLI is not installed. Please install it first.${NC}"
    exit 1
fi

# Check if user is authenticated
if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" | grep -q .; then
    echo -e "${YELLOW}⚠️  Not authenticated with gcloud. Please run 'gcloud auth login' first.${NC}"
    exit 1
fi

# Set the project
echo -e "${YELLOW}📋 Setting project to $PROJECT_ID...${NC}"
gcloud config set project $PROJECT_ID

# Enable required APIs
echo -e "${YELLOW}🔧 Enabling required APIs...${NC}"
gcloud services enable cloudbuild.googleapis.com
gcloud services enable run.googleapis.com
gcloud services enable containerregistry.googleapis.com
gcloud services enable aiplatform.googleapis.com

# Use existing service account from vertex-credentials.json
echo -e "${YELLOW}🔐 Using existing service account...${NC}"
EXISTING_SA="vertex-chat-user@$PROJECT_ID.iam.gserviceaccount.com"

if gcloud iam service-accounts describe "$EXISTING_SA" &>/dev/null; then
    echo -e "${GREEN}✅ Using existing service account: $EXISTING_SA${NC}"
    
    # Ensure user has permission to act as the service account
    echo -e "${YELLOW}Verifying user permissions...${NC}"
    gcloud iam service-accounts add-iam-policy-binding "$EXISTING_SA" \
        --member="user:$(gcloud config get-value account)" \
        --role="roles/iam.serviceAccountUser" 2>/dev/null || echo -e "${GREEN}User permissions already set${NC}"
else
    echo -e "${RED}❌ Service account $EXISTING_SA does not exist.${NC}"
    echo -e "${YELLOW}💡 Please check your vertex-credentials.json file.${NC}"
    exit 1
fi

# Build and push the Docker image
echo -e "${YELLOW}🐳 Building Docker image...${NC}"
gcloud builds submit --tag $IMAGE_NAME .

# Deploy to Cloud Run
echo -e "${YELLOW}🚀 Deploying to Cloud Run...${NC}"
gcloud run deploy $SERVICE_NAME \
    --image $IMAGE_NAME \
    --platform managed \
    --region $REGION \
    --allow-unauthenticated \
    --port 8080 \
    --memory 2Gi \
    --cpu 2 \
    --max-instances 10 \
    --service-account="$EXISTING_SA" \
    --set-env-vars "GCP_PROJECT_ID=$PROJECT_ID,GCP_REGION=$REGION,GEMINI_MODEL_NAME=gemini-1.5-pro,GOOGLE_APPLICATION_CREDENTIALS=/app/vertex-credentials.json"

# Get the service URL
SERVICE_URL=$(gcloud run services describe $SERVICE_NAME --region=$REGION --format="value(status.url)")

echo -e "${GREEN}✅ Deployment completed successfully!${NC}"
echo -e "${GREEN}🌐 Service URL: $SERVICE_URL${NC}"
echo -e "${YELLOW}📝 Note: The service is now using the default service account for authentication.${NC}"
echo -e "${YELLOW}📝 Make sure the service account has the necessary Vertex AI permissions.${NC}"
