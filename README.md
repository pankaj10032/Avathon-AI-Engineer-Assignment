# Resource Allocation Engine

This project is a field-service-style Resource Allocation Engine built for an Emergency Medical Courier Network, where couriers carrying time-sensitive samples must be matched to hospital pickup requests under skill, capacity, shift, and expiry constraints. It includes a FastAPI backend, a React + Leaflet frontend, and multiple allocation strategies so reviewers can compare speed, optimality, and operational tradeoffs in one place.

## Tech Stack

| Layer | Technology | Purpose |
|---|---|---|
| Backend API | FastAPI | Serves data, allocations, reset, and urgent re-optimization endpoints |
| Optimization | Python, SciPy, NumPy | Implements Greedy, Hungarian, Simulated Annealing, and Hybrid dispatch |
| Data Validation | Pydantic | Enforces courier, request, and assignment schemas |
| Frontend | React, Vite | Interactive dashboard and controls |
| Mapping | React-Leaflet, OpenStreetMap | Live map visualization with no paid API key |
| Testing | Pytest, pytest-cov | Algorithm and API coverage |

## Setup

```bash
cd backend && pip install -r requirements.txt && uvicorn main:app --reload
cd frontend && npm install && npm start
pytest tests/ --cov
```

## Docker

Run the full stack with Docker Compose:

```bash
docker compose up --build
```

This starts:
- FastAPI backend on `http://localhost:8000`
- React frontend on `http://localhost:3000`

If you want to build or run the services individually:

```bash
docker build -f backend/Dockerfile -t resource-allocation-backend .
docker build -f frontend/Dockerfile -t resource-allocation-frontend .
```

Docker uses the same local `data/` files, so no external API keys or paid services are required.

## Folder Structure

```text
Avathon-AI-Engineer-Assignment/
├── backend/
│   ├── app/
│   │   ├── algorithms/
│   │   ├── models/
│   │   ├── utils/
│   │   └── reoptimizer.py
│   ├── main.py
│   └── requirements.txt
├── data/
│   ├── technicians.json
│   ├── repair_requests.json
│   ├── assignments.json
│   └── original/
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   ├── App.jsx
│   │   └── styles.css
│   └── package.json
├── tests/
│   ├── conftest.py
│   ├── test_algorithms.py
│   ├── test_constraints.py
│   └── test_api.py
├── README.md
└── ANALYSIS.md
```

## Screenshots

Add your screenshots in a `screenshots/` folder at the repo root and reference them in this section.

- `screenshots/overview.png` - Main dashboard with map, metrics, and assignments
- `screenshots/greedy-animation.png` - Step-by-step greedy playback
- `screenshots/hungarian-heatmap.png` - Hungarian cost matrix and batch reveal
- `screenshots/comparison.png` - Side-by-side metrics comparison view

## Known Limitations

- Travel time uses a simplified traffic multiplier rather than a live routing API.
- Map coordinates are representative city points, not precise live GPS traces.
- Re-optimization logic preempts only a single assignment and does not yet model route chains or hospital-specific priority policies.
- The Hungarian and Simulated Annealing implementations are tuned for assessment clarity, not production-scale throughput.

## Future Improvements

- Integrate real traffic and route data from a mapping provider.
- Add live GPS tracking and courier status updates over WebSockets.
- Persist allocation history and build operator analytics dashboards.
- Train a machine learning model on historical allocations to improve scoring.
- Add role-based authentication for dispatchers and supervisors.
