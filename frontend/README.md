# CrisisSentinel frontend

React 19 + Vite. No UI framework; the design system lives in two CSS files (`src/index.css` tokens and base, `src/App.css` components).

```bash
npm install
npm run dev      # http://localhost:5173, proxies /api to http://localhost:8000
npm run lint
npm test         # 12 component tests against payloads produced by the real backend
npm run build
```

Set `VITE_API_URL` (see `.env.example`) when the backend is hosted on a different origin.

Structure: `src/api.js` (all network access, including the SSE stream), `src/format.js`, `src/constants.js`, `src/components/*`. The UI never invents numbers: every figure is rendered from an API field, and degraded stages are labelled.
