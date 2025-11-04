# Vendor Portal Guide

## 🎯 Perfect for Showcasing!

The **Vendor Portal** is now live on your Fly.io deployment and demonstrates the **KEY FEATURE** for automotive software vendors.

## 🚀 Access on Fly.io

Once deployed (in ~3 minutes):
```
https://cloud-vs-automotive-demo.fly.dev/vendor
```

Also accessible from the home page tile: **"Vendor Portal"**

---

## 🏢 What It Shows

### Vendor Perspective (TechVendor Software)

**Scenario**: TechVendor sells automotive software licenses to Acme, Globex, Initech

**Portal Features**:
1. **Customer Management**
   - View all customers (Acme Corporation, Globex Industries, Initech Systems)
   - See CRM IDs (Salesforce/SAP integration)
   - Track active licenses per customer
   - Monitor customer status

2. **License Provisioning**
   - Select customer from dropdown
   - Choose product (ECU Dev Suite, GreenHills Multi, etc.)
   - Configure quantities:
     - Total licenses
     - Commit quantity (fixed budget)
     - Max overage (flexible capacity)
   - Set pricing:
     - Commit fee (monthly fixed cost)
     - Overage per-use fee
   - Link to CRM opportunity ID

3. **Product Catalog**
   - ECU Development Suite
   - GreenHills Multi IDE
   - AUTOSAR Configuration Tool
   - CAN Bus Analyzer Pro
   - Model-Based Design Studio
   - Each with default configurations

---

## 📊 Demo Workflow

### Scenario 1: Provision License to Existing Customer

1. **Open Vendor Portal**:
   ```
   https://cloud-vs-automotive-demo.fly.dev/vendor
   ```

2. **Click "Provision New License to Customer"**

3. **Fill in details**:
   - Customer: BMW AG
   - Product: DaVinci Configurator SE
   - Total: 20 licenses
   - Commit: 5 (fixed budget)
   - Max Overage: 15 (additional capacity)
   - CRM Opportunity: OPP-2025-BMW-001

4. **Click "Provision License"**

5. **Result**:
   - ✅ License package created
   - ✅ Linked to BMW's CRM account
   - ✅ BMW can now use these licenses (in their own server instance)

### Scenario 2: Add New Customer

1. **Click "Add New Customer"**

2. **Fill in details**:
   - Company: Tesla Inc
   - Tenant ID: tesla (lowercase, no spaces)
   - Domain: tesla.com
   - CRM ID: CRM-TESLA-004

3. **Click "Add Customer"**

4. **Result**:
   - ✅ Tesla appears in customer list
   - ✅ Ready to receive license provisioning

### Scenario 3: View Customer Portfolio

1. **Customer table shows**:
   - Company name
   - Tenant ID (for subdomain)
   - CRM ID (Salesforce/SAP link)
   - Active licenses count
   - Status (active/inactive)

---

## 🎨 Key UI Elements

### Customer Table
```
┌──────────────────┬───────────┬─────────────┬─────────────────┬──────────┐
│ Company          │ Tenant ID │ CRM ID      │ Active Licenses │ Status   │
├──────────────────┼───────────┼─────────────┼─────────────────┼──────────┤
│ BMW AG           │ bmw       │ CRM-BMW-001 │ 2 active        │ active   │
│ Mercedes-Benz AG │ mercedes  │ CRM-MB-002  │ 2 active        │ active   │
│ Audi AG          │ audi      │ CRM-AUDI-003│ 2 active        │ active   │
└──────────────────┴───────────┴─────────────┴─────────────────┴──────────┘
```

### Product Catalog
```
DaVinci Configurator SE
  • 20 total (5 commit, 15 overage)
  • €5000 commit + €500 per overage

DaVinci Configurator IDE
  • 10 total (10 commit, 0 overage)
  • €3000 commit

Greenhills Multi 8.2
  • 20 total (5 commit, 15 overage)
  • €8000 commit + €800 per overage

Vector ASAP2 v20
  • 20 total (5 commit, 15 overage)
  • €4000 commit + €400 per overage
```

---

## 🔗 Integration Points

### CRM Integration (Salesforce/SAP)

**Customer Mapping**:
```json
{
  "tenant_id": "bmw",
  "crm_id": "CRM-BMW-001"
}
```

**Opportunity Tracking**:
```json
{
  "package_id": "pkg-bmw-davinci-se-abc123",
  "crm_opportunity_id": "OPP-2025-BMW-001"
}
```

