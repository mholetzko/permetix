# Grafana Cloud Setup Guide

This guide walks you through connecting your Fly.io license server to Grafana Cloud for monitoring.

## 🎯 Why Grafana Cloud?

- ✅ Free tier: 10k series, 14 days retention
- ✅ No infrastructure to manage
- ✅ Built-in alerting
- ✅ Accessible from anywhere
- ✅ Pre-built dashboards

## 📋 Setup Steps

### 1. Sign Up for Grafana Cloud

1. Visit: https://grafana.com/auth/sign-up/create-user
2. Fill in your details and create account
3. Verify your email
4. You'll be taken to your Grafana Cloud portal

### 2. Get Your Credentials

From your Grafana Cloud portal:

1. Click on **"My Account"** (top right)
2. Go to **"Stacks"**
3. Click on your stack name
4. Under **"Prometheus"**, click **"Details"** or **"Send Metrics"**
5. Copy these values:
   ```
   Remote Write Endpoint: https://prometheus-prod-XX-XX.grafana.net/api/prom/push
   Username: 123456
   Password/API Key: (click "Generate now" if needed)
   ```

### 3. Configure Prometheus to Push Metrics

Since Prometheus needs to run somewhere to scrape and push metrics, you have options:

#### Option A: Run Prometheus Locally (Easiest for Testing)

1. Update `prometheus-cloud.yml` with your credentials:

```yaml
remote_write:
  - url: https://prometheus-prod-XX-XX.grafana.net/api/prom/push
    basic_auth:
      username: YOUR_USERNAME  # e.g., 123456
      password: YOUR_API_KEY   # The API key you generated
```

2. Run Prometheus locally with Docker:

```bash
docker run -d \
  -p 9090:9090 \
  -v $(pwd)/prometheus-cloud.yml:/etc/prometheus/prometheus.yml \
  --name prometheus-cloud \
  prom/prometheus
```

3. Check it's working: http://localhost:9090/targets

#### Option B: Deploy Prometheus to Fly.io

This keeps everything in the cloud.

1. Create `fly-prometheus.toml`:

```toml
app = 'license-prometheus'
primary_region = 'fra'

[build]
  image = 'prom/prometheus:latest'

[mounts]
  source = 'prometheus_data'
  destination = '/prometheus'

[http_service]
  internal_port = 9090
  force_https = true
  auto_stop_machines = 'stop'
  auto_start_machines = true
  min_machines_running = 0

[[vm]]
  size = 'shared-cpu-1x'
```

2. Deploy:

```bash
# Create volume
flyctl volumes create prometheus_data --size 1 -a license-prometheus

# Deploy
flyctl deploy -c fly-prometheus.toml --dockerfile Dockerfile.prometheus
```

3. Create `Dockerfile.prometheus`:

```dockerfile
FROM prom/prometheus:latest
COPY prometheus-cloud.yml /etc/prometheus/prometheus.yml
```

#### Option C: Use Grafana Agent (Lightweight)

Grafana Agent is lighter than Prometheus and designed for this.

1. Create `grafana-agent.yaml`:

```yaml
server:
  log_level: info

metrics:
  global:
    scrape_interval: 30s
    external_labels:
      cluster: 'fly-io'
      environment: 'production'
  configs:
    - name: default
      remote_write:
        - url: https://prometheus-prod-XX-XX.grafana.net/api/prom/push
          basic_auth:
            username: YOUR_USERNAME
            password: YOUR_API_KEY
      scrape_configs:
        - job_name: 'license-server'
          scheme: https
          static_configs:
            - targets: ['license-server-demo.fly.dev']
          metrics_path: /metrics
```

2. Run with Docker:

```bash
docker run -d \
  -v $(pwd)/grafana-agent.yaml:/etc/agent/agent.yaml \
  grafana/agent:latest \
  --config.file=/etc/agent/agent.yaml
```

### 4. Import the Dashboard to Grafana Cloud

