# AI disclosure

## Tools and what they produced

| Tool | Used by | What it produced |
|---|---|---|
| Claude Code (Anthropic, Claude Opus 5.5) | Joydeep | Phase 1: data audit, Python pipeline, tests, the data link to the dashboard, documentation drafts. Phase 2: the decision core in `src/ops/` (forecast window, demand, allocation, routing, simulator, notices, export pack, offline check, fallback chain), its TypeScript port in `src/lib/ops/`, the Operations screens in `src/ops-ui/`, the tests and these docs. |
| Figma Make | Apu | The first version of the Phase 1 React dashboard (layout, components, bilingual text). |
| Claude, Gemini | Apu | Phase 1 dashboard development. |
| ChatGPT, Claude | Ridwan | Project skeleton and data validation. |

## How the work was checked

Phase 2 was built in a supervised session, one module at a time, each committed only when its tests passed. Every number the product shows is produced by code in this repository and covered by tests:

- **Data:** the onsite file is checked cell by cell against the Phase 1 data and its `.xlsx` original; the supply formulas are checked on all 31,320 rows with exact decimal arithmetic (`tests/test_onsite_dataset.py`, `tests/test_formulas.py`).
- **Decisions:** property tests compare the allocation with the scipy HiGHS LP optimum, the routing with scipy's max-flow, and the crew auto-suggest with brute force (`tests/test_allocate.py`, `tests/test_overflow.py`, `tests/test_simulate.py`).
- **Browser vs Python:** the TypeScript port must reproduce six Python scenarios exactly, including every SMS, WhatsApp message and brief (`scripts/test-ops.test.ts`).
- **Offline:** the committed export pack is rebuilt with all sockets blocked and must match byte for byte (`tests/test_offline.py`).
- **Screens:** all six tabs and the Explain drawer were opened in a headless browser with no console errors.

## Decisions taken with the team

Where the PRD and the data disagreed, the evidence was shown to the team before the code changed:

- Extend the Phase 1 React dashboard instead of Streamlit, and reuse the Phase 1 models without retraining.
- Keep the Phase 1 model although it over-forecasts the 2025 peak, and show forecast and actual side by side.
- Round the 10% bed buffer down to whole beds (the PRD rule left routing with almost nothing to move).
- Take the crew effect from the 2- and 3-week Poisson models (the only ones guaranteed to respond in the right direction).

The rounding rule (half down) and the floor-sharing method (Webster) follow from the data and from a counterexample; both are kept as tests. See [ARCHITECTURE.md](ARCHITECTURE.md#12-where-we-differ-from-the-prd-and-why).

## No AI inside the product

Forecasts come from the scikit-learn models trained in Phase 1. Allocation, routing, the simulator and the notices are deterministic code. The product makes no LLM or API call.
