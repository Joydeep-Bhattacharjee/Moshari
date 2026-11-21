# PRD — Moshari: Ward-Level Dengue Early Warning

## 1. Problem statement

Dengue hits Dhaka and Chattogram every year. In peak season, hospitals run out of beds, saline and test kits. Mosquito control usually starts after hospital cases have already spiked, when the outbreak is weeks ahead of the response.

Predicting dengue is not a same-day weather problem:

- **Breeding clock.** Rain leaves stagnant water in drains and containers. Aedes eggs take 7–14 days to become adult mosquitoes, then infection and incubation follow. Cases rise 2–4 weeks after the rain.
- **Ward vulnerability.** The same rain hits wards differently. A ward with poor drainage (`water_logging_risk_index`), crowding (`population_density_sqkm`) and weak waste collection (`sanitation_score`) becomes a hotspot faster than its neighbours.

## 2. Goal

Build a working prototype that uses weather data to predict ward-level dengue risk 2–4 weeks ahead, so public health officers can target high-risk wards before outbreaks peak. Treat it as stage 1 of a production system.

## 3. Users

- **City health officers** who plan mosquito spraying and larvicide teams.
- **Public health analysts** who need to trust and check the forecasts.

## 4. User stories

| ID | As a health officer, I want to… |
|---|---|
| U1 | see the dengue risk of a ward 2, 3 or 4 weeks ahead |
| U2 | know which weather and ward factors drive that risk |
| U3 | see which wards need spray teams first |
| U4 | check how reliable the forecasts have been in the past |

## 5. Data

The organizer's dataset: weekly records per ward, with `ward_id`, date, `rainfall_mm`, `avg_temp_C`, `relative_humidity_pct`, `water_logging_risk_index`, `population_density_sqkm`, `sanitation_score` and dengue cases.

## 6. Functional requirements

| ID | Requirement |
|---|---|
| R1 | **Weather data processing:** ingest temperature, humidity and rainfall, and compute multi-week rainfall lags per `ward_id` to match the mosquito breeding cycle. |
| R2 | **Risk prediction engine:** a trained ML or statistical model takes weather inputs and produces predicted cases and a risk category (Low, Medium, High, Critical) for a selected ward and time window. |
| R3 | **Cost and resource efficiency:** run efficiently on local hardware; minimize API calls; keep processing costs low for public health offices. |
| R4 | **User interface:** a working web dashboard that shows predictions and the main weather drivers clearly. |

## 7. Non-functional requirements

| Area | Requirement |
|---|---|
| Setup | a fresh clone launches locally in ≤ 3 minutes using the README commands |
| Speed | fast local inference from a saved model (joblib or pickle) |
| Cost | no unnecessary API calls; any LLM use has token and cost controls |
| Validation | chronological train/test split, never random |
| Transparency | all AI assistants and external APIs listed in the README |

## 8. Acceptance criteria

- Multi-week, ward-level rainfall lag features are computed in code, not hard-coded.
- The model generates predictions and risk tiers dynamically for any selected ward and week.
- The dashboard has clear inputs (ward, week, horizon) and a breakdown of the drivers behind each forecast.
- `ARCHITECTURE.md` (1–2 pages) has a data-flow diagram, the chronological validation split and the reasons for the model choice.
- `ARCHITECTURE.md` documents API-call minimization and cost controls.
- Git history shows commits from every team member across the 24 hours.

## 9. Out of scope

- Live weather APIs
- User accounts and authentication
- Cloud deployment

## 10. Deliverables

1. Public GitHub repository with a dependency file (`requirements.txt` and/or `package.json`)
2. `README.md` with launch commands, AI disclosure and external APIs
3. `ARCHITECTURE.md`
4. Saved model file
5. Uncut demo video (≤ 3 minutes) on localhost, with voiceover and no slides

## 11. Build plan

1. Set up the repository, environment and CI.
2. Audit and validate the dataset.
3. Build weekly per-ward features with multi-week rainfall lags.
4. Define the chronological split and baseline models.
5. Train and select the model; define risk tiers.
6. Save the model; build inference and driver explanations.
7. Build the dashboard.
8. Write README and ARCHITECTURE.md; test a fresh clone.
9. Record the demo video and submit.

## 12. Timeline

Round: 21 November 2:00 PM BST → 22 November 2:00 PM BST.
