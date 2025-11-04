# Real-Time Dashboard

## ⚡ Overview

The real-time dashboard provides **zero-lag, live monitoring** of license server activity using Server-Sent Events (SSE). Perfect for live demos and immediate problem investigation.

---

## 🎯 **Architecture**

```
┌──────────────────────────────────────────────────────────┐
│  FastAPI Backend                                         │
│                                                          │
│  On every request:                                       │
│  ├─ Record event in memory buffer (6h retention)        │
│  ├─ Update Prometheus metrics (for long-term storage)   │
│  └─ Stream via SSE to connected clients (1s interval)   │
└──────────────────────────────────────────────────────────┘
                          │
                          ├──→ Browser (Chart.js)
                          │    └─ Real-time charts
                          │    └─ Live metrics cards
                          │    └─ < 1 second latency
                          │
                          └──→ Prometheus (5s scrape)
                               └─ Grafana Cloud
                               └─ Historical analysis
```

---

## 📊 **What It Shows**

### **Metric Cards (Updated every second)**
1. **Borrows/Minute** - Current borrow rate with pulse animation
2. **Overage Rate** - Percentage with color-coded warnings (>15% yellow, >30% red)
3. **Returns/Minute** - Return rate
4. **Failures/Minute** - Failed borrow attempts
5. **Active Licenses** - Total borrowed across all tools
6. **Buffer Size** - Total events stored (6-hour window)

### **Charts (Configurable time window)**
1. **License Borrows** - Line chart of borrow rate
2. **Overage Checkouts** - Line chart of overage events
3. **License Utilization by Tool** - Stacked horizontal bar chart showing:
   - In Commit (blue)
   - In Overage (orange)
   - Available (grey)

**Time Range Options:**
- 1 minute (60 seconds)
- 5 minutes (300 seconds)
- 10 minutes (600 seconds)
- **30 minutes (default)** (1800 seconds)
- 1 hour (3600 seconds)
- 3 hours (10800 seconds)
- 6 hours (21600 seconds - full buffer)

---

## 🚀 **Usage**

### **Access the Dashboard**
```
http://localhost:8000/realtime
https://license-server-demo.fly.dev/realtime
```

### **Run a Stress Test to See It in Action**
```bash
cd stress-test
./run_stress_test.sh

# Select:
# - Target: Fly.io Production
# - Profile: Medium Load
# - Tool: Vector - DaVinci Configurator SE

# Then watch the real-time dashboard!
```

---

## 🔧 **Technical Details**

### **Backend Components**

1. **RealtimeMetricsBuffer Class** (`app/main.py`)
   - In-memory deque storage
   - Automatic 6-hour retention cleanup
   - Thread-safe operations
   - Stores: borrows, returns, failures

2. **SSE Endpoint** (`/realtime/stream`)
   - Streams JSON events every 1 second
   - Auto-reconnects on disconnect
   - Includes:
     - Current status for all tools
     - Recent events (last 60s)
     - Calculated rates
     - Buffer statistics

3. **Stats Endpoint** (`/realtime/stats`)
   - HTTP GET for current buffer state
   - Useful for debugging

### **Frontend Components**

1. **Chart.js Integration** (`app/static/realtime.js`)
   - Three real-time charts
   - Smooth animations (300ms)
   - Rolling 60-second window
   - No animation on updates for smoothness

2. **SSE Client**
   - EventSource API
   - Auto-reconnection with exponential backoff
   - Max 10 reconnection attempts
   - Connection status indicator

3. **Visual Feedback**
   - Pulse animations on activity
   - Color-coded warnings
   - Real-time connection status
   - Activity indicators on metric cards

---

## 💾 **Storage & Performance**

### **Memory Usage**
- **Borrows**: Max 100,000 events (~28/sec for 6 hours)
- **Returns**: Max 100,000 events
- **Failures**: Max 10,000 events
- **Total**: ~210,000 events max ≈ **5-10 MB RAM**

### **Cleanup Strategy**
- Automatic cleanup on every event addition
- Removes events older than 6 hours
- O(1) for adds, O(n) for cleanup (but infrequent)

### **Network Traffic**
- **SSE stream**: ~1 KB/second per connected client
- **1 hour**: ~3.6 MB per client
- **Minimal overhead** compared to polling

