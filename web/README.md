# Home Finances web app

The frontend: Svelte 5 + TypeScript, built by Vite, charts drawn as SVG with
d3-scale/d3-shape. It is a pure HTTP client of the FastAPI backend, which it
reaches under `/api` on its own origin (Vite's proxy in development, nginx in
Docker), so the browser never needs CORS.

    npm install
    npm run dev        # http://localhost:5173, /api forwarded to http://localhost:8000
    npm test           # vitest: the pure helpers in src/lib
    npm run check      # svelte-check + TypeScript
    npm run build      # static files in dist/

`API_PROXY_TARGET` changes where the dev server forwards `/api`.

Layout:

- `src/lib/`: pure helpers (money, dates, filtering, targets, shaping per view) with `*.test.ts` beside them, the session/API client (`session.svelte.ts`) and the hash router.
- `src/lib/ui/`: the shared look (Card, Kpi, Tabs, Segmented, FilterRow, Callout, Lede, Notices).
- `src/lib/charts/`: the chart primitives and palette.
- `src/pages/`: one file per page; `src/sections/`: the tabs and cards they're made of.