1. Log into your Grafana Cloud instance: https://YOUR_STACK.grafana.net
2. Go to **Dashboards** → **Import**
3. Copy the contents of `grafana/dashboards/license_business_metrics.json`
4. Paste into the "Import via panel json" text box
5. Click **Load**
6. Select your Prometheus datasource
7. Click **Import**

### 5. Verify Data is Flowing

1. In Grafana Cloud, go to **Explore**
2. Select your Prometheus datasource
3. Run a query: `license_borrow_success_total`
4. You should see data!

If not, check:
- Prometheus is running and scraping
- Your credentials are correct
- The remote_write endpoint is reachable

### 6. Set Up Alerts (Optional)

In Grafana Cloud:

1. Go to **Alerting** → **Alert rules**
2. Click **New alert rule**
3. Example alert: "High Overage Rate"

```promql
sum(rate(license_overage_checkouts_total[5m])) / 
(sum(rate(license_borrow_success_total[5m])) + 0.0001) > 0.3
```

4. Set notification channels (email, Slack, PagerDuty, etc.)

## 🎯 Quick Test

Generate some traffic:

```bash
cd clients/python
./run_example.sh
# Choose: 2) Fly.io Production
# Choose: 3) Stress test
```

Within 1-2 minutes, you should see metrics in Grafana Cloud!

## 📊 Available Metrics

All these metrics are available in Grafana Cloud:

```
license_borrow_attempts_total{tool, user}
license_borrow_success_total{tool, user}
license_borrow_failure_total{tool, reason}
license_borrow_duration_seconds{tool}
licenses_borrowed{tool}
licenses_total{tool}
licenses_overage{tool}
licenses_commit{tool}
licenses_max_overage{tool}
licenses_at_max_overage{tool}
license_overage_checkouts_total{tool, user}
```

## 🔍 Useful Queries for Grafana Cloud

### Success Rate
```promql
sum(rate(license_borrow_success_total[5m])) / 
sum(rate(license_borrow_attempts_total[5m]))
```

### Overage Rate
```promql
sum(rate(license_overage_checkouts_total[5m])) / 
(sum(rate(license_borrow_success_total[5m])) + 0.0001)
```

### Active Licenses
```promql
sum(licenses_borrowed)
```

### Top Users
```promql
topk(10, sum by (user) (rate(license_borrow_success_total[5m])))
```

### Cost Calculation (24h)
```promql
sum(increase(license_overage_checkouts_total[24h])) * 100 + 
count(licenses_total) * 1000
```

## 💡 Tips

1. **Tag your metrics** with environment labels to separate prod/dev
2. **Set up alerts** for critical metrics (overage > 30%, success rate < 95%)
3. **Use variables** in dashboards for filtering by tool or user
4. **Create multiple dashboards** for different audiences (ops vs business)
5. **Enable retention** for important metrics (paid plans get longer retention)

## 🆘 Troubleshooting

### No data appearing in Grafana Cloud?

1. Check Prometheus logs: `docker logs prometheus-cloud`
2. Verify remote_write is working: Look for errors in logs
3. Test the endpoint manually:
   ```bash
   curl -u USERNAME:API_KEY \
     -H "Content-Type: application/x-protobuf" \
     https://prometheus-prod-XX-XX.grafana.net/api/prom/push
   ```

### Metrics delayed?

- Free tier has rate limits
- Check your scrape_interval (30s recommended)
- Verify your query time range

### Dashboard not showing data?

- Verify datasource is selected correctly
- Check time range (default is last 6 hours)
- Ensure metrics have the correct labels

## 📚 Resources

- Grafana Cloud Docs: https://grafana.com/docs/grafana-cloud/
- Prometheus Remote Write: https://prometheus.io/docs/prometheus/latest/configuration/configuration/#remote_write
- Grafana Agent: https://grafana.com/docs/agent/latest/
- PromQL Guide: https://prometheus.io/docs/prometheus/latest/querying/basics/

---

**Estimated Setup Time:** 15-20 minutes

**Monthly Cost:** $0 (free tier is sufficient for this demo)

**Maintenance:** Minimal (just keep Prometheus/Agent running)

