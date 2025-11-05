# Quick Start: Logs & Traces

This guide shows you how to start collecting logs and traces in 5 minutes.

## 🚀 Option 1: Local Development (Docker Compose)

### Start Everything

```bash
# Start all services (Loki, Tempo, Promtail, Grafana)
docker-compose up -d

# Check all services are running
docker-compose ps

# View logs
docker-compose logs -f api
```

### Verify It's Working

**1. Check Logs in Grafana:**
- Open: http://localhost:3000 (admin/admin)
- Go to **Explore** → Select **Loki** datasource
- Run query: `{job="docker-logs"}`
- You should see logs from your app!

**2. Check Traces in Grafana:**
- Go to **Explore** → Select **Tempo** datasource
- Run query: `{ service.name = "license-server" }`
- You should see traces!

**3. Generate Some Traffic:**
```bash
# Make some requests
curl http://localhost:8000/licenses/status
curl http://localhost:8000/licenses/borrow -X POST -H "Content-Type: application/json" -d '{"tool":"ECU Development Suite","user":"test"}'
```

**4. Check Logs Endpoint:**
```bash
# View recent logs via HTTP
curl http://localhost:8000/logs?limit=10
```

✅ **That's it!** Logs and traces are automatically collected locally.

---

## 🌐 Option 2: Fly.io Production (Grafana Cloud)

### Step 1: Get Grafana Cloud Credentials

**For Loki (Logs):**
1. Go to: https://grafana.com → **My Account** → **Stacks**
2. Click your stack
3. Under **Loki**, click **"Details"** or **"Send Logs"**
4. Copy:
   - Push URL: `https://logs-prod-XX-XX.grafana.net/loki/api/v1/push`
   - Username: `123456`
   - API Key: (click "Generate now" if needed)

**For Tempo (Traces):**
1. In the same stack, under **Tempo**, click **"Details"**
2. Copy:
   - OTLP Endpoint: `https://tempo-us-central1-XX.grafana.net:443`
   - Basic Auth: `username:token` format

### Step 2: Configure Fly.io Secrets

```bash
# Set Loki credentials
flyctl secrets set LOKI_URL="https://logs-prod-XX-XX.grafana.net/loki/api/v1/push"
flyctl secrets set LOKI_AUTH="123456:your-loki-api-key"

# Set Tempo credentials
flyctl secrets set OTEL_EXPORTER_OTLP_ENDPOINT="https://tempo-us-central1-XX.grafana.net:443"
flyctl secrets set OTEL_EXPORTER_OTLP_HEADERS="Authorization: Basic $(echo -n 'username:token' | base64)"
```

**Alternative (using Bearer token for Tempo):**
```bash
flyctl secrets set OTEL_EXPORTER_OTLP_HEADERS="Authorization: Bearer your-tempo-token"
```

### Step 3: Restart App

```bash
# Restart to pick up new secrets
flyctl apps restart license-server-demo

# Or redeploy
flyctl deploy
```

### Step 4: Verify It's Working

**1. Check App Logs:**
```bash
# View app logs to see if Loki/Tempo handlers are configured
flyctl logs | grep -i "loki\|tempo\|trace"
```

You should see:
```
INFO license-server Loki push handler configured
```

**2. Check Logs in Grafana Cloud:**
- Go to: https://matthiasholetzko.grafana.net/explore
- Select **Loki** datasource
- Run query: `{app="license-server"}`
- Make some requests to generate logs:
  ```bash
  curl https://license-server-demo.fly.dev/licenses/status
  ```

**3. Check Traces in Grafana Cloud:**
- Go to: https://matthiasholetzko.grafana.net/explore
- Select **Tempo** datasource
- Run query: `{ service.name = "license-server" }`
- You should see traces!

**4. Test Logs Endpoint:**
```bash
# View recent logs via HTTP
curl https://license-server-demo.fly.dev/logs?limit=10
```

---

## ✅ Quick Verification Checklist

### Local Development
- [ ] `docker-compose up -d` running
- [ ] Grafana accessible at http://localhost:3000
- [ ] Loki datasource working (can query logs)
- [ ] Tempo datasource working (can query traces)
- [ ] App logs visible in Grafana Explore

### Fly.io Production
- [ ] `LOKI_URL` and `LOKI_AUTH` set in Fly.io
- [ ] `OTEL_EXPORTER_OTLP_ENDPOINT` and `OTEL_EXPORTER_OTLP_HEADERS` set
- [ ] App restarted after setting secrets
- [ ] Logs visible in Grafana Cloud
- [ ] Traces visible in Grafana Cloud

---

## 🐛 Troubleshooting

### No Logs Appearing?

**Local:**
```bash
# Check Promtail is running
docker-compose ps promtail

# Check Promtail logs
docker-compose logs promtail

# Check Loki is receiving logs
docker-compose logs loki | tail -20
```

**Fly.io:**
```bash
# Check app logs
flyctl logs | grep -i "loki"

# Verify secrets are set
flyctl secrets list

# Test /logs endpoint
curl https://license-server-demo.fly.dev/logs
```

### No Traces Appearing?

**Local:**
```bash
# Check Tempo is running
docker-compose ps tempo

# Check Tempo logs
docker-compose logs tempo

# Verify app is sending traces
docker-compose logs api | grep -i "trace"
```

**Fly.io:**
```bash
# Verify OTEL secrets are set
flyctl secrets list | grep OTEL

# Check app logs for trace errors
flyctl logs | grep -i "trace\|otel"
```

### Common Issues

**1. "Loki push handler configured" but no logs:**
- Check Grafana Cloud Loki credentials are correct
- Verify API key hasn't expired
- Check network connectivity from Fly.io

**2. Traces not showing:**
- Verify Tempo endpoint URL is correct
- Check authentication headers format
- Ensure Tempo datasource is configured in Grafana Cloud

**3. Local docker-compose not working:**
- Make sure ports aren't already in use
- Check `docker-compose logs` for errors
- Try `docker-compose down && docker-compose up -d`

---

## 📊 What You'll See

### Logs in Grafana
- **Query:** `{app="license-server"}`
- Shows: All application logs with timestamps, levels, messages
- Includes: `request_id` and `trace_id` for correlation

### Traces in Grafana
- **Query:** `{ service.name = "license-server" }`
- Shows: Request traces with spans showing:
  - HTTP request duration
  - Route paths
  - Status codes
  - Trace IDs for correlation

### Correlation
- Click on a trace span → **"Logs"** button
- See all logs related to that trace
- All connected via `trace_id`

---

## 🎯 Next Steps

1. **View in Dashboard:** Open the license ops dashboard to see integrated logs, traces, and metrics
2. **Set Up Alerts:** Configure alerts based on log patterns or trace errors
3. **Explore Correlation:** Use trace-to-logs correlation to debug issues
4. **Read Documentation:**
   - [Loki Push Setup](./LOKI_PUSH_SETUP.md) - Detailed Loki configuration
   - [Log Scraping Options](./LOG_SCRAPING_OPTIONS.md) - All log collection methods

---

**That's it!** You're now collecting logs and traces. 🎉

