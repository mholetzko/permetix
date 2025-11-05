# Loki Log Filtering Guide

## Real-time Log Filtering Examples

### Filter Debug Logs (Faulty Endpoint)
```
{app="license-server"} |~ "faulty endpoint triggered"
```

### Filter All Errors
```
{app="license-server"} | json | level="ERROR"
```

### Filter 500 Errors Specifically
```
{app="license-server"} |~ "500 response route="
```

### Filter by Route (e.g., /faulty)
```
{app="license-server"} | json | route="/faulty"
```

### Filter Borrow Operations
```
{app="license-server"} |~ "borrow"
```

### Filter by Tool
```
{app="license-server"} | json | tool="ECU Development Suite"
```

### Filter by User
```
{app="license-server"} | json | user="alice"
```

### Combine Filters (Debug + Error)
```
{app="license-server"} |~ "faulty" or level="ERROR"
```

### Time Range Filtering
Use Grafana's time picker, or in LogQL:
```
{app="license-server"} |~ "faulty" [$__range]
```

## Quick Test
1. Click "Trigger Fault (500)" on dashboard
2. In Grafana Explore → Loki:
   - Query: `{app="license-server"} |~ "faulty"`
   - You should see both debug and error log lines

