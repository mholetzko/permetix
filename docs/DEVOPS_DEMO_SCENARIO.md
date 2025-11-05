# DevOps Observability Demo Scenario
## "The Overage Crisis Journey" - Live Demo Guide

---

## 🎯 **Scenario Overview**

**Story:** A development team starts hitting overage limits on their Vector DaVinci licenses, causing unexpected costs. We'll demonstrate how cloud DevOps observability enables fast detection, diagnosis, and resolution.

**Key Message:** In cloud DevOps, the same team that builds owns the monitoring, sees the same data, and fixes issues in minutes. In automotive (edge/IoT), the journey is longer with many handoffs.

---

## 📋 **Demo Flow (10-15 minutes)**

### **Part 1: Normal Operations** (2 min)
### **Part 2: The Problem Appears** (3 min)
### **Part 3: Detection & Alert** (2 min)
### **Part 4: Investigation** (3 min)
### **Part 5: Decision & Fix** (2 min)
### **Part 6: Verification** (2 min)

---

## 🎬 **PART 1: Normal Operations**

### **What You Do:**
1. Open the dashboard: `https://license-server-demo.fly.dev/dashboard`
2. Show current status - everything green
3. Open Grafana: Show baseline metrics

### **Talking Points:**
- "Here's our license server running in production"
- "We have 6 automotive tools, serving multiple development teams"
- "Right now, everything looks normal"

**Automotive Parallel:** *"In a vehicle, sensors are recording data, but it's stored locally in vehicle memory."*

---

## 🎬 **PART 2: The Problem Appears**

### **What You Do:**
Run stress test to simulate overage:

```bash
cd stress-test
./run_stress_test.sh

# Select:
# - Fly.io Production
# - Heavy Load (20 workers, 100 ops)
# - Full Cycle
# - Vector - DaVinci Configurator SE (has overage)
```

### **Talking Points:**
- "A development team just started a large build job"
- "They're using Vector DaVinci Configurator SE"
- "This tool has 5 commit licenses and 15 overage licenses"
- "Watch what happens..."

**Show in real-time:**
- Stress test output showing borrows
- Some succeed, some go into overage
- Dashboard showing overage charges accumulating

**Automotive Parallel:** *"In automotive, this would be like an error occurring in a vehicle. The ECU logs it, but headquarters doesn't know yet."*

---

## 🎬 **PART 3: Detection & Alert**

### **What You Do:**

1. **Open Grafana Dashboard:**
   - Navigate to: Business Metrics Dashboard
   - Point to: "Overage Rate" panel

2. **Show the metrics:**
   - Overage checkout count spiking
   - Cost increasing
   - Overage rate > 50%

