from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from datetime import datetime
import os, math

app=Flask(__name__)
app.config["SECRET_KEY"]=os.environ.get("SECRET_KEY","change-me-in-production")
db_url=os.environ.get("DATABASE_URL","sqlite:///ridego.db")
if db_url.startswith("postgres://"): db_url=db_url.replace("postgres://","postgresql://",1)
app.config["SQLALCHEMY_DATABASE_URI"]=db_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"]=False
db=SQLAlchemy(app)

class User(db.Model):
    id=db.Column(db.Integer,primary_key=True)
    name=db.Column(db.String(100),nullable=False)
    email=db.Column(db.String(150),unique=True,nullable=False)
    phone=db.Column(db.String(30))
    password_hash=db.Column(db.String(255),nullable=False)
    role=db.Column(db.String(20),nullable=False,default="user") # user, rider, admin
    created_at=db.Column(db.DateTime,default=datetime.utcnow)
    def set_password(self,p): self.password_hash=generate_password_hash(p)
    def check_password(self,p): return check_password_hash(self.password_hash,p)

class Rider(db.Model):
    id=db.Column(db.Integer,primary_key=True)
    user_id=db.Column(db.Integer,db.ForeignKey("user.id"),unique=True,nullable=False)
    vehicle_type=db.Column(db.String(30),default="Go")
    vehicle_number=db.Column(db.String(40))
    online=db.Column(db.Boolean,default=False)
    lat=db.Column(db.Float)
    lng=db.Column(db.Float)
    rating=db.Column(db.Float,default=5.0)
    user=db.relationship("User")

class VehicleFare(db.Model):
    id=db.Column(db.Integer,primary_key=True)
    name=db.Column(db.String(30),unique=True,nullable=False)
    base_fare=db.Column(db.Float,default=0)
    per_km=db.Column(db.Float,default=0)
    booking_fee=db.Column(db.Float,default=0)
    active=db.Column(db.Boolean,default=True)

class Booking(db.Model):
    id=db.Column(db.Integer,primary_key=True)
    user_id=db.Column(db.Integer,db.ForeignKey("user.id"),nullable=False)
    rider_id=db.Column(db.Integer,db.ForeignKey("rider.id"))
    pickup=db.Column(db.String(255),nullable=False)
    dropoff=db.Column(db.String(255),nullable=False)
    pickup_lat=db.Column(db.Float,nullable=False)
    pickup_lng=db.Column(db.Float,nullable=False)
    dropoff_lat=db.Column(db.Float,nullable=False)
    dropoff_lng=db.Column(db.Float,nullable=False)
    distance_km=db.Column(db.Float,default=0)
    duration_min=db.Column(db.Float,default=0)
    vehicle_type=db.Column(db.String(30),nullable=False)
    fare=db.Column(db.Float,default=0)
    status=db.Column(db.String(30),default="requested")
    payment_method=db.Column(db.String(20),default="cash")
    created_at=db.Column(db.DateTime,default=datetime.utcnow)
    user=db.relationship("User",foreign_keys=[user_id])
    rider=db.relationship("Rider",foreign_keys=[rider_id])

def me(): return db.session.get(User,session["user_id"]) if session.get("user_id") else None
@app.context_processor
def inject(): return {"me":me()}

def role_required(*roles):
    def deco(fn):
        @wraps(fn)
        def wrapper(*a,**kw):
            u=me()
            if not u or u.role not in roles:
                flash("Please login with the correct account.","warning")
                return redirect(url_for("login"))
            return fn(*a,**kw)
        return wrapper
    return deco

def fare_for(vehicle,distance):
    f=VehicleFare.query.filter_by(name=vehicle,active=True).first()
    if not f: return 0
    return round(f.base_fare + f.booking_fee + max(distance,0)*f.per_km,2)

@app.route("/")
def index():
    fares=VehicleFare.query.filter_by(active=True).all()
    return render_template("index.html",fares=fares)

@app.route("/register",methods=["GET","POST"])
def register():
    if request.method=="POST":
        email=request.form["email"].strip().lower()
        if User.query.filter_by(email=email).first():
            flash("Email already exists.","danger"); return redirect(url_for("register"))
        u=User(name=request.form["name"].strip(),email=email,phone=request.form.get("phone"),role=request.form.get("role","user"))
        u.set_password(request.form["password"]); db.session.add(u); db.session.flush()
        if u.role=="rider":
            db.session.add(Rider(user_id=u.id,vehicle_type=request.form.get("vehicle_type","Go"),vehicle_number=request.form.get("vehicle_number")))
        db.session.commit(); session["user_id"]=u.id
        return redirect(url_for("rider_dashboard") if u.role=="rider" else url_for("admin_dashboard") if u.role=="admin" else url_for("index"))
    return render_template("auth.html",mode="register")

@app.route("/login",methods=["GET","POST"])
def login():
    if request.method=="POST":
        u=User.query.filter_by(email=request.form["email"].strip().lower()).first()
        if not u or not u.check_password(request.form["password"]):
            flash("Invalid email or password.","danger"); return redirect(url_for("login"))
        session["user_id"]=u.id
        return redirect(url_for("rider_dashboard") if u.role=="rider" else url_for("admin_dashboard") if u.role=="admin" else url_for("index"))
    return render_template("auth.html",mode="login")

@app.route("/logout")
def logout(): session.clear(); return redirect(url_for("index"))

@app.post("/api/fare-preview")
def fare_preview():
    d=request.get_json() or {}; return jsonify(fare=fare_for(d.get("vehicle","Go"),float(d.get("distance",0))))

