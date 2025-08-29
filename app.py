import os
from datetime import datetime, date, timedelta
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__, static_folder='static', static_url_path='/static')

DATABASE_URL = os.environ.get("DATABASE_URL")
if DATABASE_URL:
    app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL
else:
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///cronospark.db"

app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-key")

db = SQLAlchemy(app)

# ---------------------------
# MODELS
# ---------------------------
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(120), unique=True, nullable=False)
    pin_hash = db.Column(db.String(256), nullable=False)  # hashed PIN
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def verify_pin(self, pin_plain):
        return check_password_hash(self.pin_hash, pin_plain)

    def __repr__(self):
        return f"<User {self.username}>"

class Event(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    date = db.Column(db.String(50), nullable=True)  # ISO date YYYY-MM-DD
    time = db.Column(db.String(20), nullable=True)  # hh:mm
    link = db.Column(db.String(500), nullable=True)
    urgent = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Event {self.id} {self.title}>"

# ---------------------------
# DB init & utilities
# ---------------------------
def parse_iso_date(s):
    if not s:
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except Exception:
        try:
            return datetime.fromisoformat(s).date()
        except Exception:
            return None

def clean_past_events():
    """Elimina eventos con fecha anterior a hoy (solo si tienen fecha válida)."""
    today = date.today()
    to_delete = []
    for e in Event.query.all():
        d = parse_iso_date(e.date)
        if d and d < today:
            to_delete.append(e)
    if to_delete:
        for e in to_delete:
            db.session.delete(e)
        db.session.commit()
        app.logger.info(f"Limpiados {len(to_delete)} eventos pasados.")

with app.app_context():
    db.create_all()
    try:
        clean_past_events()
    except Exception as ex:
        app.logger.exception("Error limpiando eventos pasados: %s", ex)

# ---------------------------
# Auth helpers
# ---------------------------
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            flash("Necesitas iniciar sesión.", "error")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated

def get_current_user():
    uid = session.get("user_id")
    if not uid:
        return None
    return User.query.get(uid)

@app.context_processor
def inject_user():
    return {"current_user": get_current_user()}

# ---------------------------
# AUTH ROUTES
# ---------------------------
@app.route("/register", methods=["GET", "POST"])
def register():
    """Crear usuario: username + PIN(4 dígitos). Útil para primer setup."""
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        pin = request.form.get("pin", "").strip()

        if not username or not pin:
            flash("Usuario y PIN son obligatorios.", "error")
            return redirect(url_for("register"))

        if not pin.isdigit() or len(pin) != 4:
            flash("El PIN debe tener exactamente 4 dígitos.", "error")
            return redirect(url_for("register"))

        if User.query.filter_by(username=username).first():
            flash("Ya existe ese usuario.", "error")
            return redirect(url_for("register"))

        hashed = generate_password_hash(pin, method="pbkdf2:sha256", salt_length=8)
        user = User(username=username, pin_hash=hashed)
        db.session.add(user)
        db.session.commit()
        flash("Usuario creado. Ya puedes iniciar sesión.", "success")
        return redirect(url_for("login"))

    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        pin = request.form.get("pin", "").strip()

        user = User.query.filter_by(username=username).first()
        if not user or not user.verify_pin(pin):
            flash("Usuario o PIN inválido.", "error")
            return redirect(url_for("login"))

        session["user_id"] = user.id
        flash(f"Bienvenido {user.username} ✔", "success")
        return redirect(url_for("index"))

    return render_template("login.html")

@app.route("/logout")
def logout():
    session.pop("user_id", None)
    flash("Sesión cerrada.", "info")
    return redirect(url_for("login"))

# ---------------------------
# APP ROUTES (protegidos)
# ---------------------------
@app.route("/")
@login_required
def index():
    # Limpieza ligera
    try:
        clean_past_events()
    except Exception:
        pass

    user = get_current_user()
    if not user:
        flash("Usuario no encontrado en sesión.", "error")
        return redirect(url_for("login"))

    # traer solo eventos del usuario
    all_events = Event.query.filter_by(user_id=user.id).order_by(Event.date, Event.time, Event.created_at.desc()).all()

    today = date.today()
    near_threshold = today + timedelta(days=3)

    very_near_urgent = []
    other_events = []
    for e in all_events:
        e_date = parse_iso_date(e.date)
        is_very_near = False
        days_left = None
        days_label = None

        if e_date:
            days_left = (e_date - today).days
            if days_left < 0:
                days_label = "Venció"
            elif days_left == 0:
                days_label = "Hoy"
            elif days_left == 1:
                days_label = "Mañana"
            else:
                days_label = f"En {days_left} días"
            if e.urgent and 0 <= days_left <= 3:
                is_very_near = True

        setattr(e, "_is_very_near", is_very_near)
        setattr(e, "_days_left", days_left)
        setattr(e, "_days_label", days_label)

        if is_very_near:
            very_near_urgent.append(e)
        else:
            other_events.append(e)

    events_ordered = very_near_urgent + other_events
    urgent_events = [e for e in events_ordered if e.urgent][:5]

    return render_template("index.html", events=events_ordered, urgent_events=urgent_events)

@app.route("/add", methods=["GET", "POST"])
@login_required
def add_event():
    if request.method == "POST":
        user = get_current_user()
        title = request.form.get("title")
        description = request.form.get("description")
        date_str = request.form.get("date")
        time = request.form.get("time")
        link = request.form.get("link")
        urgent = True if request.form.get("urgent") == "on" else False

        if not title:
            flash("El título es obligatorio", "error")
            return redirect(url_for("index"))

        if date_str and parse_iso_date(date_str) is None:
            flash("Formato de fecha inválido. Usa YYYY-MM-DD.", "error")
            return redirect(url_for("add_event"))

        event = Event(
            user_id=user.id,
            title=title,
            description=description,
            date=date_str or None,
            time=time or None,
            link=link or None,
            urgent=urgent
        )
        db.session.add(event)
        db.session.commit()
        flash("Evento agregado ✔", "success")
        return redirect(url_for("index"))

    return render_template("add_event.html")

@app.route("/delete/<int:event_id>", methods=["POST"])
@login_required
def delete_event(event_id):
    user = get_current_user()
    event = Event.query.get_or_404(event_id)
    if event.user_id != user.id:
        flash("No tienes permiso para eliminar este evento.", "error")
        return redirect(url_for("index"))
    db.session.delete(event)
    db.session.commit()
    flash("Evento eliminado 🗑️", "info")
    return redirect(url_for("index"))

# ---------------------------
# RUN
# ---------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
