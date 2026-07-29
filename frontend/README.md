# Transkrybe.ai — frontend

React 19 + Vite single-page app. It talks to the FastAPI backend documented in
the [main README](../README.md); start that first or the app has nothing to call.

```bash
npm install
npm run dev        # http://localhost:5173
```

`vite.config.js` proxies `/api/*` to `http://localhost:8000`, so there is no CORS
setup in development. In production the backend serves the built bundle from the
same origin, so the same relative `/api` base URL works unchanged.

## Scripts

| Command | Purpose |
|---|---|
| `npm run dev` | Dev server with HMR on port 5173 |
| `npm run build` | Production bundle → `dist/` |
| `npm run preview` | Serve the built bundle locally |
| `npm run lint` | ESLint |

## Layout

```text
src/
  api/            axios wrappers, one per endpoint group; baseURL '/api'
  hooks/          React Query hooks for server data
  store/          Zustand store — all client state
  components/     one directory per tab, plus layout/ modals/ shared/
  styles/         plain CSS; design tokens in variables.css
  featureFlags.js hard UI toggles for not-yet-ready features
  App.jsx         tab routing via the Zustand activeTab field
```

## Conventions

- **State:** Zustand for client state, React Query for server data. No Redux,
  no Context providers for app state.
- **No router.** The active tab is a store field, not a URL.
- **Plain CSS only** — no Tailwind, no component library.
- **Sanitize HTML.** Anything from `/api/colorize` goes through DOMPurify before
  `dangerouslySetInnerHTML`.
