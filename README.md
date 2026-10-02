# RideGo — Small Uber-style Flask system

Roles:
- User: select pickup/drop-off, GPS, route distance, fare, book, watch confirmation.
- Rider: go online, receive matching vehicle requests, accept, start, complete.
- Admin: manage vehicle base fare, per-km fare, booking fee, view bookings.

## Demo
Admin: admin@ridego.local / admin123
Rider: rider@ridego.local / rider123

Create a normal User account from Register.

## Automatic location and distance
- Browser Geolocation API supplies the user's current GPS after permission.
- Nominatim searches/reverse-geocodes addresses.
- OSRM calculates road distance and duration.
- Leaflet displays the map.

Geolocation requires permission and secure contexts (HTTPS or localhost). Public Nominatim/OSRM services have usage policies; for production, use a provider/account designed for your traffic.

## Local
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python app.py

## GitHub
git init
git add .
git commit -m "RideGo small Uber system"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/ridego-small-uber.git
git push -u origin main

## Render
Connect the GitHub repo.
Build: pip install -r requirements.txt
Start: gunicorn app:app

SQLite is included for learning/prototyping. For production, use PostgreSQL by setting DATABASE_URL.

## Important production upgrades
- WebSocket/SSE notifications instead of 5-second polling
- Dedicated geocoding/routing API with key and quotas
- PostgreSQL
- OTP authentication
- CSRF protection
- rate limiting
- payment gateway
- driver verification/KYC
- cancellation rules
- surge pricing
- trip audit logs
- push/SMS/WhatsApp notifications
