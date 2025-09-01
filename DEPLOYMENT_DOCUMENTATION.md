# MCP Server Deployment Documentation

## Overview

This documentation covers the deployment of the MCP CRM Server to Google Cloud Run. The project includes two deployment scripts:

- **`deploy.sh`** - Deploys the core MCP server
- **`deploy_ui.sh`** - Deploys the MCP server with web UI interface

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Architecture Overview](#architecture-overview)
3. [Deployment Scripts](#deployment-scripts)
4. [Configuration Options](#configuration-options)
5. [Deployment Process](#deployment-process)
6. [Post-Deployment](#post-deployment)
7. [Troubleshooting](#troubleshooting)
8. [Cost Optimization](#cost-optimization)
9. [Security Considerations](#security-considerations)

## Prerequisites

### Required Tools
- **Google Cloud CLI (gcloud)** - [Installation Guide](https://cloud.google.com/sdk/docs/install)
- **Docker** - [Installation Guide](https://docs.docker.com/get-docker/)
- **Bash shell** (Linux/macOS/WSL)

### Google Cloud Setup
1. **Create a Google Cloud Project**
   ```bash
   gcloud projects create YOUR_PROJECT_ID
   gcloud config set project YOUR_PROJECT_ID
   ```

2. **Enable Billing**
   - Link a billing account to your project in the Google Cloud Console

3. **Create Service Account**
   ```bash
   gcloud iam service-accounts create vertex-chat-user \
     --display-name="Vertex AI Chat User"
   
   gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
     --member="serviceAccount:vertex-chat-user@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
     --role="roles/aiplatform.user"
   ```

4. **Authenticate**
   ```bash
   gcloud auth login
   gcloud auth application-default login
   ```

### Project Structure
Ensure your project has the following structure:
```
mcp-server/
├── main.py                 # Core server (deploy.sh)
├── main_with_ui.py         # UI server (deploy_ui.sh)
├── requirements.txt        # Python dependencies
├── Dockerfile              # Container configuration
├── servers/                # MCP server implementations
│   ├── crm_server.py
│   └── crm_tools.py
├── static/                 # Web UI files (for deploy_ui.sh)
│   └── index.html
├── deploy.sh              # Core deployment script
├── deploy_ui.sh           # UI deployment script
└── cache_manager.py       # Will be added in future updates
```

## Architecture Overview

### Core MCP Server (`deploy.sh`)
```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Client Apps   │───▶│  Cloud Run      │───▶│  Vertex AI      │
│                 │    │  MCP Server     │    │  (Gemini)       │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

### UI Server (`deploy_ui.sh`)
```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Web Browser   │───▶│  Cloud Run      │───▶│  Vertex AI      │
│   (UI)          │    │  UI Server      │    │  (Gemini)       │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                              │
                              ▼
                       ┌─────────────────┐
                       │  CRM System     │
                       │  (External)     │
                       └─────────────────┘
```

## Deployment Scripts

### 1. Core MCP Server (`deploy.sh`)

**Purpose**: Deploys the core MCP server for CRM operations.

**Features**:
- ✅ Optimized resource allocation
- ✅ Scale-to-zero capability
- ✅ High performance architecture
- ✅ Cost-effective deployment

**Usage**:
```bash
# Basic deployment
./deploy.sh

# With custom configuration
PROJECT_ID="your-project" \
REGION="us-central1" \
SERVICE_NAME="my-mcp-server" \
./deploy.sh
```

### 2. UI Server (`deploy_ui.sh`)

**Purpose**: Deploys the MCP server with a web-based user interface.

**Features**:
- ✅ Web UI for easy interaction
- ✅ Real-time streaming responses
- ✅ Cursor-like typing effects
- ✅ Responsive design
- ✅ Tool management interface

**Usage**:
```bash
# Basic deployment
./deploy_ui.sh

# With custom configuration
PROJECT_ID="your-project" \
REGION="us-central1" \
SERVICE_NAME="my-mcp-ui" \
./deploy_ui.sh
```

## Configuration Options

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PROJECT_ID` | Auto-detected | Google Cloud Project ID |
| `REGION` | `australia-southeast1` | Deployment region |
| `SERVICE_NAME` | `insites-mcp-server` | Cloud Run service name |

### Resource Allocation

#### Core Server (`deploy.sh`)
- **Memory**: 512Mi (optimized from 2Gi)
- **CPU**: 1 core (optimized from 2 cores)
- **Concurrency**: 80 requests per instance
- **Min Instances**: 0 (scale to zero)
- **Max Instances**: 10

#### UI Server (`deploy_ui.sh`)
- **Memory**: 2Gi
- **CPU**: 2 cores
- **Max Instances**: 10

## Deployment Process

### Step-by-Step Deployment

1. **Pre-flight Checks**
   ```bash
   # Verify gcloud installation
   gcloud --version
   
   # Check authentication
   gcloud auth list
   
   # Verify project structure
   ls -la main.py servers/ requirements.txt
   ```

2. **Run Deployment**
   ```bash
   # For core server
   chmod +x deploy.sh
   ./deploy.sh
   
   # For UI server
   chmod +x deploy_ui.sh
   ./deploy_ui.sh
   ```

3. **Monitor Deployment**
   - Watch for colored output indicating progress
   - Check for any error messages
   - Verify service URL is provided

### What Happens During Deployment

1. **API Enablement**
   - Cloud Build API
   - Cloud Run API
   - Container Registry API
   - Vertex AI API

2. **Infrastructure Setup**
   - Service account verification

3. **Application Deployment**
   - Docker image build and push
   - Cloud Run service deployment
   - Environment variable configuration
   - Service URL generation

## Post-Deployment

### Verification

1. **Health Check**
   ```bash
   curl https://YOUR_SERVICE_URL/health
   # Expected: {"status": "ok"}
   ```

2. **API Documentation**
   ```bash
   # Open in browser
   https://YOUR_SERVICE_URL/docs
   ```

3. **UI Access** (for deploy_ui.sh)
   ```bash
   # Open in browser
   https://YOUR_SERVICE_URL/ui
   ```

### Testing

#### Core Server Testing
```bash
# Test basic query
curl -X POST "https://YOUR_SERVICE_URL/query" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Get all contacts",
    "instance_url": "YOUR_CRM_URL",
    "instance_api_key": "YOUR_API_KEY"
  }'

# Test tools listing
curl "https://YOUR_SERVICE_URL/tools"
```

#### UI Server Testing
```bash
# Open web interface
open https://YOUR_SERVICE_URL/ui

# Test streaming responses
# Send a message through the UI and verify character-by-character streaming
```

### Monitoring

1. **Cloud Run Console**
   - Visit: https://console.cloud.google.com/run
   - Monitor request volume, latency, and errors

2. **Logs**
   ```bash
   gcloud logs tail --service=YOUR_SERVICE_NAME
   ```

3. **Service Monitoring**
   ```bash
   gcloud logs tail --service=YOUR_SERVICE_NAME
   ```

## Troubleshooting

### Common Issues

#### 1. Authentication Errors
```bash
# Error: Not authenticated with gcloud
gcloud auth login
gcloud auth application-default login
```

#### 2. Service Account Issues
```bash
# Error: Service account does not exist
gcloud iam service-accounts create vertex-chat-user \
  --display-name="Vertex AI Chat User"

gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
  --member="serviceAccount:vertex-chat-user@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/aiplatform.user"
```

#### 3. API Enablement Issues
```bash
# Manually enable required APIs
gcloud services enable cloudbuild.googleapis.com
gcloud services enable run.googleapis.com
gcloud services enable aiplatform.googleapis.com
```

#### 4. Service Connection Issues
```bash
# Check service status
gcloud run services describe YOUR_SERVICE_NAME --region=YOUR_REGION

# Verify service logs
gcloud logs tail --service=YOUR_SERVICE_NAME
```

#### 5. Memory/CPU Issues
```bash
# Check service logs for OOM errors
gcloud logs tail --service=YOUR_SERVICE_NAME --filter="severity>=ERROR"

# Consider increasing resources
# Edit deploy script and increase memory/CPU values
```

### Debug Commands

```bash
# Check service status
gcloud run services describe YOUR_SERVICE_NAME --region=YOUR_REGION

# View recent logs
gcloud logs read --service=YOUR_SERVICE_NAME --limit=50

# Test service connectivity
curl -v https://YOUR_SERVICE_URL/health

# Check Redis connectivity (if caching enabled)
curl https://YOUR_SERVICE_URL/cache/stats
```

## Cost Optimization

### Current Optimizations

1. **Resource Optimization**
   - Reduced memory from 2Gi to 512Mi (75% reduction)
   - Reduced CPU from 2 cores to 1 core (50% reduction)
   - Scale-to-zero capability

2. **Performance Features**
   - Concurrency handling (80 requests per instance)
   - CPU throttling for cost optimization
   - Generation 2 execution environment

### Cost Monitoring

```bash
# Check current costs
gcloud billing accounts list
gcloud billing accounts describe ACCOUNT_ID

# Monitor Cloud Run costs
# Visit: https://console.cloud.google.com/billing
```

### Further Optimization

1. **Adjust Resource Allocation**
   ```bash
   # Edit deploy script to modify:
   --memory 256Mi  # Reduce further if possible
   --cpu 0.5       # Reduce CPU allocation
   --max-instances 5  # Limit maximum instances
   ```

2. **Implement Request Batching**
   - Group multiple requests together
   - Use batch processing where possible

3. **Performance Monitoring**
   - Monitor response times
   - Track error rates
   - Optimize based on usage patterns

## Security Considerations

### Service Account Security

1. **Principle of Least Privilege**
   - Service account has minimal required permissions
   - Only Vertex AI user role assigned

2. **IAM Best Practices**
   ```bash
   # Review service account permissions
   gcloud projects get-iam-policy YOUR_PROJECT_ID \
     --flatten="bindings[].members" \
     --filter="bindings.members:vertex-chat-user@YOUR_PROJECT_ID.iam.gserviceaccount.com"
   ```

### Network Security

1. **HTTPS Enforcement**
   - Cloud Run automatically provides HTTPS
   - All traffic encrypted in transit

2. **Service Isolation**
   - Each service runs in isolated environment
   - No direct network access between services

### Data Security

1. **API Key Management**
   - Store API keys securely
   - Use environment variables
   - Rotate keys regularly

2. **Logging and Monitoring**
   - Monitor for suspicious activity
   - Review access logs regularly
   - Implement alerting for anomalies

## Maintenance

### Regular Tasks

1. **Update Dependencies**
   ```bash
   # Update requirements.txt
   pip freeze > requirements.txt
   
   # Redeploy with updated dependencies
   ./deploy.sh
   ```

2. **Monitor Performance**
   - Check response times
   - Monitor error rates
   - Review performance metrics

3. **Security Updates**
   - Keep base images updated
   - Review security advisories
   - Update dependencies with security patches

### Backup and Recovery

1. **Configuration Backup**
   ```bash
   # Backup deployment configuration
   cp deploy.sh deploy.sh.backup
   cp deploy_ui.sh deploy_ui.sh.backup
   ```

2. **Service Recovery**
   ```bash
   # Redeploy service
   ./deploy.sh
   
   # Or rollback to previous version
   gcloud run services update-traffic YOUR_SERVICE_NAME \
     --to-revisions=REVISION_NAME=100
   ```

## Support

### Getting Help

1. **Check Logs**
   ```bash
   gcloud logs tail --service=YOUR_SERVICE_NAME
   ```

2. **Review Documentation**
   - This deployment guide
   - Google Cloud documentation
   - MCP protocol documentation

3. **Common Resources**
   - [Google Cloud Run Documentation](https://cloud.google.com/run/docs)
   - [Vertex AI Documentation](https://cloud.google.com/vertex-ai/docs)
   - [MCP Protocol Documentation](https://modelcontextprotocol.io/)

### Contact Information

For deployment-specific issues:
- Review the troubleshooting section above
- Check Google Cloud Console for detailed error messages
- Consult Google Cloud support if needed

---

**Last Updated**: January 2025  
**Version**: 1.0  
**Compatibility**: Google Cloud Run, Vertex AI
