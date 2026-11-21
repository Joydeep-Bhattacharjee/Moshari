# Moshari Architecture

## Overview
**Moshari** is a ward-level dengue early-warning and risk prioritization dashboard built with **React**, **Vite**, **TypeScript**, and **Tailwind CSS**[cite: 1, 2, 5]. It supports ward selection, forecast-origin week selection, forecast horizons, rainfall scenario exploration, priority ranking with CSV export, validation metrics, and bilingual display (`EN`, `বাংলা`, and `EN + বাংলা`)[cite: 1, 5].

## Tech Stack & Project Structure
- **Frontend Framework & Build Tool:** React + TypeScript with Vite (`vite.config.ts`, `tsconfig.json`)[cite: 6].
- **Styling:** Tailwind CSS v4 with custom layout and responsive styles in `src/index.css`[cite: 2].
- **Data Visualization:** Plotly (`src/components/Chart.tsx`) for multi-series time-series timelines[cite: 1, 2].
- **Main Application & Views:**
  - `src/App.tsx`: Manages UI state (`lang`, `ward`, `week`, `horizon`, `multiplier`, `tab`, `notice`), renders the sidebar controls, top bar, KPI cards, timeline, feature contribution bars, what-if scenario comparison, priority list, heatmap, CSV download (`moshari-priority-...csv`), and footer[cite: 1, 5].
  - `src/components/Validation.tsx`: Renders backtesting and model validation views[cite: 1].
  - `src/components/About.tsx`: Renders project overview and guidance views[cite: 1].
  - `src/data.ts`: Holds data types, mock data, backend override hook, bilingual text dictionary, risk tier logic, and forecast/series/validation helpers[cite: 5].

## Data Flow & Backend Integration (`src/data.ts`)
1. **Mock / Stub Layer:** Defines default wards (`MOCK_WARDS`), origin weeks (`MOCK_WEEKS`), baseline case counts (`MOCK_WARD_BASE_CASES`), and driver labels (`DRIVER_NAMES`) when no live backend records are supplied[cite: 5].
2. **Backend Adapter Hook:** `setBackendForecastData(records)` stores `BackendForecastRecord[]` (`ward`, `week`, `horizon`, `pred`, `lo`, `hi`, `actual`, `rain`, `drivers`) in module state (`backendRecords`)[cite: 5].
3. **Lookup & Fallback:** Helper functions (`forecast`, `priority`, `series`, `driverValues`) check `findBackendRecord(ward, week, horizon)` first and fall back to mock calculations when matching records are not present[cite: 5].
4. **Formatting & Risk Tiers:** `tierFor(cases)` classifies risk tiers (`Low`, `Medium`, `High`, `Critical`), `dateLabel` and `addWeeks` format and shift UTC dates, and `label_text` formats strings for `EN`, `বাংলা`, or `EN + বাংলা`[cite: 5].

## Repository Hygiene
- `.gitignore` excludes dependencies (`node_modules/`), build outputs (`dist/`, `build/`), environment files (`.env*`), Vite/TypeScript cache files, and Python cache artifacts (`__pycache__/`, `*.py[cod]`)[cite: 6].