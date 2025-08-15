# MCP CRM Server

A FastAPI-based server that integrates with CRM systems using the Model Context Protocol (MCP) and LangChain. This server provides a REST API interface for CRM operations with streaming responses and real-time updates.

## Features

- 🚀 **FastAPI Server**: Modern, fast web framework with automatic API documentation
- 🔗 **MCP Integration**: Uses Model Context Protocol for tool management
- 🤖 **LangChain Agent**: Powered by Google Vertex AI Gemini models
- 📡 **Real-time Streaming**: Server-Sent Events (SSE) for live response streaming
- 🐳 **Docker Ready**: Containerized for easy deployment
- ☁️ **Cloud Run Compatible**: Optimized for Google Cloud Platform deployment
- 🛠️ **Tool Discovery**: Built-in endpoints to list and discover available MCP tools

## Tool Discovery

The MCP CRM Server provides multiple ways to discover and list available tools:

### 1. API Endpoint for Tool Listing

```bash
# Get all available tools via REST API
GET /tools

# Response includes tool names, descriptions, and parameter schemas
{
  "success": true,
  "total_tools": 13,
  "tools": [
    {
      "name": "get_contacts",
      "description": "Get all contacts from the CRM system",
      "schema": {...}
    },
    ...
  ]
}
```

### 2. Built-in Tool for Discovery

The CRM server includes a `list_available_tools` tool that can be called directly:

```python
# When using the MCP server directly
result = await list_available_tools()
# Returns detailed information about all available tools
```

### 3. Standalone Discovery Script

Use the included `discover_tools.py` script to discover tools without starting the full server:

```bash
python discover_tools.py
```

This will output a formatted list of all available tools with their descriptions and parameters.

### Available Tools

The CRM server provides the following tools:

- **Contact Management**: `get_contacts`, `get_contact_by_uuid`, `save_contact`
- **Address Management**: `get_contact_addresses`, `get_contact_addresses_by_uuid`
- **Company Management**: `get_companies`, `get_company_relationships`, `get_company_addresses`
- **System Fields**: `get_system_fields`, `get_contact_sytem_fields`, `get_company_sytem_fields`
- **Utility**: `list_available_tools`

Each tool includes proper documentation, parameter validation, and error handling.

## Prerequisites

- Python 3.11+
- Google Cloud Platform account
- Google Cloud CLI (`gcloud`) installed and authenticated
- Vertex AI API enabled
- Service account with appropriate permissions

## Quick Start

### 1. Clone and Setup

```bash
git clone <your-repo-url>
cd mcp-server
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Environment Configuration

Create a `.env` file in the root directory:

```bash
GCP_PROJECT_ID=your-project-id
GCP_REGION=your-region
GEMINI_MODEL_NAME=gemini-1.5-pro
```

### 3. Vertex AI Credentials

Place your `vertex-credentials.json` file in the root directory. This file should contain your service account credentials for Vertex AI access.

### 4. Local Development

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8080
```

The server will be available at `http://localhost:8080`

## Deployment

### Option 1: Google Cloud Run (Recommended)

#### Prerequisites
- Google Cloud CLI installed and authenticated
- Project with billing enabled
- Required APIs enabled

#### Deploy using the script

```bash
# Make the script executable
chmod +x deploy.sh

# Set environment variables (optional, defaults will be used)
export PROJECT_ID="your-project-id"
export REGION="your-region"
export SERVICE_NAME="crm-server"

# Run deployment
./deploy.sh
```

#### Manual deployment

```bash
# Set your project
gcloud config set project YOUR_PROJECT_ID

# Enable required APIs
gcloud services enable cloudbuild.googleapis.com
gcloud services enable run.googleapis.com
gcloud services enable containerregistry.googleapis.com

# Build and deploy
gcloud builds submit --tag gcr.io/YOUR_PROJECT_ID/crm-server .
gcloud run deploy crm-server \
    --image gcr.io/YOUR_PROJECT_ID/crm-server \
    --platform managed \
    --region YOUR_REGION \
    --allow-unauthenticated \
    --port 8080 \
    --memory 2Gi \
    --cpu 2 \
    --max-instances 10 \
    --set-env-vars "GCP_PROJECT_ID=YOUR_PROJECT_ID,GCP_REGION=YOUR_REGION"
```

