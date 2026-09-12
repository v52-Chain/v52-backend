# Vector52 Backend — Render Deployment Guide

## Overview

This guide covers deploying v52-backend to [Render](https://render.com), a modern cloud platform that supports Python applications.

**Deployment Status:** Ready for production  
**Python Version:** 3.11+  
**Stack:** FastAPI + Uvicorn  
**Build Time:** ~2-3 minutes  

---

## Prerequisites

1. **GitHub Repository**: Branch must be pushed to GitHub (feat/franco-rpc-providers or main)
2. **Render Account**: https://render.com (free tier available)
3. **API Keys**: Alchemy, The Graph (optional)
4. **Domain** (optional): For custom CORS origins

---

## Step 1: Prepare Environment Variables

Render requires the following **sensitive** variables to be set via the dashboard (NOT in render.yaml):

### Required (for Ethereum audit functionality)
```
ALCHEMY_API_KEY=BzQ7vfg8Ro9ZLkO9LxymylRQe0bsYY6H
```

### Optional (improves The Graph reliability)
```
V52_GRAPH_API_KEY={your-the-graph-studio-api-key}
```

### Optional (for MongoDB - Phase 1)
```
V52_MONGODB_URI=mongodb+srv://user:password@cluster.mongodb.net/
V52_STORAGE_BACKEND=mongo
```

> **Security:** Never commit API keys to Git. Always use Render's environment variable dashboard.

---

## Step 2: Connect Repository to Render

1. **Go to**: https://dashboard.render.com
2. **Click**: "New +" → "Web Service"
3. **Select**: "Build and deploy from a Git repository"
4. **Authorize GitHub** and select your repository
5. **Choose branch**: `main` or `feat/franco-rpc-providers` (whichever is merged)
6. **Service name**: `vector52-backend`
7. **Runtime**: Python 3.11
8. **Build command**: `pip install -e .`
9. **Start command**: `python -m uvicorn app.main:app --host 0.0.0.0 --port $PORT`
10. **Plan**: Standard or higher (free tier has limitations)

---

## Step 3: Configure Environment Variables

In Render Dashboard → Your Service → Environment:

### Add these variables:

| Variable | Value | Type |
|----------|-------|------|
| `V52_ENV` | `production` | Standard |
| `ALCHEMY_API_KEY` | (Your API key) | Secret |
| `V52_CORS_ORIGINS` | `https://yourfrontend.vercel.app` | Standard |
| `V52_PUBLIC_ORIGIN` | `https://yourfrontend.vercel.app` | Standard |
| `V52_GRAPH_API_KEY` | (Your API key - optional) | Secret |
| `V52_GRAPH_ENDPOINT` | `https://gateway.thegraph.com/api/{api_key}/subgraphs/id/5zvR82QoaXYFyDEKLZ9t6v9adgnptxYpKpSbxtgVENFV` | Standard |
| `RPC_TIMEOUT_MS` | `15000` | Standard |
| `RPC_MAX_RETRIES` | `3` | Standard |
| `V52_STORAGE_BACKEND` | `file` | Standard |
| `V52_DATA_DIR` | `/tmp/evidence_vault` | Standard |

> **Note**: Mark sensitive variables (API keys) as "Secret" so they don't appear in logs.

---

## Step 4: Deploy

### Option A: Automatic Deploy
- Push to GitHub → Render automatically redeploys
- Configured in `render.yaml` with `autoDeploy: true`

### Option B: Manual Deploy
1. Render Dashboard → Your Service
2. Click **"Manual Deploy"** → Select branch
3. Wait for build and deployment (2-3 minutes)

---

## Step 5: Verify Deployment

### Check Status
```bash
# Get your Render URL from dashboard
# It looks like: https://vector52-backend.render.com

# Test health endpoint
curl https://vector52-backend.render.com/healthz
# Expected: {"status":"ok","version":"0.1.0"}
```

### Check Logs
```bash
# In Render Dashboard → Logs
# Look for: "Application startup complete"
```

### Test Provider Status
```bash
curl https://vector52-backend.render.com/v1/providers/status
# Should return: ethereum UP, avalanche UP, graph CONFIGURED
```

---

## Monitoring & Logs

### Live Logs
- Render Dashboard → Your Service → Logs
- Shows real-time application output

### Health Check
- Render monitors `/healthz` endpoint every 30 seconds
- Service automatically restarts if unhealthy

### Performance Metrics
- CPU, Memory, Build time visible in dashboard

---

## Troubleshooting

### Build Fails: "ModuleNotFoundError"
**Solution**: Ensure `setuptools>=68` is installed
```bash
# Push this change:
# In pyproject.toml, verify [build-system]
```

### 502 Bad Gateway
**Likely causes**:
1. App crashed (check logs)
2. V52_ENV not set to "production"
3. Port binding issue

**Solution**:
```bash
# Check logs for errors
# Verify environment variables are set
# Restart service from Render dashboard
```

### CORS Error from Frontend
**Solution**: Add your frontend URL to `V52_CORS_ORIGINS`
```
V52_CORS_ORIGINS=https://yourfrontend.vercel.app,https://preview.yourfrontend.vercel.app
```

### Alchemy 403 Error
**Cause**: Avalanche not enabled in Alchemy app, OR rate limits exceeded

**Solution**:
1. Go to https://dashboard.alchemy.com/apps
2. Select your app → Networks → Enable Avalanche C-Chain
3. If rate-limited, wait or upgrade plan

### Graph Tests Skipped
**This is normal** — V52_GRAPH_API_KEY is optional

**To enable**: Add your API key to Render environment variables

---

## Database Migration (Future - Phase 1)

When ready to use MongoDB:

1. **Set up MongoDB Atlas**:
   - https://www.mongodb.com/cloud/atlas
   - Create free cluster
   - Generate connection string

2. **Add to Render environment**:
   ```
   V52_MONGODB_URI={your-connection-string}
   V52_STORAGE_BACKEND=mongo
   ```

3. **Restart service**

---

## Scaling & Optimization

### Current Configuration
- Plan: Standard (good for MVP)
- Memory: 1GB (sufficient for < 1000 req/min)
- CPU: Shared

### For High Traffic
- Upgrade to Pro plan
- Enable horizontal scaling
- Add Redis for caching (`V52_CACHE_ENABLED=true`)

### Performance Tips
1. Increase `RPC_TIMEOUT_MS` to 20000 for reliability
2. Set `RPC_MAX_RETRIES=5` for production
3. Enable caching: `V52_CACHE_ENABLED=true`

---

## Rollback

If deployment breaks:

1. **Render Dashboard** → Your Service
2. **Deployments** tab
3. Click previous working version → **Redeploy**
4. Service reverts to last stable deployment

---

## Cost Estimate

| Tier | Cost | Includes |
|------|------|----------|
| Free | $0 | Spinning instance (slow start) |
| Standard | $7/mo | Always-on instance, good for MVP |
| Pro | $12/mo | Dedicated resources, scaling |

**Recommendation**: Start with Standard tier for stable development.

---

## Next Steps

1. ✅ Merge feat/franco-rpc-providers to main (if not already done)
2. ✅ Create Render account
3. ✅ Connect GitHub repository
4. ✅ Set environment variables
5. ✅ Deploy
6. ✅ Test endpoints
7. ✅ Share API URL with frontend team

---

## Support & Documentation

- **Render Docs**: https://render.com/docs
- **FastAPI Docs**: https://fastapi.tiangolo.com
- **Vector52 API Docs**: https://api.vector52.xyz/docs (after deployment)

---

## Key Files

- `Procfile` — Process file for Render
- `render.yaml` — Render configuration (optional, can be set in UI)
- `pyproject.toml` — Python dependencies
- `.env.example` — Template for environment variables
- `.gitignore` — Excludes .env and secrets

