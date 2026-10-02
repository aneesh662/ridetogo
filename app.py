import os
from datetime import datetime
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DATA_DIR = os.environ.get('DATA_DIR', os.path.join(BASE_DIR, 'data'))
os.makedirs(DATA_DIR, exist_ok=True)
DB_PATH = os.path.join(DATA_DIR, 'ridego.db')

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'change-this-secret-in-production')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + DB_PATH
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(160), unique=True, nullable=False)
    phone = db.Column(db.String(30), nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='user')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Rider(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), unique=True, nullable=False)
    vehicle_type = db.Column(db.String(50), nullable=False)
    vehicle_number = db.Column(db.String(50), nullable=False)
    vehicle_model = db.Column(db.String(80), default='')
    vehicle_color = db.Column(db.String(40), default='')
    license_number = db.Column(db.String(80), default='')
    license_expiry = db.Column(db.String(30), default='')
    address = db.Column(db.String(255), default='')
    online = db.Column(db.Boolean, default=False)
    lat = db.Column(db.Float)
    lng = db.Column(db.Float)
    rating = db.Column(db.Float, default=5.0)
    user = db.relationship('User', backref=db.backref('rider_profile', uselist=False))

class VehicleFare(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    base_fare = db.Column(db.Float, default=0)
    per_km = db.Column(db.Float, default=0)
    booking_fee = db.Column(db.Float, default=0)
    active = db.Column(db.Boolean, default=True)

class Booking(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    rider_id = db.Column(db.Integer, db.ForeignKey('rider.id'))
    pickup = db.Column(db.String(255), nullable=False)
    dropoff = db.Column(db.String(255), nullable=False)
    pickup_lat = db.Column(db.Float, nullable=False)
    pickup_lng = db.Column(db.Float, nullable=False)
    dropoff_lat = db.Column(db.Float, nullable=False)
    dropoff_lng = db.Column(db.Float, nullable=False)
    distance_km = db.Column(db.Float, nullable=False)
    duration_min = db.Column(db.Float, nullable=False)
    vehicle_type = db.Column(db.String(50), nullable=False)
    fare = db.Column(db.Float, nullable=False)
    payment_method = db.Column(db.String(30), default='cash')
    status = db.Column(db.String(30), default='requested')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user = db.relationship('User', backref='bookings')
    rider = db.relationship('Rider', backref='bookings')

def fare_for(vehicle, distance):
    f = VehicleFare.query.filter_by(name=vehicle, active=True).first()
    if not f:
        return None
    return round(f.base_fare + f.booking_fee + max(0, distance) * f.per_km, 2)

def login_required(role=None):
    def deco(fn):
        @wraps(fn)
        def wrapped(*args, **kwargs):
            if not session.get('user_id'):
                return redirect(url_for('login'))
            if role and session.get('role') != role:
                flash('Access denied.', 'danger')
                return redirect(url_for('home'))
            return fn(*args, **kwargs)
        return wrapped
    return deco

def seed():
    db.create_all()
    if not User.query.filter_by(email='admin@ridego.com').first():
        db.session.add(User(name='RideGo Admin', email='admin@ridego.com', phone='9999999999', password_hash=generate_password_hash('admin123'), role='admin'))
    defaults = [('Auto',30,12,5),('Go',50,18,10),('Comfort',80,24,15),('XL',110,32,20)]
    for name, base, km, fee in defaults:
        if not VehicleFare.query.filter_by(name=name).first():
            db.session.add(VehicleFare(name=name, base_fare=base, per_km=km, booking_fee=fee, active=True))
    db.session.commit()

with app.app_context():
    seed()

@app.route('/')
def home():
    fares = VehicleFare.query.filter_by(active=True).all()
    return render_template('index.html', fares=fares)

@app.route('/signup', methods=['GET','POST'])
def signup():
    if request.method == 'POST':
        name, email, phone, password = [request.form.get(x,'').strip() for x in ('name','email','phone','password')]
        if not all([name,email,phone,password]):
            flash('Please fill all fields.', 'danger')
        elif User.query.filter_by(email=email.lower()).first():
            flash('Email already registered.', 'danger')
        else:
            u = User(name=name, email=email.lower(), phone=phone, password_hash=generate_password_hash(password), role='user')
            db.session.add(u); db.session.commit()
            flash('Account created. Please login.', 'success')
            return redirect(url_for('login'))
    return render_template('auth.html', mode='signup')

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email','').strip().lower(); password = request.form.get('password','')
        u = User.query.filter_by(email=email).first()
        if u and check_password_hash(u.password_hash, password):
            session['user_id']=u.id; session['role']=u.role; session['name']=u.name
            if u.role == 'admin': return redirect(url_for('admin'))
            if u.role == 'rider': return redirect(url_for('rider'))
            return redirect(url_for('book'))
        flash('Invalid email or password.', 'danger')
    return render_template('auth.html', mode='login')

@app.route('/logout')
def logout():
    session.clear(); return redirect(url_for('home'))

@app.route('/book', methods=['GET','POST'])
@login_required('user')
def book():
    if request.method == 'POST':
        try:
            vehicle=request.form['vehicle_type']; distance=float(request.form['distance_km']); duration=float(request.form['duration_min'])
            pl=float(request.form['pickup_lat']); pg=float(request.form['pickup_lng']); dl=float(request.form['dropoff_lat']); dg=float(request.form['dropoff_lng'])
            pickup=request.form['pickup']; dropoff=request.form['dropoff']; payment=request.form.get('payment_method','cash')
            fare=fare_for(vehicle,distance)
            if fare is None: raise ValueError('Vehicle fare unavailable')
            b=Booking(user_id=session['user_id'], pickup=pickup, dropoff=dropoff, pickup_lat=pl, pickup_lng=pg, dropoff_lat=dl, dropoff_lng=dg, distance_km=distance, duration_min=duration, vehicle_type=vehicle, fare=fare, payment_method=payment, status='requested')
            db.session.add(b); db.session.commit()
            flash(f'Ride #{b.id} requested. Waiting for a Rider.', 'success')
            return redirect(url_for('my_rides'))
        except Exception as e:
            flash(str(e), 'danger')
    return render_template('book.html', fares=VehicleFare.query.filter_by(active=True).all())

@app.route('/my-rides')
@login_required('user')
def my_rides():
    rides=Booking.query.filter_by(user_id=session['user_id']).order_by(Booking.created_at.desc()).all()
    return render_template('user_rides.html', rides=rides)

@app.route('/rider')
@login_required('rider')
def rider():
    rider=Rider.query.filter_by(user_id=session['user_id']).first()
    requests=Booking.query.filter_by(status='requested', vehicle_type=rider.vehicle_type).order_by(Booking.created_at.desc()).all() if rider else []
    active=Booking.query.filter_by(rider_id=rider.id).filter(Booking.status.in_(['accepted','ongoing'])).first() if rider else None
    return render_template('rider.html', rider=rider, requests=requests, active=active)

@app.post('/rider/status')
@login_required('rider')
def rider_status():
    r=Rider.query.filter_by(user_id=session['user_id']).first(); data=request.get_json(silent=True) or request.form
    r.online=bool(data.get('online')); 
    if data.get('lat') is not None: r.lat=float(data['lat']); r.lng=float(data['lng'])
    db.session.commit(); return jsonify(ok=True)

@app.post('/rider/booking/<int:bid>/<action>')
@login_required('rider')
def rider_action(bid, action):
    r=Rider.query.filter_by(user_id=session['user_id']).first(); b=db.session.get(Booking,bid)
    if not b or (action!='accept' and b.rider_id!=r.id): return jsonify(ok=False,error='Not allowed'),403
    if action=='accept':
        if b.status!='requested': return jsonify(ok=False,error='Already accepted'),400
        b.rider_id=r.id; b.status='accepted'
    elif action=='start' and b.status=='accepted': b.status='ongoing'
    elif action=='complete' and b.status=='ongoing': b.status='completed'
    elif action=='cancel': b.status='cancelled'
    else: return jsonify(ok=False,error='Invalid action'),400
    db.session.commit(); return jsonify(ok=True,status=b.status)

@app.get('/api/booking/<int:bid>')
@login_required()
def booking_api(bid):
    b=db.session.get(Booking,bid)
    if not b or (session['role']=='user' and b.user_id!=session['user_id']): return jsonify(error='Not found'),404
    rider=None
    if b.rider_id:
        r=db.session.get(Rider,b.rider_id); rider={'name':r.user.name,'phone':r.user.phone,'vehicle_type':r.vehicle_type,'vehicle_number':r.vehicle_number,'lat':r.lat,'lng':r.lng,'rating':r.rating}
    return jsonify(id=b.id,status=b.status,vehicle=b.vehicle_type,fare=b.fare,distance=b.distance_km,duration=b.duration_min,rider=rider)

@app.post('/api/fare-preview')
def fare_preview():
    try:
        vehicle=request.json['vehicle']; distance=float(request.json['distance']); fare=fare_for(vehicle,distance)
        return jsonify(fare=fare)
    except Exception: return jsonify(fare=None),400

@app.route('/admin')
@login_required('admin')
def admin():
    riders=Rider.query.order_by(Rider.id.desc()).all(); users=User.query.filter_by(role='user').order_by(User.id.desc()).all(); fares=VehicleFare.query.order_by(VehicleFare.id).all(); bookings=Booking.query.order_by(Booking.created_at.desc()).limit(100).all()
    revenue=sum(b.fare for b in Booking.query.filter_by(status='completed').all())
    return render_template('admin.html', riders=riders, users=users, fares=fares, bookings=bookings, revenue=revenue)

@app.post('/admin/rider/create')
@login_required('admin')
def admin_create_rider():
    name=request.form['name'].strip(); email=request.form['email'].strip().lower(); phone=request.form['phone'].strip(); password=request.form['password']; vehicle=request.form['vehicle_type']; number=request.form['vehicle_number'].strip(); model=request.form.get('vehicle_model','').strip(); color=request.form.get('vehicle_color','').strip(); license_no=request.form.get('license_number','').strip(); license_expiry=request.form.get('license_expiry','').strip(); address=request.form.get('address','').strip()
    if User.query.filter_by(email=email).first(): flash('Email already exists.','danger'); return redirect(url_for('admin'))
    u=User(name=name,email=email,phone=phone,password_hash=generate_password_hash(password),role='rider'); db.session.add(u); db.session.flush()
    db.session.add(Rider(user_id=u.id,vehicle_type=vehicle,vehicle_number=number,vehicle_model=model,vehicle_color=color,license_number=license_no,license_expiry=license_expiry,address=address)); db.session.commit(); flash('Rider created successfully.','success'); return redirect(url_for('admin'))

@app.post('/admin/rider/<int:rid>/toggle')
@login_required('admin')
def admin_toggle_rider(rid):
    r=db.session.get(Rider,rid); r.online=not r.online; db.session.commit(); return redirect(url_for('admin'))

@app.post('/admin/rider/<int:rid>/delete')
@login_required('admin')
def admin_delete_rider(rid):
    r=db.session.get(Rider,rid)
    if r:
        u=r.user
        Booking.query.filter_by(rider_id=r.id).update({Booking.rider_id:None})
        db.session.delete(r); db.session.delete(u); db.session.commit()
    flash('Rider deleted.','success'); return redirect(url_for('admin'))

@app.post('/admin/fare')
@login_required('admin')
def admin_fare():
    fid=request.form.get('id'); name=request.form['name'].strip(); base=float(request.form['base_fare']); km=float(request.form['per_km']); fee=float(request.form['booking_fee']); active=bool(request.form.get('active'))
    f=db.session.get(VehicleFare,int(fid)) if fid else None
    if not f: f=VehicleFare(name=name); db.session.add(f)
    f.name=name; f.base_fare=base; f.per_km=km; f.booking_fee=fee; f.active=active; db.session.commit(); return redirect(url_for('admin'))

@app.post('/admin/fare/<int:fid>/delete')
@login_required('admin')
def admin_fare_delete(fid):
    f=db.session.get(VehicleFare,fid)
    if f: db.session.delete(f); db.session.commit()
    return redirect(url_for('admin'))

@app.get('/health')
def health(): return jsonify(status='ok')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT',5000)), debug=True)
