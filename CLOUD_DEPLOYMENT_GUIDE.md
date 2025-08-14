# Cloud MCP Server Deployment Guide

This guide will help you deploy your CRM MCP server to Google Cloud Run and use it with Claude Desktop.

## 🚀 Quick Start

### 1. Deploy to Cloud Run

```bash
# Make sure you're authenticated with gcloud
gcloud auth login

# Deploy the cloud MCP server
./deploy_cloud_mcp.sh
```

### 2. Set CRM Credentials

```bash
# Get your service name and region from the deployment output
gcloud run services update cloud-crm-mcp --region=australia-southeast1 \
  --set-env-vars CRM_INSTANCE_URL='https://your-crm-instance.com',CRM_INSTANCE_API_KEY='your-api-key'
```

### 3. Configure Claude Desktop

- **Name:** Cloud CRM Server
- **Transport:** http
- **URL:** `https://your-service-url.run.app/mcp`

## 📋 Prerequisites

- Google Cloud account with billing enabled
- `gcloud` CLI installed and authenticated
- Python 3.8+ and pip
- Access to your CRM instance with API credentials

## 🔧 Detailed Deployment Steps

### Step 1: Prepare Your Environment

```bash
# Install gcloud CLI (if not already installed)
# macOS:
brew install google-cloud-sdk

# Linux:
curl https://sdk.cloud.google.com | bash
exec -l $SHELL

# Authenticate with Google Cloud
gcloud auth login
gcloud config set project YOUR_PROJECT_ID
```

### Step 2: Deploy the Server

```bash
# Run the deployment script
./deploy_cloud_mcp.sh

# Or deploy manually:
gcloud builds submit --tag gcr.io/YOUR_PROJECT_ID/cloud-crm-mcp -f Dockerfile.cloud .
gcloud run deploy cloud-crm-mcp \
  --image gcr.io/YOUR_PROJECT_ID/cloud-crm-mcp \
  --platform managed \
  --region australia-southeast1 \
  --allow-unauthenticated \
  --port 8080 \
  --memory 1Gi \
  --cpu 1
```

### Step 3: Configure CRM Credentials

```bash
# Set your CRM credentials as environment variables
gcloud run services update cloud-crm-mcp --region=australia-southeast1 \
  --set-env-vars CRM_INSTANCE_URL='https://your-crm-instance.com',CRM_INSTANCE_API_KEY='your-api-key'
```

### Step 4: Test the Deployment

```bash
# Get your service URL
SERVICE_URL=$(gcloud run services describe cloud-crm-mcp --region=australia-southeast1 --format="value(status.url)")

# Test the health endpoint
curl "$SERVICE_URL/health"

# Test the MCP endpoint
curl -X POST "$SERVICE_URL/mcp" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}'
```

## 🖥️ Claude Desktop Configuration

### Option 1: HTTP Transport (Recommended)

1. **Open Claude Desktop**
2. **Go to Settings** (gear icon)
3. **Navigate to "Tools" section**
4. **Click "Add Tool"**
5. **Select "MCP Server"**
6. **Configure:**
   - **Name:** Cloud CRM Server
   - **Transport:** http
   - **URL:** `https://your-service-url.run.app/mcp`

### Option 2: Local Development

If you want to test locally before deploying:

```bash
# Set environment variables
export CRM_INSTANCE_URL="https://your-crm-instance.com"
export CRM_INSTANCE_API_KEY="your-api-key"

# Run locally
python servers/cloud_crm_server.py

# In Claude Desktop, use:
# - Transport: http
# - URL: http://localhost:8080/mcp
```

## 🔍 Testing Your Setup

### 1. Check Available Tools

Ask Claude: "What tools are available from the CRM server?"

### 2. Test a Tool

Ask Claude: "Get me all contacts from the CRM"

### 3. Verify Response

Claude should be able to:
- Connect to your cloud MCP server
- List available CRM tools
- Execute CRM queries and return results

## 🚨 Troubleshooting

### Common Issues

1. **"Service not found" error:**
   ```bash
   # Check if service exists
   gcloud run services list --region=australia-southeast1
   ```

2. **"Permission denied" error:**
   ```bash
   # Ensure you're authenticated
   gcloud auth list
   gcloud config get-value project
   ```

3. **"Environment variables not set" error:**
   ```bash
   # Check current environment variables
   gcloud run services describe cloud-crm-mcp --region=australia-southeast1 --format="value(spec.template.spec.containers[0].env[].name,spec.template.spec.containers[0].env[].value)"
   ```

4. **"Connection timeout" in Claude Desktop:**
   - Verify your service URL is correct
   - Check if the service is running: `gcloud run services describe cloud-crm-mcp --region=australia-southeast1`
   - Ensure the service allows unauthenticated access

### Debugging Commands

```bash
# View service logs
gcloud run services logs read cloud-crm-mcp --region=australia-southeast1

# Update service with new environment variables
gcloud run services update cloud-crm-mcp --region=australia-southeast1 \
  --set-env-vars CRM_INSTANCE_URL='https://new-url.com',CRM_INSTANCE_API_KEY='new-key'

# Delete and redeploy if needed
gcloud run services delete cloud-crm-mcp --region=australia-southeast1
./deploy_cloud_mcp.sh
```

## 🔒 Security Considerations

- **API Keys:** Never commit API keys to version control
- **Environment Variables:** Use Cloud Run's environment variable feature
- **Access Control:** Consider restricting access to authenticated users only
- **HTTPS:** Cloud Run automatically provides HTTPS endpoints
- **Monitoring:** Set up Cloud Monitoring for production use

## 📊 Monitoring and Scaling

### View Metrics

```bash
# View service metrics
gcloud run services describe cloud-crm-mcp --region=australia-southeast1

# Check Cloud Build logs
gcloud builds list --limit=10
```

### Scaling

The service is configured to:
- **Memory:** 1GB (configurable)
- **CPU:** 1 vCPU (configurable)
- **Max Instances:** 5 (configurable)
- **Auto-scaling:** Enabled by default

### Cost Optimization

- **Memory:** Start with 1GB, increase if needed
- **CPU:** 1 vCPU is usually sufficient for MCP servers
- **Max Instances:** Limit to control costs
- **Region:** Choose closest to your users

## 🎯 Next Steps

Once deployed:

1. **Test all CRM tools** through Claude Desktop
2. **Monitor performance** and adjust resources as needed
3. **Set up alerts** for errors or high usage
4. **Consider production hardening** (authentication, monitoring, etc.)

## 📚 Additional Resources

- [Google Cloud Run Documentation](https://cloud.google.com/run/docs)
- [MCP Protocol Specification](https://modelcontextprotocol.io/)
- [Claude Desktop Tools](https://docs.anthropic.com/claude/docs/tools-overview)

Your cloud-based CRM MCP server is now ready to use with Claude Desktop! 🎉


