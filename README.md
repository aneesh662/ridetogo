# RideGo - Small Uber Style Taxi Booking System

Flask + SQLite + Bootstrap + JavaScript + Leaflet/OpenStreetMap.

## Roles
- User: sign up, choose pickup/drop directly on map, automatic road distance/fare, book ride, see Rider confirmation.
- Rider: created by Admin, login, go online, share GPS, accept/start/complete rides.
- Admin: create/delete Riders, set vehicle fares, view users/rides/revenue.

## Local run
```bash
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python app.py
```
Open http://127.0.0.1:5000

Default Admin: admin@ridego.com / admin123

## Render
The included render.yaml configures Gunicorn and a persistent disk for SQLite. Render's normal filesystem is ephemeral, so persistent storage is required if SQLite data must survive restarts/deploys. For a larger production system, use managed PostgreSQL instead.

Push this folder to GitHub and create a Render Web Service from the repository.
