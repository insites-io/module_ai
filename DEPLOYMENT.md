# Deployment Guide - MCP CRM Server

This guide provides step-by-step instructions for deploying the MCP CRM Server to various platforms.

## Prerequisites

- Google Cloud Platform account with billing enabled
- Google Cloud CLI (`gcloud`) installed and authenticated
- Python 3.11+ (for local development)
- Docker (for containerized deployment)

## Quick Deployment to Google Cloud Run

### 1. Install and Setup Google Cloud CLI

```bash
# Install gcloud CLI (macOS)
curl https://sdk.cloud.google.com | bash
exec -l $SHELL

# Or install via Homebrew
brew install google-cloud-sdk

# Authenticate
gcloud auth login
gcloud auth application-default login
```

### 2. Set Project and Enable APIs

```bash
# Set your project ID
gcloud config set project YOUR_PROJECT_ID

# Enable required APIs
gcloud services enable cloudbuild.googleapis.com
gcloud services enable run.googleapis.com
gcloud services enable containerregistry.googleapis.com
gcloud services enable aiplatform.googleapis.com
```

### 3. Prepare Service Account

```bash
# Create service account for the MCP Server
gcloud iam service-accounts create mcp-server-sa \
    --display-name="MCP Server Service Account"

# Grant necessary roles
gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
    --member="serviceAccount:mcp-server-sa@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/aiplatform.user"

gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
    --member="serviceAccount:mcp-server-sa@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/storage.objectViewer"

# Note: We no longer need to download credentials file for Cloud Run
# The service will use the default service account authentication
```

### 4. Deploy Using Script

```bash
# Make script executable
chmod +x deploy.sh

# Set environment variables
export PROJECT_ID="YOUR_PROJECT_ID"
export REGION="us-central1"  # or your preferred region
export SERVICE_NAME="crm-server"

# Run deployment
./deploy.sh
```

### 5. Verify Deployment

```bash
# Get service URL
gcloud run services describe crm-server --region=YOUR_REGION --format="value(status.url)"

# Test health check
curl https://YOUR_SERVICE_URL/

# View logs
gcloud logs read --service=crm-server --limit=20
```

## Manual Deployment

If you prefer to deploy manually:

```bash
# Build and push Docker image
gcloud builds submit --tag gcr.io/YOUR_PROJECT_ID/crm-server .

# Deploy to Cloud Run
gcloud run deploy crm-server \
    --image gcr.io/YOUR_PROJECT_ID/crm-server \
    --platform managed \
    --region YOUR_REGION \
    --allow-unauthenticated \
    --port 8080 \
    --memory 2Gi \
    --cpu 2 \
    --max-instances 10 \
    --set-env-vars "GCP_PROJECT_ID=YOUR_PROJECT_ID,GCP_REGION=YOUR_REGION,GEMINI_MODEL_NAME=gemini-1.5-pro"
```

## Local Development

### 1. Setup Virtual Environment

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Environment Variables

Create `.env` file:

```bash
GCP_PROJECT_ID=your-project-id
GCP_REGION=your-region
GEMINI_MODEL_NAME=gemini-1.5-pro
```

### 3. Run Locally

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8080
```

## Docker Deployment

### Build and Run Locally

```bash
# Build image
docker build -t mcp-crm-server .

# Run container
docker run -p 8080:8080 \
    -e GCP_PROJECT_ID=your-project-id \
    -e GCP_REGION=your-region \
    -v $(pwd)/vertex-credentials.json:/app/vertex-credentials.json \
    mcp-crm-server
```

### Push to Container Registry

```bash
# Tag for your registry
docker tag mcp-crm-server gcr.io/YOUR_PROJECT_ID/crm-server

# Push to Google Container Registry
docker push gcr.io/YOUR_PROJECT_ID/crm-server
```

## Environment Variables Reference

| Variable | Required | Description | Example |
|----------|----------|-------------|---------|
| `GCP_PROJECT_ID` | ✅ | Google Cloud Project ID | `my-project-123` |
| `GCP_REGION` | ✅ | Google Cloud Region | `us-central1` |
| `GEMINI_MODEL_NAME` | ❌ | Vertex AI model name | `gemini-1.5-pro` |

## Troubleshooting

### Container Startup Issues

If you encounter "container failed to start" errors:

1. **Check the Dockerfile fixes:**
   - Ensure `curl` is installed for health checks
   - Verify the CMD uses `${PORT:-8080}` for Cloud Run compatibility
   - Remove hardcoded credentials file dependencies

2. **Verify service account permissions:**
   ```bash
   # Check if service account exists
   gcloud iam service-accounts list --filter="displayName:MCP Server"
   
   # Verify roles are assigned
   gcloud projects get-iam-policy YOUR_PROJECT_ID \
       --flatten="bindings[].members" \
       --filter="bindings.members:serviceAccount:mcp-server-sa@YOUR_PROJECT_ID.iam.gserviceaccount.com"
   ```

3. **Check build logs:**
   ```bash
   # View recent builds
   gcloud builds list --limit=5
   
   # Check specific build logs
   gcloud builds log BUILD_ID
   ```

### Common Deployment Issues

1. **Build Failures**
   ```bash
   # Check build logs
   gcloud builds log BUILD_ID
   
   # Verify Dockerfile syntax
   docker build --no-cache .
   ```

2. **Runtime Errors**
   ```bash
   # Check service logs
   gcloud logs read --service=crm-server --limit=50
   
   # Test locally first
   docker run --rm -it mcp-crm-server
   ```

3. **Authentication Issues**
   ```bash
   # Verify credentials
   gcloud auth list
   gcloud config list
   
   # Re-authenticate if needed
   gcloud auth application-default login
   ```

### Performance Tuning

```bash
# Scale up resources
gcloud run services update crm-server \
    --region=YOUR_REGION \
    --memory=4Gi \
    --cpu=4 \
    --max-instances=20

# Enable concurrency
gcloud run services update crm-server \
    --region=YOUR_REGION \
    --concurrency=80
```

## Monitoring and Logging

### Enable Cloud Monitoring

```bash
# Enable monitoring APIs
gcloud services enable monitoring.googleapis.com
gcloud services enable cloudtrace.googleapis.com

# View metrics in Cloud Console
# Go to: https://console.cloud.google.com/run
```

### Log Analysis

```bash
# Real-time logs
gcloud logs tail --service=crm-server

# Filter logs by severity
gcloud logs read --service=crm-server --filter="severity>=ERROR"

# Export logs
gcloud logging read --project=YOUR_PROJECT_ID --format="table(timestamp,severity,textPayload)" > logs.txt
```

## Security Best Practices

1. **Use Secrets Manager for sensitive data**
   ```bash
   # Create secret
   echo -n "your-api-key" | gcloud secrets create crm-api-key --data-file=-
   
   # Update service to use secret
   gcloud run services update crm-server \
       --region=YOUR_REGION \
       --set-secrets=CRM_API_KEY=crm-api-key:latest
   ```

2. **Enable VPC Connector for private networking**
3. **Implement proper IAM roles and permissions**
4. **Use HTTPS and secure headers**
5. **Regular security updates and patches**

## Cost Optimization

- Use appropriate instance sizes
- Set reasonable max-instances limits
- Monitor usage with Cloud Billing
- Consider using Cloud Run's scale-to-zero feature
- Use spot instances for non-critical workloads

## Next Steps

After successful deployment:

1. Test all API endpoints
2. Set up monitoring and alerting
3. Configure CI/CD pipeline
4. Implement backup and disaster recovery
5. Set up performance testing
6. Document operational procedures
