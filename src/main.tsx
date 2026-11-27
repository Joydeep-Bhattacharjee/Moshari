import React from 'react'
import ReactDOM from 'react-dom/client'
// Fonts are bundled locally so the dashboard makes no external requests.
import '@fontsource/inter/400.css'
import '@fontsource/inter/500.css'
import '@fontsource/inter/600.css'
import '@fontsource/inter/700.css'
import '@fontsource/inter/800.css'
import '@fontsource/dm-sans/400.css'
import '@fontsource/dm-sans/500.css'
import '@fontsource/dm-sans/600.css'
import '@fontsource/dm-sans/700.css'
import '@fontsource/noto-sans-bengali/400.css'
import '@fontsource/noto-sans-bengali/500.css'
import '@fontsource/noto-sans-bengali/600.css'
import App from './App'
import { initData, type Dashboard, type ValidationFile } from './data'
import type { OpsConfig, OpsForecasts } from './lib/ops/types.ts'
import { OpsApp } from './ops-ui/OpsApp'
import './index.css'

// Two apps share the site: #/forecast is the Phase 1 forecast dashboard, anything else
// is the Phase 2 Operations app. Switching between them reloads to load the right data.
type Route = 'forecast' | 'ops'
const routeOf = (hash: string): Route => (hash.startsWith('#/forecast') ? 'forecast' : 'ops')
const route = routeOf(window.location.hash)
window.addEventListener('hashchange', () => {
  if (routeOf(window.location.hash) !== route) window.location.reload()
})

async function fetchJson<T>(path: string): Promise<T> {
  const response = await fetch(`${import.meta.env.BASE_URL}${path}`)
  if (!response.ok) throw new Error(`${path}: HTTP ${response.status}`)
  return (await response.json()) as T
}

const root = ReactDOM.createRoot(document.getElementById('root')!)

function showError(error: unknown, command: string) {
  root.render(
    <div className="error-notice" style={{ margin: 40 }}>
      Could not load the dashboard data ({String(error)}). Run <code>{command}</code> and refresh the page.
    </div>,
  )
}

if (route === 'forecast') {
  Promise.all([fetchJson<Dashboard>('data/dashboard.json'), fetchJson<ValidationFile>('data/validation.json')])
    .then(([dashboard, validation]) => {
      initData(dashboard, validation)
      root.render(
        <React.StrictMode>
          <App />
        </React.StrictMode>,
      )
    })
    .catch((error: unknown) => showError(error, 'python -m src.export'))
} else {
  Promise.all([fetchJson<OpsConfig>('data/ops/config.json'), fetchJson<OpsForecasts>('data/ops/forecasts.json')])
    .then(([config, forecasts]) => {
      root.render(
        <React.StrictMode>
          <OpsApp config={config} forecasts={forecasts} />
        </React.StrictMode>,
      )
    })
    .catch((error: unknown) => showError(error, 'python -m src.ops.ui_export'))
}