@app.route("/book",methods=["POST"])
@role_required("user")
def book():
    data=request.form
    required=["pickup","dropoff","pickup_lat","pickup_lng","dropoff_lat","dropoff_lng","distance_km","duration_min","vehicle_type"]
    if any(not data.get(x) for x in required):
        flash("Please select valid pickup and drop-off locations.","danger"); return redirect(url_for("index"))
    dist=float(data["distance_km"]); vehicle=data["vehicle_type"]
    fare=fare_for(vehicle,dist)
    b=Booking(user_id=me().id,pickup=data["pickup"],dropoff=data["dropoff"],
        pickup_lat=float(data["pickup_lat"]),pickup_lng=float(data["pickup_lng"]),
        dropoff_lat=float(data["dropoff_lat"]),dropoff_lng=float(data["dropoff_lng"]),
        distance_km=dist,duration_min=float(data["duration_min"]),vehicle_type=vehicle,
        fare=fare,payment_method=data.get("payment_method","cash"))
    db.session.add(b); db.session.commit()
    flash(f"Booking #{b.id} created. Waiting for a rider.","success")
    return redirect(url_for("user_rides"))

@app.route("/rides")
@role_required("user")
def user_rides():
    rides=Booking.query.filter_by(user_id=me().id).order_by(Booking.created_at.desc()).all()
    return render_template("user_rides.html",rides=rides)

@app.route("/api/booking/<int:bid>")
def booking_status(bid):
    u=me(); b=db.session.get(Booking,bid)
    if not u or not b or (b.user_id!=u.id and u.role not in ("admin","rider")): return jsonify(error="forbidden"),403
    return jsonify(id=b.id,status=b.status,rider=(b.rider.user.name if b.rider else None),vehicle=b.vehicle_type,fare=b.fare,distance=b.distance_km,duration=b.duration_min)

@app.route("/rider",methods=["GET","POST"])
@role_required("rider")
def rider_dashboard():
    r=Rider.query.filter_by(user_id=me().id).first()
    if request.method=="POST":
        r.online=request.form.get("online")=="1"
        if request.form.get("lat"): r.lat=float(request.form["lat"]); r.lng=float(request.form["lng"])
        db.session.commit()
    open_requests=Booking.query.filter_by(status="requested",vehicle_type=r.vehicle_type).order_by(Booking.created_at.desc()).all()
    mine=Booking.query.filter_by(rider_id=r.id).order_by(Booking.created_at.desc()).all()
    return render_template("rider.html",rider=r,open_requests=open_requests,mine=mine)

@app.post("/rider/booking/<int:bid>/<action>")
@role_required("rider")
def rider_action(bid,action):
    r=Rider.query.filter_by(user_id=me().id).first(); b=db.session.get(Booking,bid)
    if not b or (action=="accept" and (not r.online or b.status!="requested")): return redirect(url_for("rider_dashboard"))
    if action=="accept":
        b.rider_id=r.id; b.status="accepted"
    elif action=="start" and b.rider_id==r.id: b.status="ongoing"
    elif action=="complete" and b.rider_id==r.id: b.status="completed"
    elif action=="cancel" and b.rider_id==r.id: b.status="cancelled"
    db.session.commit(); return redirect(url_for("rider_dashboard"))

@app.route("/admin")
@role_required("admin")
def admin_dashboard():
    fares=VehicleFare.query.order_by(VehicleFare.name).all()
    stats={"Users":User.query.filter_by(role="user").count(),"Riders":User.query.filter_by(role="rider").count(),"Bookings":Booking.query.count(),"Revenue":round(db.session.query(db.func.sum(Booking.fare)).filter(Booking.status=="completed").scalar() or 0,2)}
    return render_template("admin.html",fares=fares,stats=stats,bookings=Booking.query.order_by(Booking.created_at.desc()).limit(100).all())

@app.post("/admin/fare")
@role_required("admin")
def save_fare():
    name=request.form["name"].strip()
    f=VehicleFare.query.filter_by(name=name).first()
    if not f: f=VehicleFare(name=name); db.session.add(f)
    f.base_fare=float(request.form["base_fare"]); f.per_km=float(request.form["per_km"]); f.booking_fee=float(request.form["booking_fee"]); f.active="active" in request.form
    db.session.commit(); flash(f"{name} fare saved.","success"); return redirect(url_for("admin_dashboard"))

@app.post("/admin/fare/<int:fid>/delete")
@role_required("admin")
def delete_fare(fid):
    f=db.session.get(VehicleFare,fid)
    if f: f.active=False; db.session.commit()
    return redirect(url_for("admin_dashboard"))

def seed():
    db.create_all()
    defaults=[("Auto",30,12,5),("Go",50,18,10),("Comfort",80,24,15),("XL",110,32,20)]
    for n,b,k,fee in defaults:
        if not VehicleFare.query.filter_by(name=n).first(): db.session.add(VehicleFare(name=n,base_fare=b,per_km=k,booking_fee=fee))
    if not User.query.filter_by(email="admin@ridego.local").first():
        u=User(name="RideGo Admin",email="admin@ridego.local",role="admin"); u.set_password("admin123"); db.session.add(u)
    if not User.query.filter_by(email="rider@ridego.local").first():
        u=User(name="Demo Rider",email="rider@ridego.local",phone="9999999999",role="rider"); u.set_password("rider123"); db.session.add(u); db.session.flush()
        db.session.add(Rider(user_id=u.id,vehicle_type="Go",vehicle_number="KL-08-AB-1234",online=True))
    db.session.commit()

with app.app_context(): seed()
if __name__=="__main__": app.run(host="0.0.0.0",port=int(os.environ.get("PORT",5000)),debug=True)
