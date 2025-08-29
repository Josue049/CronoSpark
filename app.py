import os
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)

# Configuración de base de datos: usa DATABASE_URL si está en el entorno (Postgres en Render)
DATABASE_URL = os.environ.get("DATABASE_URL")
if DATABASE_URL:
    app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL
else:
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///cronospark.db"

app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-key")

db = SQLAlchemy(app)

class Event(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    date = db.Column(db.String(50), nullable=True)  # ISO date YYYY-MM-DD
    time = db.Column(db.String(20), nullable=True)  # hh:mm
    link = db.Column(db.String(500), nullable=True)
    urgent = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Event {self.id} {self.title}>"

@app.before_first_request
def create_tables():
    db.create_all()

@app.route("/")
def index():
    # Ordena por fecha (si hay) y luego por hora y creación
    events = Event.query.order_by(Event.date.asc().nullsfirst(), Event.time.asc().nullsfirst(), Event.created_at.desc()).all()
    urgent_events = Event.query.filter_by(urgent=True).order_by(Event.date.asc().nullsfirst()).limit(5).all()
    return render_template("index.html", events=events, urgent_events=urgent_events)

@app.route("/add", methods=["GET", "POST"])
def add_event():
    if request.method == "POST":
        title = request.form.get("title")
        description = request.form.get("description")
        date = request.form.get("date")
        time = request.form.get("time")
        link = request.form.get("link")
        urgent = True if request.form.get("urgent") == "on" else False

        if not title:
            flash("El título es obligatorio", "error")
            return redirect(url_for("index"))

        event = Event(title=title, description=description, date=date or None, time=time or None, link=link or None, urgent=urgent)
        db.session.add(event)
        db.session.commit()
        flash("Evento agregado ✔", "success")
        return redirect(url_for("index"))

    return render_template("add_event.html")

@app.route("/delete/<int:event_id>", methods=["POST"])
def delete_event(event_id):
    event = Event.query.get_or_404(event_id)
    db.session.delete(event)
    db.session.commit()
    flash("Evento eliminado 🗑️", "info")
    return redirect(url_for("index"))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)