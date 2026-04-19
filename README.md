# Cairo Fire Station Simulation Platform

Interactive tool for evaluating and optimizing fire station placement in Cairo using real OpenStreetMap road data (87k intersections, 243k edges).

## Quick Start

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python app.py
```

The app opens at **http://127.0.0.1:5000**.

## Deployment

Deployment to Render.com was attempted but failed: loading the road graph plus scipy's sparse matrix representation exceeds the 512 MB RAM limit on Render's free tier. The app requires more memory at runtime, which would need Render's Standard plan ($25/mo) or higher.

| Component | Technology |
|-----------|-----------|
| Backend | Flask, scipy (Dijkstra on CSR matrix), OSMnx, NumPy |
| Frontend | Leaflet.js 1.9.4, Chart.js 4.4.0, vanilla JS |
