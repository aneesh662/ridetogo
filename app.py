from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import os

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "change-this-secret")
db_url = os.environ.get("DATABASE_URL", "sqlite:///ridego.db")
if db_url.startswith("postgres://"): db_url = db_url.replace("postgres://","postgresql://",1)
app.config["SQLALCHEMY_DATABASE_URI"] = db_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)

class User(db.Model):
    id=db.Column(db.Integer,primary_key=True); name=db.Column(db.String(100),nullable=False)
    email=db.Column(db.String(120),unique=True,nullable=False); phone=db.Column(db.String(30))
    password_hash=db.Column(db.String(255),nullable=False); role=db.Column(db.String(20),default="customer")
    created_at=db.Column(db.DateTime,default=datetime.utcnow)
    def set_password(self,p): self.password_hash=generate_password_hash(p)
    def check_password(self,p): return check_password_hash(self.password_hash,p)

class Driver(db.Model):
    id=db.Column(db.Integer,primary_key=True); user_id=db.Column(db.Integer,db.ForeignKey("user.id"),nullable=False)
    vehicle_type=db.Column(db.String(30),default="Go"); vehicle_number=db.Column(db.String(30))
    online=db.Column(db.Boolean,default=False); rating=db.Column(db.Float,default=5.0)
    user=db.relationship("User")

class Booking(db.Model):
    id=db.Column(db.Integer,primary_key=True); customer_id=db.Column(db.Integer,db.ForeignKey("user.id"),nullable=False)
    driver_id=db.Column(db.Integer,db.ForeignKey("driver.id")); pickup=db.Column(db.String(255),nullable=False)
    dropoff=db.Column(db.String(255),nullable=False); ride_type=db.Column(db.String(30),default="Go")
    distance_km=db.Column(db.Float,default=5); fare=db.Column(db.Float,default=0)
    status=db.Column(db.String(30),default="requested"); payment_method=db.Column(db.String(30),default="cash")
    created_at=db.Column(db.DateTime,default=datetime.utcnow)
    customer=db.relationship("User",foreign_keys=[customer_id]); driver=db.relationship("Driver",foreign_keys=[driver_id])

RATES={"Auto":(35,12),"Go":(50,18),"Comfort":(80,24),"XL":(110,32)}
def calc_fare(t,d): 
    base,km=RATES.get(t,RATES["Go"]); return round(base+max(float(d),1)*km,2)
def current_user():
    return db.session.get(User,session["user_id"]) if session.get("user_id") else None
@app.context_processor
def inject(): return {"current_user":current_user()}

@app.route("/")
def index(): return render_template("index.html",rates=RATES)

@app.route("/register",methods=["GET","POST"])
def register():
    if request.method=="POST":
        email=request.form["email"].strip().lower()
        if User.query.filter_by(email=email).first(): flash("Email already registered.","danger"); return redirect(url_for("register"))
        u=User(name=request.form["name"].strip(),email=email,phone=request.form.get("phone")); u.set_password(request.form["password"])
        db.session.add(u); db.session.commit(); session["user_id"]=u.id; return redirect(url_for("index"))
    return render_template("auth.html",mode="register")

@app.route("/login",methods=["GET","POST"])
def login():
    if request.method=="POST":
        u=User.query.filter_by(email=request.form["email"].strip().lower()).first()
        if not u or not u.check_password(request.form["password"]): flash("Invalid login.","danger"); return redirect(url_for("login"))
        session["user_id"]=u.id
        return redirect(url_for("admin" if u.role=="admin" else "driver" if u.role=="driver" else "index"))
    return render_template("auth.html",mode="login")

@app.route("/logout")
def logout(): session.clear(); return redirect(url_for("index"))

@app.post("/api/fare")
def fare_api():
    d=request.get_json() or {}; return jsonify(fare=calc_fare(d.get("ride_type","Go"),d.get("distance",5)))

@app.post("/book")
def book():
    u=current_user()
    if not u: return redirect(url_for("login"))
    t=request.form.get("ride_type","Go"); dist=float(request.form.get("distance",5) or 5)
    b=Booking(customer_id=u.id,pickup=request.form["pickup"],dropoff=request.form["dropoff"],ride_type=t,distance_km=dist,fare=calc_fare(t,dist),payment_method=request.form.get("payment_method","cash"))
    db.session.add(b); db.session.commit(); flash(f"Ride #{b.id} requested. Estimated fare ₹{b.fare:.0f}.","success"); return redirect(url_for("my_rides"))

@app.route("/rides")
def my_rides():
    u=current_user()
    if not u: return redirect(url_for("login"))
    return render_template("rides.html",rides=Booking.query.filter_by(customer_id=u.id).order_by(Booking.created_at.desc()).all())

@app.route("/driver",methods=["GET","POST"])
def driver():
    u=current_user()
    if not u or u.role!="driver": return redirect(url_for("login"))
    d=Driver.query.filter_by(user_id=u.id).first()
    if request.method=="POST": d.online=request.form.get("online")=="1"; db.session.commit()
    return render_template("driver.html",driver=d,requests=Booking.query.filter_by(status="requested").all(),mine=Booking.query.filter_by(driver_id=d.id).order_by(Booking.created_at.desc()).all())

@app.post("/driver/booking/<int:bid>/<action>")
def driver_action(bid,action):
    u=current_user(); d=Driver.query.filter_by(user_id=u.id).first() if u else None; b=db.session.get(Booking,bid)
    if not d or not b: return redirect(url_for("login"))
    if action=="accept" and d.online and b.status=="requested": b.driver_id=d.id; b.status="accepted"
    elif action=="start" and b.driver_id==d.id: b.status="ongoing"
    elif action=="complete" and b.driver_id==d.id: b.status="completed"
    db.session.commit(); return redirect(url_for("driver"))

@app.route("/admin")
def admin():
    u=current_user()
    if not u or u.role!="admin": return redirect(url_for("login"))
    stats={"customers":User.query.filter_by(role="customer").count(),"drivers":User.query.filter_by(role="driver").count(),"rides":Booking.query.count(),"revenue":round(db.session.query(db.func.sum(Booking.fare)).filter(Booking.status=="completed").scalar() or 0,2)}
    return render_template("admin.html",stats=stats,rides=Booking.query.order_by(Booking.created_at.desc()).limit(100).all())

def seed():
    db.create_all()
    if not User.query.filter_by(email="admin@ridego.local").first():
        a=User(name="RideGo Admin",email="admin@ridego.local",role="admin"); a.set_password("admin123"); db.session.add(a)
    if not User.query.filter_by(email="driver@ridego.local").first():
        u=User(name="Demo Driver",email="driver@ridego.local",phone="9999999999",role="driver"); u.set_password("driver123"); db.session.add(u); db.session.flush()
        db.session.add(Driver(user_id=u.id,vehicle_type="Go",vehicle_number="KL-08-AB-1234",online=True))
    db.session.commit()
with app.app_context(): seed()
if __name__=="__main__": app.run(host="0.0.0.0",port=int(os.environ.get("PORT",5000)),debug=True)
