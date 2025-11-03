# Cloud vs Automotive DevOps Demo

[![GitHub Repository](https://img.shields.io/badge/GitHub-cloud--vs--automotive--demo-blue?logo=github)](https://github.com/mholetzko/cloud-vs-automotive-demo)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

An interactive demonstration showcasing the differences between Automotive (Edge/IoT) and Cloud DevOps observability practices, featuring a license server with a complete observability stack.

## 🎯 Purpose

This demo is designed for automotive companies to understand how cloud DevOps loops work, from commit to deployment to monitoring, and how these practices differ from traditional automotive development workflows.

## ✨ Features

### 📊 Interactive Presentation
- **Reveal.js-based presentation** comparing Automotive vs Cloud DevOps
- Mercedes-Benz styled design
- 15 professional slides covering key differences
- Access at `/presentation`

### 🎫 License Server Demo
- **FastAPI-based license management** system
- Borrow/return licenses with user tracking
- **Budget system** with commit pricing and overage charges
- Real-time status dashboard with SVG pie charts
- Configuration page for managing budgets and pricing

### 📈 Complete Observability Stack
- **Prometheus** - Metrics collection and monitoring
- **Grafana** - Pre-configured dashboards (auto-provisioned)
- **Loki** - Log aggregation and analysis
- **Promtail** - Log shipping agent
- Structured logging with JSON format
- Frontend error tracking

### 🚀 Full DevOps Loop
- **GitHub Actions CI/CD** pipeline
- Automated testing with pytest
- Docker containerization
- Local simulation script (`scripts/local_devops_demo.sh`)

## 🚀 Quick Start

### Local Development

**Prerequisites:** Docker and Docker Compose

```bash
# Clone the repository
git clone https://github.com/mholetzko/cloud-vs-automotive-demo.git
cd cloud-vs-automotive-demo

# Start the full stack
docker compose up --build

# Access the services:
# - License Server:  http://localhost:8000
# - Presentation:    http://localhost:8000/presentation
# - Grafana:         http://localhost:3000 (admin/admin)
# - Prometheus:      http://localhost:9090
```

### Local Demo Script

Simulates the complete CI/CD loop locally:

```bash
./scripts/local_devops_demo.sh
```

This script:
1. Creates/activates Python virtual environment
2. Installs dependencies
3. Runs tests
4. Builds Docker image
5. Starts docker-compose stack
6. Generates test data by hitting endpoints
7. Displays access URLs

## 📱 Application Features

### License Management
- **Borrow licenses** as a user
- **View your borrowed licenses** with one-click return
- **See all borrows** across all users
- **Pool status** with real-time pie charts

### Budget & Pricing
- **Commit quantity** - Fixed budget licenses
- **Max overage** - Out-of-budget allowance
- **Commit price** - Fixed fee for committed licenses
- **Overage price** - Per-license fee for overage usage
- **Cost tracking** - Accumulated overage charges persist over time
- **Configuration page** - Manage budgets and pricing per tool

### Observability
- **Metrics**: Borrow attempts, success/failure rates, duration histograms
- **Logs**: Structured JSON logs with correlation IDs
- **Dashboards**: Pre-configured Grafana dashboards
- **Frontend errors**: Automatic capture and reporting

## 🏗️ Architecture

```
┌─────────────────┐
│   FastAPI App   │
│  (Port 8000)    │
└────────┬────────┘
         │
    ┌────┴────┬──────────┬──────────┐
    │         │          │          │
┌───▼───┐ ┌──▼──┐  ┌────▼────┐ ┌──▼────┐
│ SQLite│ │Prom.│  │ Promtail│ │Grafana│
└───────┘ └──┬──┘  └────┬────┘ └───┬───┘
             │          │           │
             └──────────┴───────────┘
                    │
                ┌───▼───┐
                │  Loki │
                └───────┘
```

## 📊 Observability Stack

### Prometheus Metrics
- `license_borrow_attempts_total{tool}`
- `license_borrow_success_total{tool}`
- `license_borrow_failure_total{tool,reason}`
- `license_borrow_duration_seconds_bucket{tool}`
- `licenses_borrowed{tool}`

### Loki Log Queries

**Backend logs:**
```logql
{job="license-server"} | json | level="info"
{job="license-server"} | json | event="borrow_license"
{job="license-server"} | json | tool="cad_tool"
```

**Frontend errors:**
```logql
{job="license-server"} | json | event="frontend_error"
```

### Grafana Dashboards
Pre-configured dashboard includes:
- License utilization by tool
- Borrow/return rates
- Error rates and types
- Response time percentiles

## 🚢 Deployment to Fly.io

The repository includes `fly.toml` for easy deployment:

```bash
# Install flyctl
curl -L https://fly.io/install.sh | sh

# Login to Fly.io
flyctl auth login

# Launch the app (first time)
flyctl launch --config fly.toml

# Deploy updates
flyctl deploy
```

See [DEPLOYMENT.md](DEPLOYMENT.md) for detailed deployment instructions including Railway.app and DigitalOcean.

## 🧪 Testing

```bash
# Activate virtual environment
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows

# Install dependencies
pip install -r requirements.txt

# Run tests
pytest -v

# Run tests with coverage
pytest --cov=app tests/
```

## 🎓 Key Concepts Explained

The presentation (`/presentation`) covers:

1. **Ownership Model** - Single team vs tiered support
2. **Signal Types** - Continuous time-series vs request-based
3. **Operational Differences** - Shared visibility in cloud
4. **Speed & Certainty** - Minutes vs weeks to triage
5. **Bridging the Gap** - How to bring cloud practices to edge/IoT

## 📁 Project Structure

```
.
├── app/
│   ├── main.py              # FastAPI application
│   ├── db.py                # Database logic
│   └── static/
│       ├── index.html       # Main dashboard
│       ├── presentation.html # Interactive presentation
│       ├── overview.html    # DevOps comparison page
│       ├── config.html      # Budget configuration
│       ├── app.js           # Frontend JavaScript
│       └── style.css        # Mercedes-Benz styling
├── tests/
│   ├── test_licenses.py     # Backend tests
│   └── test_frontend.py     # Frontend tests
├── grafana/
│   ├── dashboards/          # Dashboard JSON files
│   └── provisioning/        # Auto-provisioning configs
├── scripts/
│   └── local_devops_demo.sh # Local CI simulation
├── docker-compose.yml       # Full stack orchestration
├── Dockerfile               # App container
├── fly.toml                 # Fly.io deployment config
└── requirements.txt         # Python dependencies
```

## 🔧 Configuration

Environment variables:
- `LICENSE_DB_PATH` - SQLite database path (default: `/data/licenses.db`)
- `LICENSE_DB_SEED` - Seed default data (default: `true`)

## 📚 API Documentation

Once running, visit:
- **Interactive API docs**: http://localhost:8000/docs
- **OpenAPI spec**: http://localhost:8000/openapi.json

## 🤝 Contributing

This is a demonstration project. Feel free to fork and adapt for your own presentations!

## 📄 License

MIT License - feel free to use this for your own demos and presentations.

## 🙏 Acknowledgments

- Built with FastAPI, Prometheus, Grafana, Loki, and Reveal.js
- Inspired by Mercedes-Benz design principles
- Created to bridge the gap between Automotive and Cloud DevOps practices


