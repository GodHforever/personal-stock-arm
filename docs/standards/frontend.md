# Frontend Design Standards

> Subordinate to: `docs/paradigm/` (development paradigm is supreme authority)

---

## 1. Architecture

### Tech Stack
- React 18 + TypeScript 5 + Vite
- State management: Zustand
- Charts: ECharts (financial chart ecosystem)
- HTTP client: Axios (wrapped in `src/api/`)
- Styling: CSS Modules or Tailwind CSS

### Directory Structure
```
web/
├── src/
│   ├── api/              # API client (all backend calls go through here)
│   │   ├── client.ts     # Axios instance with base URL, interceptors
│   │   ├── stocks.ts     # Stock-related API calls
│   │   ├── analysis.ts   # Analysis API calls
│   │   └── types.ts      # Request/response TypeScript types
│   ├── components/       # Reusable UI components
│   │   ├── StockChart.tsx
│   │   ├── MacroChart.tsx
│   │   └── ...
│   ├── pages/            # Page-level components (route targets)
│   │   ├── Home.tsx
│   │   ├── Watchlist.tsx
│   │   ├── MacroData.tsx
│   │   ├── Earnings.tsx
│   │   └── Settings.tsx
│   ├── stores/           # Zustand state stores
│   │   ├── useStockStore.ts
│   │   └── useSettingsStore.ts
│   ├── hooks/            # Custom React hooks
│   ├── utils/            # Pure utility functions
│   ├── types/            # Shared TypeScript types
│   ├── App.tsx           # Root component + router
│   └── main.tsx          # Entry point
├── public/               # Static assets
├── index.html
├── vite.config.ts
├── tsconfig.json
└── package.json
```

## 2. Design Rules

### Responsive Design
- Must work on both desktop (1280px+) and mobile (360px+) viewports
- PWA-ready: includes `manifest.json`, service worker for offline shell
- Mobile-first breakpoints: base mobile → `md:` tablet → `lg:` desktop

### Theme Support
- Light and dark themes (mandatory for financial tool)
- Theme persisted in localStorage
- CSS custom properties for theme values (colors, backgrounds, borders)

### Charts (ECharts)
- All financial charts use ECharts
- Candlestick charts for K-line data
- Line charts for macro trend data
- Chart components accept data via props, handle their own rendering
- Responsive: charts resize on window resize

### API Communication
- All API calls go through `src/api/client.ts`
- Unified error handling in Axios interceptor
- Loading states managed per-request in components
- SSE for real-time task progress

## 3. State Management

### Zustand Store Conventions
```typescript
// stores/useStockStore.ts
interface StockState {
  watchlists: Watchlist[];
  selectedStock: Stock | null;
  // actions
  fetchWatchlists: () => Promise<void>;
  selectStock: (code: string) => void;
}

export const useStockStore = create<StockState>((set) => ({
  watchlists: [],
  selectedStock: null,
  fetchWatchlists: async () => { ... },
  selectStock: (code) => set({ selectedStock: ... }),
}));
```

- One store per domain (stocks, settings, analysis)
- Actions live inside the store (not as separate functions)
- No component-level state for data shared across pages

## 4. Performance

- React.lazy + Suspense for route-level code splitting
- ECharts loaded on demand (not in initial bundle)
- API responses cached where appropriate (SWR pattern or Zustand with TTL)
- Images and heavy assets lazy-loaded
