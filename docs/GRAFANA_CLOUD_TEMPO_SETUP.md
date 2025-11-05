# Grafana Cloud Tempo Setup

This guide shows you exactly how to configure Tempo for OpenTelemetry tracing.

## 📍 Your Tempo Configuration

From Grafana Cloud:
- **URL:** `https://tempo-prod-10-prod-eu-west-2.grafana.net/tempo`
- **Username:** `1378044`
- **Password:** Shows "configured" (you need the actual token)

## ⚠️ Important: OTLP Endpoint vs Query Endpoint

The URL you see (`/tempo`) is for **querying** traces, not for **sending** them.

### For OpenTelemetry (Sending Traces):
- **Endpoint:** `https://tempo-prod-10-prod-eu-west-2.grafana.net:443`
- **No `/tempo` path needed** - OTLP uses `/v1/traces` automatically
- **Port:** `443` (HTTPS)

### For Grafana (Querying Traces):
- **URL:** `https://tempo-prod-10-prod-eu-west-2.grafana.net/tempo`
- This is what you configure in Grafana datasource

---

## 🔑 Step 1: Get Your Actual Token

The password shows "configured" but you need the actual token value:

### Option A: Generate New Token (Recommended)
1. In Grafana Cloud → Tempo → Details
2. Look for **"Generate token"** or **"Create token"** button
3. Click it
4. Copy the token (it will look like a long string: `glc_eyJvIjoi...`)

### Option B: View Existing Token
1. Look for **"Show token"** or **"View token"** link
2. Click it to reveal the actual token
3. Copy it

### Option C: Use API Key
1. Go to **My Account** → **API Keys**
2. Create a new API key with Tempo permissions
3. Use that as the token

---

## ✅ Step 2: Configure Fly.io

Use the correct endpoint format:

```bash
# Set OTLP endpoint (no /tempo path, just base URL with port)
flyctl secrets set OTEL_EXPORTER_OTLP_ENDPOINT="https://tempo-prod-10-prod-eu-west-2.grafana.net:443"

# Set authentication (username:token format)
flyctl secrets set OTEL_EXPORTER_OTLP_HEADERS="Authorization: Basic $(echo -n '1378044:YOUR_ACTUAL_TOKEN_HERE' | base64)"
```

**Replace `YOUR_ACTUAL_TOKEN_HERE` with the actual token from Step 1.**

---

## 🔍 Step 3: Verify Configuration

### Check Secrets Are Set:
```bash
flyctl secrets list | grep OTEL
```

You should see:
```
OTEL_EXPORTER_OTLP_ENDPOINT=https://tempo-prod-10-prod-eu-west-2.grafana.net:443
OTEL_EXPORTER_OTLP_HEADERS=Authorization: Basic ...
```

### Restart App:
```bash
flyctl apps restart license-server-demo
```

### Check Logs:
```bash
flyctl logs | grep -i "otel\|trace"
```

Look for:
- ✅ No errors = Good
- ❌ Connection errors = Bad (check endpoint/credentials)
- ❌ Authentication errors = Bad (check token)

---

## 🧪 Step 4: Test It Works

### Make a Request:
```bash
curl -I https://license-server-demo.fly.dev/faulty
```

### Copy Trace ID:
Look for `x-trace-id` in response headers:
```
x-trace-id: 1a55e1ddbbd7da8cc732b16d72b68a5f
```

### Search in Grafana Cloud:
1. Go to: https://matthiasholetzko.grafana.net/explore
2. Select **Tempo** datasource
3. Paste trace ID: `1a55e1ddbbd7da8cc732b16d72b68a5f`
4. Click **Run query**

**If you see the trace, it's working! ✅**

---

## 📊 Configure Grafana Datasource

For **querying** traces in Grafana (not sending), use:

### In Grafana Cloud:
1. Go to **Configuration** → **Data Sources**
2. Find or add **Tempo** datasource
3. Set URL: `https://tempo-prod-10-prod-eu-west-2.grafana.net/tempo`
4. Set authentication:
   - **Basic Auth:** Enabled
   - **User:** `1378044`
   - **Password:** Your actual token (same as above)

---

## 🔐 Authentication Format Reference

### For OpenTelemetry (Sending):
```bash
# Format: username:token base64 encoded
OTEL_EXPORTER_OTLP_HEADERS="Authorization: Basic $(echo -n '1378044:glc_eyJvIjoi...' | base64)"
```

### For Grafana Datasource (Querying):
- **Method:** Basic Auth
- **Username:** `1378044`
- **Password:** `glc_eyJvIjoi...` (your actual token)

---

## 🐛 Common Issues

### Issue 1: "Password shows 'configured'"
**Fix:** You need to generate or view the actual token. Look for "Generate token" or "Show token" button in Grafana Cloud.

### Issue 2: Wrong Endpoint Format
**Wrong:** `https://tempo-prod-10-prod-eu-west-2.grafana.net/tempo`
**Correct:** `https://tempo-prod-10-prod-eu-west-2.grafana.net:443`

The `/tempo` path is for querying, not sending. OTLP automatically appends `/v1/traces`.

### Issue 3: Authentication Fails
**Check:**
- Token is the actual value, not "configured"
- Base64 encoding is correct
- Username matches exactly: `1378044`

### Issue 4: Traces Still Not Found
**After setting secrets:**
1. Wait 30 seconds after restart
2. Make a NEW request (old trace IDs won't work)
3. Search for the NEW trace ID in Grafana Cloud
4. Check time range in Grafana (try "Last 1 hour")

---

## ✅ Complete Configuration Example

```bash
# 1. Get your actual token from Grafana Cloud
# (Replace YOUR_TOKEN with actual token)

# 2. Set OTLP endpoint
flyctl secrets set OTEL_EXPORTER_OTLP_ENDPOINT="https://tempo-prod-10-prod-eu-west-2.grafana.net:443"

# 3. Set authentication
flyctl secrets set OTEL_EXPORTER_OTLP_HEADERS="Authorization: Basic $(echo -n '1378044:YOUR_TOKEN' | base64)"

# 4. Restart
flyctl apps restart license-server-demo

# 5. Test
curl -I https://license-server-demo.fly.dev/faulty
# Copy x-trace-id and search in Grafana Cloud
```

---

## 📚 Related Documentation

- [Quick Start Guide](./QUICKSTART_LOGS_TRACES.md)
- [Troubleshoot Traces](./TROUBLESHOOT_TRACES.md)
- [Find Trace by ID](./FIND_TRACE_BY_ID.md)

---

**Key Point:** The endpoint for **sending** traces is different from the URL for **querying** traces. Make sure you use the correct one!