### Option 2: Docker Compose

```bash
docker-compose up -d
```

### Option 3: Kubernetes

```bash
kubectl apply -f k8s/
```

## API Usage

### Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/` | Health check |
| `GET` | `/docs` | API documentation |
| `POST` | `/messages` | Send prompt with streaming response |
| `POST` | `/query` | Direct query (synchronous) |
| `GET` | `/sse` | Server-Sent Events stream |

### Example Usage

#### 1. Streaming Response (Recommended)

```bash
# Start SSE connection
curl -N "http://your-service-url/sse?session_id=123&instance_url=https://your-crm.com&instance_api_key=your-api-key"

# Send prompt
curl -X POST "http://your-service-url/messages?session_id=123&instance_url=https://your-crm.com&instance_api_key=your-api-key" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Get me all contacts"}'
```

#### 2. Direct Query

```bash
curl -X POST "http://your-service-url/query?instance_url=https://your-crm.com&instance_api_key=your-api-key" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Get me all contacts"}'
```

### JavaScript Client Example

```javascript
// Establish SSE connection
const eventSource = new EventSource(
  `http://your-service-url/sse?session_id=${sessionId}&instance_url=${instanceUrl}&instance_api_key=${apiKey}`
);

eventSource.onmessage = function(event) {
  if (event.data === 'CONNECTED') {
    console.log('Connected to server');
  } else if (event.data === 'END_STREAM') {
    console.log('Stream ended');
    eventSource.close();
  } else {
    console.log('Received:', event.data);
  }
};

// Send prompt
fetch(`http://your-service-url/messages?session_id=${sessionId}&instance_url=${instanceUrl}&instance_api_key=${apiKey}`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ prompt: 'Get me all contacts' })
});
```

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `GCP_PROJECT_ID` | Google Cloud Project ID | Required |
| `GCP_REGION` | Google Cloud Region | Required |
| `GEMINI_MODEL_NAME` | Vertex AI model name | `gemini-1.5-pro` |

### CRM Server Configuration

The CRM server (`servers/crm_server.py`) accepts command-line arguments:

- `--instance-url`: Your CRM instance URL
- `--instance-api-key`: Your CRM instance API key

## Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Client App    │    │   MCP Server     │    │   CRM System    │
│                 │    │                  │    │                 │
│ • Web UI       │◄──►│ • FastAPI        │◄──►│ • REST API      │
│ • Mobile App   │    │ • LangChain      │    │ • Database      │
│ • CLI Tool     │    │ • MCP Tools      │    │ • Business      │
└─────────────────┘    └──────────────────┘    │   Logic        │
                                               └─────────────────┘
```

## Development

### Project Structure

```
mcp-server/
├── main.py                 # FastAPI server
├── servers/
│   └── crm_server.py      # MCP CRM server
├── static/                 # Static files
├── requirements.txt        # Python dependencies
├── Dockerfile             # Docker configuration
├── deploy.sh              # Deployment script
└── README.md              # This file
```

### Adding New MCP Tools

1. Create a new server in the `servers/` directory
2. Implement the MCP protocol interface
3. Update the deployment script if needed
4. Test locally before deploying

### Testing

```bash
# Run tests
python -m pytest

# Test MCP tools
python test_mcp_tools.py

# Test agent
python test_agent.py
```

## Troubleshooting

### Common Issues

1. **Authentication Errors**
   - Ensure `vertex-credentials.json` is properly configured
   - Check service account permissions

2. **MCP Connection Issues**
   - Verify server arguments in deployment
   - Check server logs for connection errors

3. **Memory Issues**
   - Increase Cloud Run memory allocation
   - Optimize model parameters

### Logs

```bash
# View Cloud Run logs
gcloud logs read --service=crm-server --limit=50

# View local logs
tail -f math_server.log
```

## Security Considerations

- Store API keys securely (use environment variables or secrets)
- Implement proper authentication for production use
- Use HTTPS in production
- Regularly rotate credentials
- Monitor API usage and implement rate limiting

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## License

[Add your license information here]

## Support

For issues and questions:
- Create an issue in the repository
- Check the API documentation at `/docs`
- Review the troubleshooting section above
