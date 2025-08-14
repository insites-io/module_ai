# Credentials Setup Guide

## Overview
This project requires Google Cloud credentials for authentication with Vertex AI and other Google Cloud services. For security reasons, the actual credentials file is not included in the repository.

## Setup Instructions

### Option 1: Use Template File (Recommended for Development)
1. Copy the template file:
   ```bash
   cp vertex-credentials.template.json vertex-credentials.json
   ```

2. Edit `vertex-credentials.json` with your actual credentials:
   - Replace `your-project-id-here` with your Google Cloud project ID
   - Replace `your-private-key-id-here` with your private key ID
   - Replace `YOUR_PRIVATE_KEY_CONTENT_HERE` with your actual private key
   - Replace `your-service-account@your-project-id.iam.gserviceaccount.com` with your service account email
   - Replace `your-client-id-here` with your client ID

### Option 2: Use Environment Variables (Recommended for Production)
Set the following environment variables instead of using a credentials file:

```bash
export GOOGLE_APPLICATION_CREDENTIALS="path/to/your/credentials.json"
export GOOGLE_CLOUD_PROJECT="your-project-id"
export GOOGLE_CLOUD_REGION="your-region"
```

### Option 3: Use Google Cloud CLI Authentication
If you're running locally and have `gcloud` CLI configured:

```bash
gcloud auth application-default login
```

## Getting Credentials

### Create Service Account
1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Navigate to IAM & Admin > Service Accounts
3. Click "Create Service Account"
4. Give it a name and description
5. Grant necessary roles (e.g., `Vertex AI User`, `Cloud Build Editor`)
6. Create and download the JSON key

### Required Permissions
Your service account needs these roles:
- `Vertex AI User` - For accessing Vertex AI services
- `Cloud Build Editor` - For building and deploying containers
- `Service Account User` - For running as a service account
- `Storage Object Viewer` - For accessing Cloud Storage

## Security Notes

⚠️ **IMPORTANT**: Never commit real credentials to the repository!

- The `vertex-credentials.json` file is in `.gitignore`
- Use environment variables in production environments
- Rotate credentials regularly
- Use least-privilege access principles

## Deployment

### Local Development
- Copy the template and fill in your credentials
- The Dockerfile will use the local credentials file

### Cloud Build
- Store credentials in Google Cloud Secret Manager
- Reference them in your cloudbuild.yaml
- Use environment variables in the build process

### Kubernetes/Cloud Run
- Mount credentials as secrets
- Use environment variables for configuration

## Troubleshooting

### "No vertex-credentials.json found"
This is normal if you're using environment variables. The application will fall back to:
1. Environment variables
2. Google Cloud default credentials
3. Service account metadata (if running on GCP)

### Authentication Errors
1. Verify your service account has the correct permissions
2. Check that your project ID is correct
3. Ensure your credentials haven't expired
4. Verify the service account is enabled

## Example Environment Setup

```bash
# Development
cp vertex-credentials.template.json vertex-credentials.json
# Edit the file with your credentials

# Production
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/credentials.json"
export GOOGLE_CLOUD_PROJECT="my-project-123"
export GOOGLE_CLOUD_REGION="us-central1"
```
