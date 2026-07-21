# UPSC AI Mentor Premium

Independent premium frontend for the existing local FastAPI backend. Phase 1 provides the design system, responsive application shell, routes, query provider, centralized API client, and service health indicator. Feature pages are intentionally placeholders until their controlled phases.

```powershell
Copy-Item .env.example .env
npm install
npm run dev
```

The backend defaults to `http://127.0.0.1:8000`; override it with `VITE_API_BASE_URL`. No secret or admin key belongs in frontend environment files.