**Billing Export** (future):
```bash
GET /api/vendor/billing?start=2025-11&end=2025-11
→ Returns overage costs per customer, mapped to CRM IDs
```

---

## 🌍 Production Architecture

### Current Demo (Fly.io)
```
https://cloud-vs-automotive-demo.fly.dev/vendor
  → Single server instance
  → Manages multiple customers (BMW, Mercedes, Audi)
  → Demo-friendly (all in one place)
```

### Production Deployment
```
https://vendors.cloudlicenses.com
  → Vendor portal (Vector logs in)

https://bmw.cloudlicenses.com
  → BMW's dedicated server instance
  → Completely isolated
  → Own database, own config, own observability

https://mercedes.cloudlicenses.com
  → Mercedes' dedicated server instance
  → Completely isolated

https://audi.cloudlicenses.com
  → Audi's dedicated server instance
  → Completely isolated
```

**Why Separate Instances?**
- ✅ Complete data isolation
- ✅ Independent scaling
- ✅ Custom configurations per customer
- ✅ Compliance & data residency
- ✅ Each customer has their own:
  - Dashboard
  - Budget config
  - Real-time metrics
  - Observability stack

---

## 📈 Business Value

### For Vendors (Vector, Greenhills)
- ✅ **Self-service provisioning** (no manual setup)
- ✅ **CRM integration** (link licenses to deals)
- ✅ **Usage tracking** (see customer activity)
- ✅ **Flexible pricing** (commit + overage model)
- ✅ **Billing automation** (export costs per customer)

### For Customers (BMW, Mercedes, Audi)
- ✅ **Instant activation** (no waiting for vendor)
- ✅ **Transparent costs** (see commit + overage)
- ✅ **Self-service management** (their own portal)
- ✅ **Full observability** (Prometheus, Grafana, Loki)
- ✅ **Cloud-native** (no on-premise infrastructure)

---

## 🎬 Perfect Demo for Automotive Companies

### Opening Statement
*"Imagine you're Vector, selling software tools to automotive OEMs like BMW and Mercedes. 
Traditionally, this involves manual license files, USB dongles, and complex on-premise 
servers. With our Cloud License Server, you get a **self-service vendor portal** where 
you can provision licenses instantly to your customers, track usage, and automate billing—all 
integrated with your CRM."*

### Live Demo Flow
1. **Show home page** → Click "Vendor Portal" tile
2. **Show customer list** → "Here are Vector's customers: BMW, Mercedes, Audi"
3. **Click "Provision License"** → "Vector wants to provision DaVinci SE to BMW"
4. **Fill in form** → "20 licenses, 5 commit, 15 overage, €5000 + €500 per overage"
5. **Click Provision** → "Done! BMW can now use these licenses"
6. **Explain production** → "In production, BMW would have their own server instance at bmw.cloudlicenses.com"

### Key Talking Points
- ✅ **No manual setup** (vendor clicks, customer gets licenses)
- ✅ **CRM-integrated** (maps to Salesforce opportunities)
- ✅ **Flexible pricing** (commit budget + overage capacity)
- ✅ **Cloud-native** (no on-premise infrastructure for customer)
- ✅ **Fully observable** (Prometheus, Grafana, real-time dashboards)

---

## 📖 Related Documentation

- [Cloud License Protocol](./CLOUD_LICENSE_PROTOCOL.md) - Full protocol specification
- [Multi-Tenant Architecture](./MULTITENANT_ARCHITECTURE.md) - Vendor-customer architecture
- [License Theft Prevention](./LICENSE_THEFT_PREVENTION.md) - Security model

---

## ✅ What's Live on Fly.io

After deployment (~3 minutes):

**Vendor Portal**:
- ✅ `/vendor` - Full vendor portal UI
- ✅ Customer management (view, add)
- ✅ License provisioning workflow
- ✅ Product catalog

**API Endpoints**:
- ✅ `GET /api/vendor/customers` - List customers
- ✅ `POST /api/vendor/customers` - Add customer
- ✅ `POST /api/vendor/provision` - Provision license

**Integration**:
- ✅ Multi-tenant database schema
- ✅ Tenant isolation (tenant_id scoping)
- ✅ CRM ID mapping
- ✅ Package tracking

---

## 🚀 This Is The Key Feature!

The vendor portal is **the missing piece** that shows how the entire ecosystem works:

1. **Vendor** (Vector) provisions licenses via portal
2. **Customer** (BMW) receives licenses in their instance
3. **Applications** (DaVinci) consume licenses via API
4. **Observability** (Prometheus/Grafana) tracks everything

**Perfect for automotive software vendors!** 🎉