3. **Explain the alert setup** (we'll implement this):
   ```
   ALERT: Overage rate > 30% for 5 minutes
   → Sends Slack/Email notification
   → Includes direct link to Grafana
   → Includes link to logs in Loki
   ```

### **Talking Points:**
- "Within seconds, Prometheus scraped the new metrics"
- "Alert fired automatically when overage hit 30%"
- "The team got a notification with direct links to investigate"
- "**Total time from problem to alert: < 1 minute**"

**Automotive Parallel:** 
*"In automotive:*
- *Vehicle logs the error locally*
- *Waits for telemetry upload (hours/days)*
- *Data aggregated at collector level*
- *Eventually reaches analytics platform*
- *L1 support reviews dashboard*
- *Ticket created for L2*
- *L2 escalates to L3*
- *L3 finally reaches engineering*
- **Total time: Days to weeks***"

---

## 🎬 **PART 4: Investigation**

### **What You Do:**

1. **Click through from alert to Grafana:**
   - Show "License Checkouts by User" panel
   - Identify which user/team is causing overage
   - Show "Overage Checkouts Over Time" - spike visible

2. **Jump to Loki logs:**
   ```logql
   {app="license-server"} 
   | json 
   | tool="Vector - DaVinci Configurator SE" 
   | overage="true"
   ```

3. **Show the logs:**
   - Which users borrowed in overage
   - Exact timestamps
   - Request IDs for tracing

4. **Check application metrics:**
   - `/metrics` endpoint
   - Show: `license_overage_checkouts_total`
   - Show: `licenses_overage{tool="Vector - DaVinci Configurator SE"}`

### **Talking Points:**
- "In one dashboard, I can see the entire picture"
- "Logs, metrics, and business data - all correlated"
- "I can drill down from alert → graph → logs → individual requests"
- "The same team that built this sees the same data"

**Automotive Parallel:**
*"In automotive, the engineer would need to:*
- *Request access to telemetry system*
- *Filter through aggregated data*
- *Uncertainty: 'Which software version? Which variant?'*
- *No direct correlation between logs and error*
- *Multiple tools, multiple teams, multiple handoffs"*

---

## 🎬 **PART 5: Decision & Fix**

### **What You Do:**

1. **Show the cost panel on dashboard:**
   - Total overage cost visible
   - "We're spending $X extra this month"

2. **Make a decision (choose one):**

   **Option A: Increase commit allocation**
   ```bash
   # Navigate to /config
   # Increase DaVinci SE: commit from 5 → 10
   # Show how this reduces overage potential
   ```

   **Option B: Alert the team**
   ```bash
   # Show that we can see which team is over-using
   # In real scenario: automated email to team lead
   # "Your team is using 8 licenses, only 5 are in commit"
   ```

   **Option C: Dynamic scaling (simulation)**
   ```bash
   # Explain: "In a real system, we could auto-scale"
   # "Or auto-reject borrows beyond threshold"
   # "We can implement policy decisions based on metrics"
   ```

3. **Implement the fix:**
   - Go to `/config` page
   - Update DaVinci SE: commit 5 → 10, overage 15 → 10
   - Save config

### **Talking Points:**
- "From alert to fix: **less than 5 minutes**"
- "The same developer who sees the metrics can deploy the fix"
- "No handoffs, no ticket system, no waiting"
- "Decision was data-driven: we saw costs, usage patterns, and trends"

**Automotive Parallel:**
*"In automotive:*
- *Engineering receives ticket (finally)*
- *Requests more data from field*
- *Analysis takes days/weeks*
- *Fix developed and tested*
- *OTA update scheduled*
- *Deployment takes weeks/months*
- **Total time: Weeks to months***"

---

## 🎬 **PART 6: Verification**

### **What You Do:**

1. **Run another stress test:**
   ```bash
   cd stress-test
   ./run_stress_test.sh
   # Same settings as before
   ```

2. **Show in Grafana:**
   - Overage rate now lower
   - More checkouts within commit
   - Cost growth slowed

3. **Show the feedback loop:**
   - "We can see the impact immediately"
   - "Metrics confirm the fix worked"
   - "If it didn't work, we'd know within minutes"

### **Talking Points:**
- "**Complete DevOps cycle: < 10 minutes**"
- "Problem → Detection → Investigation → Fix → Verification"
- "This is the power of cloud DevOps observability"
- "Same team, same data, fast feedback loop"

---

## 📊 **Implementation: What We Need to Add**

To make this demo perfect, let's implement:

### **1. Alerting Rules** ✨ NEW
Create Prometheus alerting rules:
```yaml
# prometheus-alerts.yml
groups:
  - name: license_alerts
    interval: 30s
    rules:
      - alert: HighOverageRate
        expr: |
          (sum(rate(license_overage_checkouts_total[5m])) / 
           sum(rate(license_borrow_success_total[5m]))) > 0.3
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High overage rate detected"
          description: "Overage rate is {{ $value }}% over last 5 minutes"
          dashboard: "https://mholetzko.grafana.net/d/license-business-metrics/license-business-metrics?orgId=1&from=now-6h&to=now&timezone=browser&var-DS_PROMETHEUS=grafanacloud-prom&refresh=10s"
          
      - alert: OverageLimitReached
        expr: licenses_overage >= licenses_max_overage
        labels:
          severity: critical
        annotations:
          summary: "Overage limit reached for {{ $labels.tool }}"
          description: "Cannot borrow more licenses"
```

### **2. Alert Notification Channel** ✨ NEW
- Grafana Alerting (via Grafana Cloud)
- Webhook to Slack (optional)
- Email notifications (optional)

### **3. Enhanced Dashboard Panel** ✨ NEW
Add to Grafana dashboard:
- **Overage Rate Gauge** with threshold markers
- **Cost Burn Rate** ($/hour)
- **Alert Status Panel**

### **4. Demo Steps** 

Follow the manual steps below to run the demo scenario interactively.

---

## 🎯 **Alternative Scenarios**

### **Scenario 2: "The Bug Journey"**

**Problem:** Frontend JavaScript error causing failed license borrows

**Journey:**
1. Users report "can't borrow licenses"
2. Alert fires: `borrow_failures` spike
3. Check Loki logs: see JavaScript errors
4. Check frontend error tracing: see stack trace
5. Correlate with deployment: "was this after the last deploy?"
6. Check Git commit from Grafana annotation
7. Fix and redeploy
8. Verify in metrics

**Time:** Detection to fix: 10-15 minutes

**Automotive Parallel:** Same bug in vehicle software would take weeks to diagnose and months to fix via OTA.

---

### **Scenario 3: "Capacity Planning"**

**Problem:** Should we buy more licenses?

**Journey:**
1. Open Grafana business dashboard
2. Show license utilization over last 30 days
3. Show peak usage times
4. Show overage costs trend
5. Calculate: "Overage costs $5000/month, new licenses cost $3000"
6. **Data-driven decision:** Buy 5 more commit licenses
7. Update config
8. Monitor cost reduction

**Key Point:** Decision made in minutes, based on real data, by the same team.

---

### **Scenario 4: "The Friday Afternoon Crisis"**

**Problem:** All licenses suddenly exhausted at 4:30 PM Friday

**Journey:**
1. Alert fires: `licenses_available` = 0 for all tools
2. Jump to Grafana: see all tools maxed out
3. Check "License Checkouts by User": ONE user has borrowed 50+ licenses
4. Check Loki logs: automated build script gone wild
5. Identify the borrow IDs
6. API call to force-return all licenses from that user
7. Send alert to user's manager
8. Crisis resolved in 5 minutes

**Key Point:** Immediate visibility, direct action, fast resolution.

---

## 💡 **Demo Tips**

### **Setup Before Demo:**
1. Reset database to fresh state
2. Ensure Grafana Cloud is accessible
3. Open all tabs in browser beforehand
4. Test stress test script

### **Practice Timing:**
- Part 1: 2 min
- Part 2: 3 min (stress test running)
- Part 3: 2 min (show alert/metrics)
- Part 4: 3 min (investigate)
- Part 5: 2 min (fix)
- Part 6: 2 min (verify)
- **Total: ~14 minutes**

### **Audience Engagement:**
- Ask: "How long would this take in your current process?"
- Ask: "How many teams would be involved?"
- Ask: "How would you know the fix worked?"

### **Backup Plan:**
If live demo fails:
- Have screenshots ready
- Have pre-recorded video
- Have static dashboard to walk through

---

## 🎬 **Presentation Structure**

### **Slide 1: The Setup**
- "Let's watch a real cloud DevOps cycle"
- "Same team: builds, deploys, monitors, fixes"

### **Slide 2: The Problem** 
- Show stress test causing overage
- "In automotive: this error would be logged locally..."

### **Slide 3: Detection**
- Show alert in < 1 minute
- "In automotive: this would take days to reach HQ..."

### **Slide 4: Investigation**
- Show unified dashboard: metrics + logs + traces
- "In automotive: multiple tools, multiple teams..."

### **Slide 5: Fix**
- Show config change and immediate deployment
- "In automotive: weeks of analysis, months for OTA..."

### **Slide 6: The Key Differences**
Split screen comparison:
```
CLOUD DEVOPS              │  AUTOMOTIVE (EDGE/IOT)
─────────────────────────────────────────────────────
1 minute: Alert fires     │  Hours: Data uploaded
5 minutes: Root cause     │  Days: L1 → L2 → L3
5 minutes: Fix deployed   │  Weeks: Analysis
2 minutes: Verified       │  Months: OTA update
─────────────────────────────────────────────────────
Total: 13 minutes         │  Total: Weeks/Months
1 team                    │  5+ teams
Direct access             │  Multiple handoffs
Immediate feedback        │  Delayed feedback
```

---

## 🚀 **Implementation Priority**

**Must Have (for demo to work):**
1. ✅ Stress test tool (done)
2. ✅ Grafana dashboard (done)
3. ✅ Loki logs (done)
4. ✅ Cost tracking (done)

**Should Have (makes demo better):**
1. ⚠️ Prometheus alerting rules
2. ⚠️ Alert notification setup
3. ⚠️ Enhanced Grafana panels
4. ⚠️ Demo automation script

**Nice to Have (polish):**
1. Frontend error tracing improvements
2. Git commit annotations in Grafana
3. Automated rollback demo
4. Cost prediction panel

---

## 📝 **Script for Presenter**

**Opening:**
"Today I'll show you what cloud DevOps observability looks like in practice. We'll watch a real problem occur, get detected, investigated, and fixed - all in under 15 minutes. Then we'll compare this to the automotive approach."

**During Demo:**
"Notice: I'm the same person who built this, seeing the alert, investigating, and fixing it. No handoffs. No ticket system. No waiting. This is the power of DevOps."

**Closing:**
"The biggest difference isn't the tools - it's the operating model. In cloud, we optimized for speed and direct feedback. In automotive edge/IoT, the constraints are different - but the goal is the same: learn and improve faster."

---

## 🎯 **Key Takeaways for Audience**

1. **Speed**: Cloud DevOps enables detection and fix in minutes
2. **Ownership**: Same team builds, runs, monitors, fixes
3. **Data Access**: Everyone sees the same telemetry
4. **Feedback Loop**: Immediate verification that fix worked
5. **Bridging the Gap**: Automotive can adopt these patterns by implementing observability gateways

---

Want me to implement any of these scenarios? I recommend we start with:
1. The alerting rules
2. A demo automation script
3. Enhanced Grafana panels

Let me know which scenario resonates most with your audience!

