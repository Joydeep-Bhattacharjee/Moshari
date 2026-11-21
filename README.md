# Moshari

Ward-level dengue early-warning and risk prioritization dashboard built with **React**, **Vite**, **TypeScript**, and **Tailwind CSS**.

## Features
- **Forecast Overview:** Ward-level risk tiers (`Low`, `Medium`, `High`, `Critical`), predicted case counts, 80% prediction intervals, 26-week rainfall and case timelines, feature contribution bars, and a rainfall multiplier what-if scenario tool.
- **Priority List:** Ranked ward overview with tier counts, a spray-team priority table, a multi-horizon heatmap (`2`, `3`, and `4` weeks ahead), and CSV export (`moshari-priority-...csv`).
- **Validation:** Backtesting overview, prediction error metrics, and outbreak classification breakdown.
- **Bilingual Support:** Switchable between `EN`, `বাংলা`, and `EN + বাংলা`.

## Run Locally
Install dependencies and start the Vite development server:

```bash
npm install
npm run dev