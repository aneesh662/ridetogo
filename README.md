# RideGo Taxi Booking — Flask + SQLite + Bootstrap

## Local setup
python -m venv venv
Windows: venv\Scripts\activate
pip install -r requirements.txt
python app.py

Open http://127.0.0.1:5000

Demo:
Admin: admin@ridego.local / admin123
Driver: driver@ridego.local / driver123

## GitHub
git init
git add .
git commit -m "Initial RideGo taxi booking system"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/ridego-taxi.git
git push -u origin main

## Render
Connect the GitHub repository as a Render Web Service.
Build: pip install -r requirements.txt
Start: gunicorn app:app

SQLite is suitable for learning/prototyping. Render persistent production deployments should use PostgreSQL by setting DATABASE_URL.

## Next production integrations
Google Maps/Mapbox, GPS tracking, OTP, Razorpay/Stripe, WhatsApp/SMS, PostgreSQL, WebSockets, driver verification, CSRF/rate limiting.
