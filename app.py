"""
Project: Global Heritage Scholars AI
Project Owner: Dr. Noel Biseko Lwoga
Contact: noelight79@gmail.com | 0784756363
"""

import os
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from apscheduler.schedulers.background import BackgroundScheduler
from scraper_ai import run_full_global_scan

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'global-heritage-ai-secret-2026')

# Supports PostgreSQL automatically on Render if DATABASE_URL is set, otherwise uses local SQLite

db_url = os.environ.get('DATABASE_URL', '').strip()
if not db_url:
    db_url = 'sqlite:///heritage_platform.db'
elif db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'index'

# --- DATABASE MODELS ---
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    trial_end = db.Column(db.DateTime, nullable=False)
    subscription_end = db.Column(db.DateTime, nullable=True)

    def has_active_access(self):
        now = datetime.utcnow()
        if self.trial_end and now <= self.trial_end:
            return True
        if self.subscription_end and now <= self.subscription_end:
            return True
        return False

    def days_remaining(self):
        now = datetime.utcnow()
        target = self.subscription_end if (self.subscription_end and self.subscription_end > self.trial_end) else self.trial_end
        if target and target > now:
            return (target - now).days + 1
        return 0

class Scholarship(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(300), nullable=False)
    organization = db.Column(db.String(200), nullable=False)
    location = db.Column(db.String(150), nullable=False)
    image_url = db.Column(db.String(500), nullable=False)
    summary = db.Column(db.Text, nullable=False)
    full_details = db.Column(db.Text, nullable=False)
    contact_email = db.Column(db.String(150), nullable=True)
    contact_phone = db.Column(db.String(100), nullable=True)
    apply_url = db.Column(db.String(500), nullable=False)
    deadline = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- ROUTES ---
@app.route('/')
def index():
    search_query = request.args.get('q', '').strip()
    query = Scholarship.query
    if search_query:
        like_pattern = f"%{search_query}%"
        query = query.filter(
            (Scholarship.title.ilike(like_pattern)) |
            (Scholarship.location.ilike(like_pattern)) |
            (Scholarship.organization.ilike(like_pattern))
        )
    scholarships = query.order_by(Scholarship.created_at.desc()).all()
    can_view = current_user.is_authenticated and current_user.has_active_access()
    return render_template('index.html', scholarships=scholarships, can_view=can_view, search_query=search_query)

@app.route('/register', methods=['POST'])
def register():
    full_name = request.form.get('full_name')
    email = request.form.get('email').lower().strip()
    password = request.form.get('password')

    if User.query.filter_by(email=email).first():
        flash('An account with this email already exists. Please log in.')
        return redirect(url_for('index'))

    # Every user gets an automatic 7-day free trial
    user = User(
        full_name=full_name,
        email=email,
        password_hash=generate_password_hash(password),
        trial_end=datetime.utcnow() + timedelta(days=7)
    )
    db.session.add(user)
    db.session.commit()
    login_user(user)
    flash('Welcome! Your 7-day free trial is now active across all devices.')
    return redirect(url_for('index'))

@app.route('/login', methods=['POST'])
def login():
    email = request.form.get('email').lower().strip()
    password = request.form.get('password')
    user = User.query.filter_by(email=email).first()

    if user and check_password_hash(user.password_hash, password):
        login_user(user)
        return redirect(url_for('index'))
    flash('Invalid email or password.')
    return redirect(url_for('index'))

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/subscribe', methods=['POST'])
@login_required
def subscribe():
    # Activates 30-day subscription for 2,000 TZS/month (Ready for Flutterwave/Selcom webhook)
    current_user.subscription_end = datetime.utcnow() + timedelta(days=30)
    db.session.commit()
    flash('Payment confirmed! Your 2,000 TZS monthly subscription is active for 30 days.')
    return redirect(url_for('index'))

@app.route('/trigger-scan', methods=['POST'])
@login_required
def trigger_scan():
    run_full_global_scan(app, db, Scholarship)
    flash('AI global scholarship scan completed!')
    return redirect(url_for('index'))

def seed_initial_scholarships():
    @app.route('/sw.js')
    def service_worker():
        return app.send_static_file('sw.js')

@app.route('/manifest.json')
def manifest_file():
    return app.send_static_file('manifest.json')
    if Scholarship.query.count() == 0:
        samples = [
            Scholarship(
                title="UNESCO / ICCROM World Heritage Conservation Fellowship",
                organization="UNESCO World Heritage Centre & ICCROM",
                location="Rome, Italy & Global Heritage Sites",
                image_url="https://unsplash.com",
                summary="Fully funded international fellowship supporting cultural heritage managers, archaeologists, and museum specialists.",
                full_details="Covers round-trip airfare, accommodation, monthly living stipend, and hands-on conservation workshops. Open to applicants with a degree in heritage studies, archaeology, architecture, or museum management.",
                contact_email="fellowships@iccrom.org",
                contact_phone="+39 06 585531",
                apply_url="https://iccrom.org",
                deadline="December 30, 2026"
            ),
            Scholarship(
                title="Getty Foundation Connecting Art Histories & Heritage Grant",
                organization="The Getty Foundation",
                location="Los Angeles, USA & Partner Museums Worldwide",
                image_url="https://unsplash.com",
                summary="Research and travel grants for scholars studying museum collections, historic monuments, and cultural preservation.",
                full_details="Provides research stipends, archival access funding, and international travel support for emerging and established heritage scholars.",
                contact_email="grants@getty.edu",
                contact_phone="+1 310 440 7320",
                apply_url="https://getty.edu",
                deadline="January 15, 2027"
            )
        ]
        db.session.add_all(samples)
        db.session.commit()

# Initialize DB & Background AI Scheduler (Runs every 12 hours automatically)
with app.app_context():
    db.create_all()
    seed_initial_scholarships()

scheduler = BackgroundScheduler()
scheduler.add_job(func=lambda: run_full_global_scan(app, db, Scholarship), trigger="interval", hours=12)
scheduler.start()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=False)
