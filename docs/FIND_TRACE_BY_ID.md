# How to Find a Trace by Trace ID

When you get an error response with a trace ID in the header, here's how to find it in Grafana.

## 🔍 Your Trace ID

From your error response:
```
x-trace-id: a8611dfc2f7d408fe9519c845f66e19a
x-request-id: debe3916
```

## 📍 Method 1: Grafana Tempo Explore (Easiest)

### Step 1: Open Grafana Explore
1. Go to your Grafana instance:
   - **Local:** http://localhost:3000
   - **Grafana Cloud:** https://matthiasholetzko.grafana.net

2. Click **Explore** (compass icon) in the left sidebar

### Step 2: Select Tempo Datasource
- In the dropdown at the top, select **Tempo**

### Step 3: Search by Trace ID
- In the search box, paste your trace ID:
  ```
  a8611dfc2f7d408fe9519c845f66e19a
  ```
- Click **"Run query"** or press Enter

### Step 4: View Trace Details
- You'll see the full trace with all spans
- Click on any span to see:
  - Request duration
  - Route path (`/faulty`)
  - Status code (500)
  - Request ID (`debe3916`)
  - All metadata

---

## 📍 Method 2: Direct URL (Fastest)

### For Local Grafana:
```
http://localhost:3000/explore?orgId=1&left=%5B%22now-1h%22,%22now%22,%22Tempo%22,%7B%22query%22:%22a8611dfc2f7d408fe9519c845f66e19a%22%7D%5D
```

### For Grafana Cloud:
Replace `matthiasholetzko` with your instance:
```
https://matthiasholetzko.grafana.net/explore?orgId=1&left=%5B%22now-1h%22,%22now%22,%22Tempo%22,%7B%22query%22:%22a8611dfc2f7d408fe9519c845f66e19a%22%7D%5D
```

**Or manually:**
1. Go to Explore
2. Select Tempo
3. Paste: `a8611dfc2f7d408fe9519c845f66e19a`

---

## 📊 What You'll See in the Trace

### Trace View Shows:
- **Service:** `license-server`
- **Operation:** `GET /faulty`
- **Duration:** How long the request took
- **Status:** 500 (error)
- **Spans:** All sub-operations (database queries, etc.)

### Span Details:
- **Attributes:** 
  - `http.method`: GET
  - `http.route`: /faulty
  - `http.status_code`: 500
  - `request_id`: debe3916
- **Tags:** All metadata from the request

---

## 🔗 Correlate with Logs

### Option 1: From Trace View
1. Click on the error span (status 500)
2. Click the **"Logs"** button (top right)
3. You'll see all logs related to this trace:
   ```
   {app="license-server"} |= "trace_id=a8611dfc2f7d408fe9519c845f66e19a"
   ```

### Option 2: Direct Log Query
1. Go to **Explore** → Select **Loki** datasource
2. Run query:
   ```logql
   {app="license-server"} |= "trace_id=a8611dfc2f7d408fe9519c845f66e19a"
   ```
   Or using request_id:
   ```logql
   {app="license-server"} |= "request_id=debe3916"
   ```

### What Logs Show:
- Request details: route, method, status
- Error message (if logged)
- Duration
- Full stack trace (if available)

---

## 🎯 Quick Steps Summary

1. **Copy trace ID** from response header: `a8611dfc2f7d408fe9519c845f66e19a`
2. **Open Grafana** → Explore → Tempo
3. **Paste trace ID** in search box
4. **Click Run** → See full trace
5. **Click "Logs"** button → See related logs

---

## 🐛 Troubleshooting

### Trace Not Found?

**1. Check if Tempo is receiving traces:**
```bash
# Local
docker-compose logs tempo | tail -20

# Fly.io - check if OTEL secrets are set
flyctl secrets list | grep OTEL
```

**2. Verify trace ID format:**
- Should be 32-character hex string (no dashes)
- Example: `a8611dfc2f7d408fe9519c845f66e19a` ✅
- Not: `a8611dfc-2f7d-408f-e951-9c845f66e19a` ❌

**3. Check time range:**
- Traces might be in a different time window
- Adjust time range in Grafana (top right)
- Try "Last 1 hour" or "Last 6 hours"

**4. Verify Tempo datasource:**
- Check Tempo is configured in Grafana
- Local: Should point to `http://tempo:3200`
- Cloud: Should point to your Grafana Cloud Tempo endpoint

---

## 💡 Pro Tips

### Tip 1: Use Request ID Too
If trace isn't found, search by request_id in logs:
```logql
{app="license-server"} |= "request_id=debe3916"
```

### Tip 2: Browser DevTools
- Check Network tab → Response Headers
- Look for `x-trace-id` and `x-request-id`
- Copy and paste into Grafana

### Tip 3: Dashboard Integration
- The license ops dashboard has a "Request Traces" panel
- Shows recent traces automatically
- Click any trace to see details

### Tip 4: Alert on Trace IDs
Set up alerts that include trace IDs in notifications:
```
Alert: High error rate
When: rate(license_http_500_total[5m]) > 5
Include: trace_id from response headers
```

---

## 📚 Related Documentation

- [Quick Start Guide](./QUICKSTART_LOGS_TRACES.md) - Setup logs and traces
- [Loki Log Filtering](./LOKI_LOG_FILTERING.md) - Query logs effectively
- [Grafana Tempo Docs](https://grafana.com/docs/tempo/latest/)

---

**That's it!** You can now find any trace by its trace ID. 🎉

