# CAMZ React SPA Dashboard

This directory contains the production-grade React 19 single-page dashboard application for CAMZ.

---

## Technology Stack

- **Framework**: React 19 + TypeScript + Vite 8
- **Styling**: TailwindCSS v4 (Vanilla CSS tokens in `src/index.css`)
- **State Management**: Zustand global store (`src/store/useStore.ts`)
- **Icons**: Lucide React Icons
- **Telemetry Charts**: Recharts & Framer Motion
- **Router**: React Router v7

---

## Directory Structure

```
frontend/
├── public/                 # Favicons & static SVGs
├── src/
│   ├── components/         # Layout & reusable components (Sidebar, TopBar, CommandPalette, etc.)
│   ├── pages/              # Route pages (Dashboard, LiveView, Recordings, Settings, Diagnostics, SystemLogs)
│   ├── store/              # Zustand global state store
│   ├── App.tsx             # Main routing & application shell
│   ├── main.tsx            # React entry point
│   └── index.css           # Global CSS variables & Tailwind v4 imports
├── dist/                   # Compiled production bundle (git-ignored)
├── package.json            # NPM dependencies & build scripts
└── vite.config.ts          # Vite build & proxy configuration
```

---

## Development Scripts

```bash
# Install dependencies
npm install

# Start Vite HMR dev server (proxies API requests to http://localhost:8000)
npm run dev

# Compile production bundle to dist/
npm run build
```
