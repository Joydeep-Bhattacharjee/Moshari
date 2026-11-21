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
import './index.css'

async function fetchJson<T>(path: string): Promise<T> {
  const response = await fetch(`${import.meta.env.BASE_URL}${path}`)
  if (!response.ok) throw new Error(`${path}: HTTP ${response.status}`)
  return (await response.json()) as T
}

const root = ReactDOM.createRoot(document.getElementById('root')!)

Promise.all([fetchJson<Dashboard>('data/dashboard.json'), fetchJson<ValidationFile>('data/validation.json')])
  .then(([dashboard, validation]) => {
    initData(dashboard, validation)
    root.render(
      <React.StrictMode>
        <App />
      </React.StrictMode>,
    )
  })
  .catch((error: unknown) => {
    root.render(
      <div className="error-notice" style={{ margin: 40 }}>
        Could not load the forecast data ({String(error)}). Run <code>python -m src.export</code> and
        refresh the page.
      </div>,
    )
  })
