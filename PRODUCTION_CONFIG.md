# Production Configuration for Vector52 Backend

## Frontend & Backend URLs

**Frontend (Vercel):**
```
https://v52-chain.vercel.app/
```

**Backend (Render):**
```
https://v52-backend.onrender.com/
```

---

## Environment Variables for Render

Configure these in Render Dashboard → Environment:

### Critical (Secrets) — Mark as "Secret"
```
ALCHEMY_API_KEY=BzQ7vfg8Ro9ZLkO9LxymylRQe0bsYY6H
V52_GRAPH_API_KEY=1536dc5ff754672341c8cbe780065abc
```

### Standard Configuration
```
V52_ENV=production
V52_CORS_ORIGINS=https://v52-chain.vercel.app/
V52_PUBLIC_ORIGIN=https://v52-chain.vercel.app/
V52_GRAPH_ENDPOINT=https://gateway.thegraph.com/api/{api_key}/subgraphs/id/5zvR82QoaXYFyDEKLZ9t6v9adgnptxYpKpSbxtgVENFV
RPC_TIMEOUT_MS=15000
RPC_MAX_RETRIES=3
V52_STORAGE_BACKEND=file
V52_DATA_DIR=/tmp/evidence_vault
V52_AI_ENABLED=false
V52_X402_ENABLED=false
V52_CACHE_ENABLED=false
```

---

## Testing After Deployment

### 1. Health Check
```bash
curl https://v52-backend.onrender.com/healthz
# Expected: {"status":"ok","version":"0.1.0"}
```

### 2. Root Endpoint
```bash
curl https://v52-backend.onrender.com/
# Shows API info and links to documentation
```

### 3. Provider Status
```bash
curl https://v52-backend.onrender.com/v1/providers/status
# Expected: ethereum UP, avalanche UP, graph CONFIGURED
```

### 4. Interactive Documentation
```
Open in browser: https://v52-backend.onrender.com/docs
```

### 5. Frontend Integration
1. Frontend at https://v52-chain.vercel.app/ should now call backend
2. Check browser console for CORS errors (unlikely with proper config)
3. Test audit endpoint with real Ethereum transaction

---

## Frontend Configuration

Your frontend (v52-chain) should have this backend URL:

```env
VITE_API_URL=https://v52-backend.onrender.com
```

Or hardcoded endpoint calls:
```typescript
const apiUrl = "https://v52-backend.onrender.com";

// Examples:
fetch(`${apiUrl}/healthz`)
fetch(`${apiUrl}/v1/providers/status`)
fetch(`${apiUrl}/v1/audits`, {method: "POST", body: ...})
```

---

## Monitoring

### Render Dashboard
- **Logs**: Real-time application output
- **Metrics**: CPU, Memory, Build time
- **Deployments**: See all deployment history
- **Health Check**: `/healthz` monitored every 30 seconds

### Key Indicators
- ✅ Status should show "Live"
- ✅ Latest deploy should be "Deployed"
- ✅ No error lines in logs containing "ValidationError"

---

## Troubleshooting

### 502 Bad Gateway
**Cause**: Application crashed or not responding

**Fix**:
1. Check Render logs for errors
2. Verify all required env vars are set
3. Restart service: Render Dashboard → "Restart" button

### CORS Errors in Frontend
**Cause**: V52_CORS_ORIGINS doesn't include frontend URL

**Fix**:
1. Go to Render → Environment
2. Update `V52_CORS_ORIGINS=https://v52-chain.vercel.app/`
3. Manual Deploy to apply changes

### 404 Not Found on Root
**Expected**: Accessing `/` returns JSON with API info

**If getting 404**: 
1. Redeploy from commit `03850b6` or later
2. Clear browser cache

---

## Architecture

```
┌─────────────────────────┐
│  Frontend (Vercel)      │
│ v52-chain.vercel.app/   │
└────────────┬────────────┘
             │ HTTPS
             ↓
┌─────────────────────────┐
│  Backend (Render)       │
│ v52-backend.onrender.com│
├─────────────────────────┤
│ • FastAPI + Uvicorn     │
│ • Alchemy RPC (ETH+AVX) │
│ • The Graph Indexer     │
│ • Evidence Vault        │
└─────────────────────────┘
```

---

## Next Steps

- [ ] Verify all env vars set in Render
- [ ] Redeploy backend
- [ ] Test `/healthz` endpoint
- [ ] Test from frontend
- [ ] Monitor logs for 24h
- [ ] Document any issues
- [ ] Set up error tracking (Sentry - future)

---

## Contacts & References

- **Render Docs**: https://render.com/docs
- **Vector52 API Docs**: https://v52-backend.onrender.com/docs
- **FastAPI**: https://fastapi.tiangolo.com
- **Alchemy Dashboard**: https://dashboard.alchemy.com/apps