---

## 🎯 **Use Cases**

### **1. Live Demo** ⭐
Show real-time DevOps in action:
- Run stress test
- Watch metrics update instantly
- Demonstrate zero-lag observability

### **2. Problem Investigation**
- Immediate visibility into current activity
- Last 6 hours of data for troubleshooting
- No need to wait for Prometheus scrape

### **3. Overage Monitoring**
- Real-time overage rate tracking
- Instant alerts (visual color changes)
- Cost implications visible immediately

### **4. DevOps Comparison**
- **Cloud**: Real-time dashboard (< 1s lag)
- **Automotive**: 30s Prometheus scrape + Grafana
- Perfect for showing the contrast!

---

## 🔄 **Comparison: Real-Time vs Prometheus**

| Feature | Real-Time Dashboard | Prometheus + Grafana |
|---------|-------------------|---------------------|
| **Latency** | < 1 second | 5-30 seconds |
| **Retention** | 6 hours | Unlimited |
| **Storage** | In-memory (~10MB) | Disk-based |
| **Use Case** | Live demos, immediate investigation | Long-term analysis, alerting |
| **Best For** | Real-time visibility | Historical trends |
| **Cost** | Free (included) | Grafana Cloud fees |

**Recommendation:** Use BOTH!
- Real-time for live demos and immediate visibility
- Prometheus/Grafana for long-term storage and analysis

---

## 🐛 **Troubleshooting**

### **Connection Keeps Dropping**
```bash
# Check if EventSource is supported
console.log('EventSource' in window);

# Check browser console for errors
# Look for: "SSE connection error"
```

### **No Data Showing**
```bash
# Test the SSE endpoint directly
curl -N http://localhost:8000/realtime/stream

# Test the stats endpoint
curl http://localhost:8000/realtime/stats
```

### **High Memory Usage**
```bash
# Check buffer stats
curl http://localhost:8000/realtime/stats | jq .total_events

# If > 200,000, events are not being cleaned up
# Check server logs for errors
```

---

## 🎬 **Demo Script**

### **Setup (before presentation)**
1. Open real-time dashboard in browser
2. Open Grafana in another tab
3. Have stress test ready

### **During Demo**
1. **Show baseline** - "Everything is normal, zero activity"
2. **Start stress test** - "Let's simulate a dev team checking out licenses"
3. **Watch real-time** - "Notice how the metrics update instantly"
4. **Point out overage** - "Some checkouts are going into overage (red)"
5. **Compare with Grafana** - "This same data is also in Grafana for long-term analysis"
6. **Highlight speed** - "From event to visibility: less than 1 second"

### **Key Talking Points**
- "This is true real-time - no polling, no delay"
- "Perfect for immediate problem detection"
- "In automotive edge/IoT, this data would take hours to reach you"
- "Cloud DevOps enables this kind of instant feedback"

---

## 📈 **Future Enhancements** (Optional)

1. **Alert Annotations** - Show when alerts fired
2. **Event Log Table** - Scrolling list of recent events
3. **User Filtering** - Filter metrics by user
4. **Tool Filtering** - Focus on specific tools
5. **Export to CSV** - Download buffer data
6. **WebSocket Upgrade** - Even lower latency (< 100ms)

---

## ✅ **Summary**

The real-time dashboard provides:
- ✅ **Zero-lag visibility** into license server activity
- ✅ **6-hour retention** for immediate problem investigation
- ✅ **Beautiful visualizations** with Chart.js
- ✅ **Low overhead** (~10MB RAM, minimal network)
- ✅ **Perfect for demos** showing cloud DevOps speed

**Best used alongside Prometheus/Grafana for a complete observability solution!**

---

## 🔗 **Related Docs**

- `REALTIME_METRICS_GUIDE.md` - Implementation details and alternatives
- `DEVOPS_DEMO_SCENARIO.md` - Full demo script using real-time dashboard
- `GRAFANA_CLOUD_SETUP.md` - Long-term metrics setup

---

**Access:** [http://localhost:8000/realtime](http://localhost:8000/realtime) or [https://license-server-demo.fly.dev/realtime](https://license-server-demo.fly.dev/realtime)

