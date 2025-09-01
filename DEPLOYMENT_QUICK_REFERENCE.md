# Deployment Quick Reference Guide

## 🚀 Quick Start Commands

### Basic Deployment
```bash
# Core MCP Server
./deploy.sh

# UI Server
./deploy_ui.sh
```

### Custom Configuration
```bash
# Deploy with custom settings
PROJECT_ID="my-project" \
REGION="us-central1" \
SERVICE_NAME="my-crm-server" \
./deploy.sh
```

## 📋 Pre-Deployment Checklist

- [ ] `gcloud auth login` completed
- [ ] `gcloud config set project PROJECT_ID` set
- [ ] Service account `vertex-chat-user` exists
- [ ] Billing enabled on project
- [ ] Project structure verified (`main.py`, `servers/`, `requirements.txt`)

## 🔧 Common Commands

### Service Management
```bash
# Check service status
gcloud run services describe SERVICE_NAME --region=REGION

# View logs
gcloud logs tail --service=SERVICE_NAME

# Update service
gcloud run services update SERVICE_NAME --region=REGION

# Delete service
gcloud run services delete SERVICE_NAME --region=REGION
```

### Testing Endpoints
```bash
# Health check
curl https://SERVICE_URL/health

# API docs
open https://SERVICE_URL/docs

# UI (for deploy_ui.sh)
open https://SERVICE_URL/ui

# Test query
curl -X POST "https://SERVICE_URL/query" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Get all contacts", "instance_url": "URL", "instance_api_key": "KEY"}'
```

## 🛠️ Troubleshooting Quick Fixes

### Authentication Issues
```bash
gcloud auth login
gcloud auth application-default login
```

### Service Account Issues
```bash
# Create service account
gcloud iam service-accounts create vertex-chat-user --display-name="Vertex AI Chat User"

# Grant permissions
gcloud projects add-iam-policy-binding PROJECT_ID \
  --member="serviceAccount:vertex-chat-user@PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/aiplatform.user"
```

### API Issues
```bash
# Enable required APIs
gcloud services enable cloudbuild.googleapis.com
gcloud services enable run.googleapis.com
gcloud services enable aiplatform.googleapis.com
gcloud services enable redis.googleapis.com
gcloud services enable vpcaccess.googleapis.com
```

### Service Issues
```bash
# Check service status
gcloud run services describe SERVICE_NAME --region=REGION

# Check service logs
gcloud logs tail --service=SERVICE_NAME
```

## 📊 Monitoring Commands

### Performance Monitoring
```bash
# View recent requests
gcloud logs read --service=SERVICE_NAME --limit=20

# Check errors
gcloud logs tail --service=SERVICE_NAME --filter="severity>=ERROR"

# Monitor service performance
gcloud logs tail --service=SERVICE_NAME
```

### Cost Monitoring
```bash
# Check billing
gcloud billing accounts list

# View costs
# Visit: https://console.cloud.google.com/billing
```

## 🔄 Update and Maintenance

### Update Dependencies
```bash
# Update requirements
pip freeze > requirements.txt

# Redeploy
./deploy.sh
```

### Rollback Service
```bash
# List revisions
gcloud run revisions list --service=SERVICE_NAME --region=REGION

# Rollback to specific revision
gcloud run services update-traffic SERVICE_NAME \
  --to-revisions=REVISION_NAME=100
```

## 🎯 Environment Variables Reference

| Variable | Default | Description |
|----------|---------|-------------|
| `PROJECT_ID` | Auto-detected | Google Cloud Project ID |
| `REGION` | `australia-southeast1` | Deployment region |
| `SERVICE_NAME` | `insites-mcp-server` | Cloud Run service name |

## 📱 Resource Allocation

### Core Server (`deploy.sh`)
- Memory: 512Mi
- CPU: 1 core
- Concurrency: 80 requests
- Min Instances: 0
- Max Instances: 10

### UI Server (`deploy_ui.sh`)
- Memory: 2Gi
- CPU: 2 cores
- Max Instances: 10

## 🔐 Security Quick Checks

```bash
# Check service account permissions
gcloud projects get-iam-policy PROJECT_ID \
  --flatten="bindings[].members" \
  --filter="bindings.members:vertex-chat-user@PROJECT_ID.iam.gserviceaccount.com"

# Verify HTTPS
curl -I https://SERVICE_URL/health
```

## 📞 Emergency Contacts

- **Google Cloud Support**: https://cloud.google.com/support
- **Cloud Run Documentation**: https://cloud.google.com/run/docs
- **Vertex AI Documentation**: https://cloud.google.com/vertex-ai/docs

## 🎉 Success Indicators

After successful deployment, you should see:
- ✅ Service URL provided
- ✅ Health check returns `{"status": "ok"}`
- ✅ API docs accessible
- ✅ UI accessible (for deploy_ui.sh)
- ✅ No error messages in logs

---

**Quick Reference Version**: 1.0  
**Last Updated**: January 2025
