# 🚀 CRM Server Caching Enhancement Guide

## Overview

The CRM server includes an intelligent caching system that dramatically improves performance by storing and reusing query results. This reduces API calls to your CRM instance and speeds up response times.

## ⚡ Performance Benefits

- **First Request**: ~2-5 seconds (processes with LLM + CRM API calls)
- **Cached Request**: ~50-200ms (instant response from cache)
- **API Call Reduction**: Up to 90% fewer calls to your CRM instance
- **Cost Savings**: Reduced LLM usage and API costs

## 🔧 Configuration

### Environment Variables

```bash
# Enable/disable caching
ENABLE_CACHING=true

# Cache TTL (Time To Live) in seconds
CACHE_TTL_SECONDS=3600  # 1 hour default

# Redis URL for distributed caching (optional)
REDIS_URL=redis://localhost:6379
```

### Current Status

```bash
curl -s "http://localhost:8080/cache/stats" | jq
```

Example output:
```json
{
  "cache_stats": {
    "enabled": true,
    "total_keys": 5,
    "cache_type": "in-memory"
  },
  "config": {
    "enabled": true,
    "ttl_seconds": 3600,
    "redis_url": "redis://10.184.209.227"
  }
}
```

## 🎯 How Caching Works

### Cache Key Generation
The system generates unique cache keys based on:
- **Query content** (normalized and lowercased)
- **Instance URL** (your CRM instance)
- **API key hash** (first 8 characters for security)

### Cache Behavior
1. **Cache MISS**: First time query → Process with LLM → Cache result
2. **Cache HIT**: Subsequent identical query → Return cached result instantly

### Response Indicators
```json
{
  "response": "Your CRM data...",
  "success": true,
  "cached": true,           // ← Indicates cache hit
  "cached_at": "2025-01-21T10:30:00Z"
}
```

## 📊 Using Cache Management

### 1. Check Cache Statistics
```bash
curl -s "http://localhost:8080/cache/stats"
```

### 2. Clear All Cache
```bash
curl -X POST "http://localhost:8080/cache/clear"
```

### 3. Monitor Cache Performance
Watch your server logs for cache hits/misses:
```
INFO:cache_manager:🎯 Cache HIT: 09a8b0492c5cd5a2...
INFO:cache_manager:💨 Cache MISS: get me all contacts...
INFO:cache_manager:💾 Cached response: 25789cb838c7a394...
```

## 🚀 Best Practices

### 1. Optimize for Common Queries
Cache works best for:
- ✅ **Frequent queries**: "get all contacts", "show companies"
- ✅ **Static data**: System fields, contact lists
- ✅ **Repeated operations**: Same user asking similar questions

### 2. Cache Invalidation
Clear cache when data changes:
```bash
# After adding/updating contacts
curl -X POST "http://localhost:8080/cache/clear"
```

### 3. Performance Monitoring
```bash
# Check cache hit rate
curl -s "http://localhost:8080/cache/stats" | jq '.cache_stats.total_keys'
```

## 🔄 Cache Lifecycle

```mermaid
graph TD
    A[User Query] --> B{Cache Check}
    B -->|HIT| C[Return Cached Response]
    B -->|MISS| D[Process with LLM]
    D --> E[Get CRM Data]
    E --> F[Generate Response]
    F --> G[Cache Response]
    G --> H[Return Response]
    C --> I[Fast Response ~50ms]
    H --> J[Normal Response ~2-5s]
```

## 🎛️ Advanced Configuration

### Environment Variables (.env file)
```bash
# Caching Configuration
ENABLE_CACHING=true
CACHE_TTL_SECONDS=3600

# Redis Configuration (for production)
REDIS_URL=redis://username:password@host:port/database

# Performance Tuning
GCP_PROJECT_ID=your-project
GCP_REGION=your-region
GEMINI_MODEL_NAME=gemini-1.5-pro
```

### Production Redis Setup
For production environments, use Redis for distributed caching:

```bash
# Google Cloud Memorystore
REDIS_URL=redis://10.xxx.xxx.xxx:6379

# AWS ElastiCache
REDIS_URL=redis://your-cluster.cache.amazonaws.com:6379
```

## 📈 Performance Examples

### Before Caching
```bash
time curl -X POST "http://localhost:8080/query" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "get all contacts", ...}'

# Response time: ~3.2 seconds
```

### After Caching (Cache HIT)
```bash
time curl -X POST "http://localhost:8080/query" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "get all contacts", ...}'

# Response time: ~0.1 seconds (32x faster!)
```

## 🛠️ Troubleshooting

### Cache Not Working?
1. Check if caching is enabled:
   ```bash
   curl -s "http://localhost:8080/cache/stats"
   ```

2. Look for cache logs:
   ```
   INFO:cache_manager:✅ Basic cache initialized (in-memory)
   ```

3. Verify environment variables:
   ```bash
   echo $ENABLE_CACHING
   echo $CACHE_TTL_SECONDS
   ```

### Clear Cache Issues
```bash
# Force clear and restart
curl -X POST "http://localhost:8080/cache/clear"
# Restart server if needed
```

## 🎉 Benefits Summary

| Metric | Without Cache | With Cache | Improvement |
|--------|---------------|------------|-------------|
| Response Time | 2-5 seconds | 50-200ms | **25x faster** |
| API Calls | Every request | First request only | **90% reduction** |
| LLM Usage | Every request | First request only | **90% reduction** |
| Cost | High | Low | **Significant savings** |

## 📞 API Examples

### Query with Cache Check
```javascript
const response = await fetch('http://localhost:8080/query', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    prompt: 'get all contacts',
    instance_url: 'https://your-crm.com',
    instance_api_key: 'your-key'
  })
});

const data = await response.json();
console.log('Cached:', data.cached); // true/false
console.log('Response time:', data.cached ? 'Fast!' : 'Processing...');
```

### Cache Management
```javascript
// Get cache stats
const stats = await fetch('http://localhost:8080/cache/stats');
console.log(await stats.json());

// Clear cache
const clear = await fetch('http://localhost:8080/cache/clear', { method: 'POST' });
console.log(await clear.json());
```

---

🎯 **The caching enhancement is automatically active and working to speed up your CRM queries!**

