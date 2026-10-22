# CrisisSentinel API Contract

Base URL: `http://localhost:8000`

---

## 1. Disruption Scan & Exposure Analysis

Runs live web research, deterministic ERP queries, and AI strategic planning.

- **Method**: `POST`
- **Path**: `/api/disruption/scan`
- **Headers**: `Content-Type: application/json`

### Request Body:

```json
{
  "query": "Taiwan semiconductor supply chain disruption 2026"
}
```
