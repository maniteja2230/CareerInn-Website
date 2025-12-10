# app.py - FINAL COMPLETE CODE for CareerInn (Hospitality & Tech)

import os
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

from flask import (
    Flask,
    request,
    redirect,
    session,
    render_template_string,
    send_from_directory,
    url_for,
)
from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    String,
    Float,
    Text,
    Boolean,
)
from sqlalchemy.orm import declarative_base, sessionmaker, scoped_session
from groq import Groq

# -------------------- CONFIG & ENVIRONMENT --------------------
app = Flask(__name__)
# Load key from environment (MUST be set in Render Environment Variables)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "careerinn_secure_key_default_fallback") 
app.config["UPLOAD_FOLDER"] = os.path.join(os.path.dirname(__file__), "uploads")
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
ALLOWED_EXTENSIONS = {"pdf"}

# Admin credentials (MUST be set in Render Environment Variables for production security)
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin_careerinn")
# Using a fallback hash for local testing only; Render env var is required for live use
ADMIN_PASSWORD_HASH = generate_password_hash(os.getenv("ADMIN_PASSWORD", "careerinn_admin_secure"), method="pbkdf2:sha256", salt_length=16)

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

# -------------------- GROQ CLIENT HELPER --------------------
def get_groq_client():
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        return None
    return Groq(api_key=api_key)

# -------------------- DB SETUP (CRUCIAL: Path for Render Persistent Disk) --------------------
# This path /var/data must match the Mount Path of your Render Persistent Disk.
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:////var/data/careerinn.db")
engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = scoped_session(sessionmaker(bind=engine, autoflush=False, autocommit=False))
Base = declarative_base()

# -------------------- MODELS --------------------
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    password = Column(String(255), nullable=False)

class College(Base): # Hospitality College
    __tablename__ = "colleges"
    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    location = Column(String(255), nullable=False)
    fees = Column(Integer, nullable=False)
    course = Column(String(255), nullable=False)
    rating = Column(Float, nullable=False)

class BtechCourse(Base): # B.Tech College
    __tablename__ = "btech_courses"
    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False) # College name
    location = Column(String(255), nullable=False)
    fees = Column(Integer, nullable=False)
    specialization = Column(String(255), nullable=False)
    rating = Column(Float, nullable=False)

class Mentor(Base):
    __tablename__ = "mentors"
    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    experience = Column(Text, nullable=False)
    speciality = Column(String(255), nullable=False) # e.g., Hotel Ops / CSE / Data Science

class Job(Base): # Hospitality Job
    __tablename__ = "jobs"
    id = Column(Integer, primary_key=True)
    title = Column(Text, nullable=False)
    company = Column(String(255), nullable=False)
    location = Column(String(255), nullable=False)
    salary = Column(String(255), nullable=False)

class BtechJob(Base): # B.Tech Job
    __tablename__ = "btech_jobs"
    id = Column(Integer, primary_key=True)
    title = Column(Text, nullable=False)
    company = Column(String(255), nullable=False)
    location = Column(String(255), nullable=False)
    package = Column(String(255), nullable=False)

class AiUsage(Base):
    __tablename__ = "ai_usage"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False, unique=True)
    ai_used = Column(Integer, nullable=False, default=0)

class UserProfile(Base):
    __tablename__ = "user_profiles"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False, unique=True)
    skills_text = Column(Text, nullable=True)
    target_roles = Column(Text, nullable=True)
    self_rating = Column(Integer, nullable=False, default=0)
    resume_link = Column(String(500), nullable=True)
    notes = Column(Text, nullable=True)

class Subscription(Base):
    __tablename__ = "subscriptions"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False, unique=True)
    active = Column(Boolean, nullable=False, default=False)

class MockInterview(Base):
    __tablename__ = "mock_interviews"
    id = Column(Integer, primary_key=True)
    title = Column(String(300), nullable=False)
    notes = Column(Text, nullable=True)
    link = Column(String(1000), nullable=True)
    uploader_id = Column(Integer, nullable=True)

class PrevPaper(Base):
    __tablename__ = "prev_papers"
    id = Column(Integer, primary_key=True)
    title = Column(String(300), nullable=False)
    year = Column(String(20), nullable=True)
    link = Column(String(1000), nullable=True)
    uploader_id = Column(Integer, nullable=True)
    is_upload = Column(Boolean, nullable=False, default=False)

# -------------------- DB INIT & SEED --------------------
def get_db():
    return SessionLocal()

def init_db():
    db = get_db()
    # Check if DB file exists and has tables. If not, create and seed.
    Base.metadata.create_all(bind=engine)

    # --- Seed Hospitality Colleges ---
    if db.query(College).count() == 0:
        colleges_seed = [
            ("IHM Hyderabad (IHMH)", "DD Colony, Hyderabad", 320000, "BSc in Hospitality & Hotel Administration", 4.6),
            ("NITHM Hyderabad", "Gachibowli, Hyderabad", 280000, "BBA in Tourism & Hospitality", 4.3),
            ("IIHM Hyderabad", "Somajiguda, Hyderabad", 350000, "BA in Hospitality Management", 4.5),
            ("Regency College of Culinary Arts", "Himayatnagar, Hyderabad", 240000, "BHM & Culinary Arts", 4.4),
        ]
        for name, loc, fees, course, rating in colleges_seed:
            db.add(College(name=name, location=loc, fees=fees, course=course, rating=rating))

    # --- Seed B.Tech Colleges ---
    if db.query(BtechCourse).count() == 0:
        btech_seed = [
            ("IIT Hyderabad (IITH)", "Kandi, Sangareddy", 220000, "Computer Science & Engineering (CSE)", 4.8),
            ("IIIT Hyderabad", "Gachibowli, Hyderabad", 340000, "IT/CSE/ECE", 4.9),
            ("JNTU Hyderabad (JNTUH)", "Kukatpally, Hyderabad", 125000, "Various B.Tech Specializations", 4.5),
            ("Gitam Hyderabad", "Rudraram, Sangareddy", 250000, "Computer Science & Emerging Tech", 4.2),
        ]
        for name, loc, fees, spec, rating in btech_seed:
            db.add(BtechCourse(name=name, location=loc, fees=fees, specialization=spec, rating=rating))

    # --- Seed Mentors ---
    if db.query(Mentor).count() == 0:
        mentors_seed = [
            ("Mentor Chef A", "20+ years, 5-star Culinary", "Hotel Ops / Culinary"),
            ("Mentor Tech B", "Ex-Amazon SDE, 10+ years", "Computer Science / Software Dev"),
            ("Mentor Global C", "Abroad admissions & cruise guidance", "Hospitality / Global Careers"),
        ]
        for n, exp, spec in mentors_seed:
            db.add(Mentor(name=n, experience=exp, speciality=spec))

    # --- Seed Hospitality Jobs ---
    if db.query(Job).count() == 0:
        jobs_seed = [
            ("Management Trainee (Hotel Ops)", "Taj / IHCL", "Pan India", "Avg package ~₹4.5–5.5 LPA"),
            ("F&B Associate", "Marriott Hotels", "Hyderabad / Bengaluru", "Avg package ~₹3–4 LPA"),
        ]
        for t, c_, loc, sal in jobs_seed:
            db.add(Job(title=t, company=c_, location=loc, salary=sal))

    # --- Seed B.Tech Jobs ---
    if db.query(BtechJob).count() == 0:
        btech_jobs_seed = [
            ("Software Development Engineer I (SDE)", "Microsoft", "Hyderabad / Bengaluru", "Avg package ~₹15–25 LPA"),
            ("Data Analyst (Tech in Hospitality)", "OYO / Tech Startups", "Hyderabad", "Avg package ~₹6–10 LPA"),
        ]
        for t, c_, loc, pkg in btech_jobs_seed:
            db.add(BtechJob(title=t, company=c_, location=loc, package=pkg))

    # --- Seed Mock Interviews ---
    if db.query(MockInterview).count() == 0:
        db.add(MockInterview(title="Front Office Mock - Common Questions", notes="Roleplay: guest complains about late check-in.", link="https://www.example.com/mock-frontoffice", uploader_id=None))
        db.add(MockInterview(title="Technical Interview - Data Structures", notes="Practice basic DSA for SDE roles.", link="https://www.example.com/mock-dsa", uploader_id=None))
    
    # --- Seed Previous Papers ---
    if db.query(PrevPaper).count() == 0:
        db.add(PrevPaper(title="NCHM JEE - PYQ Collection", year="all", link="https://admission.aglasem.com/nchmct-jee-question-paper/", uploader_id=None, is_upload=False))
        db.add(PrevPaper(title="JEE Mains - PYQ Collection", year="all", link="https://www.example.com/jee-pyqs", uploader_id=None, is_upload=False))


    db.commit()
    db.close()

@app.teardown_appcontext
def shutdown_session(exception=None):
    SessionLocal.remove()

# init DB - this ensures tables exist and are seeded on first run
init_db()

# -------------------- AI SYSTEM PROMPT --------------------
AI_SYSTEM_PROMPT = """
You are CareerInn's AI career guide. Your expertise covers both hospitality/hotel management and B.Tech/Engineering careers.
Talk friendly and act like a mentor. Ask questions step-by-step. Guide the student based on their domain (Hosp. or Tech).
"""

# -------------------- BASE LAYOUT (UPDATED FOR TECH LINKS) --------------------
# This block is the core structure. It contains the new B.Tech navigation links.
BASE_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>{{ title or "CareerInn" }}</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <script src="https://cdn.tailwindcss.com"></script>
  <link rel="stylesheet" href="/static/style.css">
  <style>
    /* AI popup styles + animation (chef emoji) */
    .ai-fab { position: fixed; right: 20px; bottom: 20px; z-index: 1000; width:72px; height:72px; border-radius:999px; display:flex; align-items:center; justify-content:center; font-size:30px; cursor:pointer; box-shadow:0 12px 30px rgba(99,102,241,0.18); }
    .ai-fab .emoji { display:inline-block; transform-origin:center; animation: float 3s ease-in-out infinite, rotate 6s linear infinite; }
    @keyframes float { 0%{transform:translateY(0)}50%{transform:translateY(-8px)}100%{transform:translateY(0)} }
    @keyframes rotate { 0%{transform:rotate(0deg)}100%{transform:rotate(360deg)} }
    .ai-modal-bg { position: fixed; inset: 0; background: rgba(2,6,23,0.6); display: none; z-index: 1000; }
    .ai-modal { position: fixed; right: 24px; bottom: 110px; width:420px; max-width:96%; background:#060814; border-radius:16px; box-shadow:0 20px 50px rgba(0,0,0,0.6); padding:14px; display:none; z-index:1001; }
  </style>
</head>
<body class="bg-[#050815] text-white">

<div class="min-h-screen bg-gradient-to-b from-slate-950 via-slate-900 to-slate-950">

  <nav class="flex justify-between items-center px-6 md:px-10 py-4 bg-black/40 backdrop-blur-md border-b border-slate-800">
    <div class="flex items-center gap-3">
      <div class="w-12 h-12 rounded-2xl bg-slate-900 flex items-center justify-center overflow-hidden shadow-lg">
        <img src="/static/logo.png" class="w-11 h-11 object-contain" alt="logo">
      </div>
      <div>
        <p class="font-bold text-lg md:text-xl tracking-tight">CareerInn</p>
        <p class="text-[11px] text-slate-400">Hospitality & Tech Careers · Colleges · Jobs</p>
      </div>
    </div>

    <div class="hidden md:flex items-center gap-4">
      <a href="/" class="hover:text-indigo-400">Home</a>
      <a href="/courses" class="hover:text-indigo-400">Hosp. Courses</a>
      <a href="/colleges" class="hover:text-indigo-400">Hosp. Colleges</a>
      <a href="/btech-colleges" class="hover:text-indigo-400">B.Tech Colleges</a> 
      <a href="/jobs" class="hover:text-indigo-400">Hosp. Jobs</a>
      <a href="/btech-jobs" class="hover:text-indigo-400">B.Tech Jobs</a> 
      <a href="/global-match" class="hover:text-indigo-400">Global Match</a>
      <a href="/chatbot" class="hover:text-indigo-400">AI Career Bot</a>
      <a href="/support" class="hover:text-indigo-400">Support</a>

      {% if session.get('user') %}
        <div class="flex items-center gap-3">
          <a href="/profile" class="flex items-center gap-2 px-3 py-1.5 rounded-full bg-slate-800 border border-slate-700">
            <div class="w-8 h-8 rounded-full bg-indigo-600 flex items-center justify-center font-semibold text-sm">
              {{ session.get('user')[0]|upper }}
            </div>
            <div class="text-xs text-slate-300">{{ session.get('user') }}</div>
          </a>
          <a href="/logout" class="px-4 py-1.5 rounded-full bg-rose-500 hover:bg-rose-600 text-xs font-semibold">Logout</a>
        </div>
      {% else %}
        <a href="/login" class="px-4 py-1.5 rounded-full bg-indigo-500 hover:bg-indigo-600 text-xs font-semibold">Login</a>
      {% endif %}
    </div>
  </nav>

  <main class="px-5 md:px-10 py-8">
      {{ content|safe }}
  </main>
</div>

<button id="aiFab" class="ai-fab bg-gradient-to-br from-indigo-500 to-emerald-400">
  <span class="emoji">👩‍💻</span> 
</button>

<div id="aiModalBg" class="ai-modal-bg"></div>

<div id="aiModal" class="ai-modal">
  <div class="flex items-center justify-between mb-2">
    <div class="font-semibold">CareerInn AI</div>
    <button id="closeAi" class="text-slate-400 hover:text-white">✕</button>
  </div>
  <p class="text-xs text-slate-300 mb-3">Try our AI Career Chat or start a mock interview. Quick, friendly and mentoring style.</p>
  <div class="flex gap-2">
    <a href="/chatbot" class="flex-1 px-3 py-2 rounded bg-indigo-600 text-sm text-center">Start AI Career Chat</a>
    <a href="/mock-interviews/ai" class="flex-1 px-3 py-2 rounded border border-slate-700 text-sm text-center">Mock Interview Bot</a>
  </div>
</div>

<script>
  const aiFab = document.getElementById('aiFab');
  const aiModal = document.getElementById('aiModal');
  const aiModalBg = document.getElementById('aiModalBg');
  const closeAi = document.getElementById('closeAi');

  function openAi() {
    aiModal.style.display = 'block';
    aiModalBg.style.display = 'block';
  }
  function closeAiModal() {
    aiModal.style.display = 'none';
    aiModalBg.style.display = 'none';
  }

  aiFab.addEventListener('click', openAi);
  aiModalBg.addEventListener('click', closeAiModal);
  closeAi.addEventListener('click', closeAiModal);
</script>

</body>
</html>
"""

def render_page(content_html, title="CareerInn"):
    return render_template_string(BASE_HTML, content=content_html, title=title)

# -------------------- Helper: subscription --------------------
def user_is_subscribed(user_id):
    if not user_id:
        return False
    db = get_db()
    sub = db.query(Subscription).filter_by(user_id=user_id).first()
    db.close()
    return bool(sub and sub.active)

# -------------------- ADMIN PANEL (START) --------------------
def is_admin():
    return session.get("is_admin") == True

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if is_admin():
        return redirect("/admin")
    message = ""
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        try:
            authenticated = check_password_hash(ADMIN_PASSWORD_HASH, password)
        except Exception:
             authenticated = (ADMIN_PASSWORD_HASH == password) # Fallback if hash generation failed

        if username == ADMIN_USERNAME and authenticated:
            session["is_admin"] = True
            return redirect("/admin")
        else:
            message = "Invalid credentials."
    
    login_form = f"""
    <div class="max-w-md mx-auto mt-10">
      <form method="POST" class="auth-card">
        <h2 class="text-xl font-bold mb-4">Admin Login</h2>
        <p class="text-red-400 text-sm mb-3">{message}</p>
        <input name="username" placeholder="Username" required class="input-box">
        <input name="password" type="password" placeholder="Password" required class="input-box">
        <button class="submit-btn">Login</button>
        <p class="text-gray-400 mt-3 text-sm">Default credentials (check Render vars): {ADMIN_USERNAME} / your_admin_password</p>
      </form>
    </div>
    """
    return render_page(login_form, "Admin Login")

@app.route("/admin/logout")
def admin_logout():
    session.pop("is_admin", None)
    return redirect("/")

@app.route("/admin")
def admin_panel():
    if not is_admin():
        return redirect("/admin/login")
    
    db = get_db()
    hosp_colleges = db.query(College).all()
    btech_colleges = db.query(BtechCourse).all()
    hosp_jobs = db.query(Job).all()
    btech_jobs = db.query(BtechJob).all()
    mentors = db.query(Mentor).all()
    users = db.query(User).all()
    db.close()

    def render_admin_card(title, data, entity_type, *headers):
        list_items = ""
        for item in data[:5]:
            if entity_type == "college":
                details = f"({item.location}, ₹{item.fees:,}, {item.rating}★)"
            elif entity_type == "btech_course":
                details = f"({item.location}, ₹{item.fees:,}, {item.rating}★, {item.specialization})"
            elif entity_type == "job":
                details = f"({item.company}, {item.salary})"
            elif entity_type == "btech_job":
                details = f"({item.company}, {item.package})"
            elif entity_type == "mentor":
                details = f"({item.speciality})"
            elif entity_type == "user":
                details = f"({item.email})"
            else:
                details = ""
            name = getattr(item, 'name', None) or getattr(item, 'title', None)
            list_items += f"<li class='text-xs text-slate-300 truncate'>{name} {details}</li>"

        return f"""
        <div class="support-box">
            <h3 class="font-bold text-lg mb-3">{title} ({len(data)})</h3>
            <ul class="list-disc ml-5 space-y-1">{list_items}</ul>
            <a href="/admin/{entity_type}/add" class="mt-4 px-3 py-1 text-xs bg-emerald-600 rounded inline-block">Add New</a>
        </div>
        """

    content = f"""
    <h1 class="text-3xl font-bold mb-6">Admin Panel</h1>
    <a href="/admin/logout" class="px-3 py-1.5 rounded-full bg-rose-600 text-xs font-semibold mb-6 inline-block">Admin Logout</a>

    <div class="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
        {render_admin_card("Hospitality Colleges", hosp_colleges, "college")}
        {render_admin_card("B.Tech Colleges", btech_colleges, "btech_course")}
        {render_admin_card("Hospitality Jobs", hosp_jobs, "job")}
        {render_admin_card("B.Tech Jobs", btech_jobs, "btech_job")}
        {render_admin_card("Mentors", mentors, "mentor")}
        {render_admin_card("Users", users, "user")}
    </div>
    """
    return render_page(content, "Admin Panel")

@app.route("/admin/<entity_type>/add", methods=["GET", "POST"])
def admin_add(entity_type):
    if not is_admin(): return redirect("/admin/login")
    
    if request.method == "POST":
        db = get_db()
        try:
            if entity_type == "college":
                db.add(College(name=request.form["name"], location=request.form["location"], fees=int(request.form["fees"]), course=request.form["course"], rating=float(request.form["rating"])))
            elif entity_type == "btech_course":
                db.add(BtechCourse(name=request.form["name"], location=request.form["location"], fees=int(request.form["fees"]), specialization=request.form["specialization"], rating=float(request.form["rating"])))
            elif entity_type == "job":
                db.add(Job(title=request.form["title"], company=request.form["company"], location=request.form["location"], salary=request.form["salary"]))
            elif entity_type == "btech_job":
                db.add(BtechJob(title=request.form["title"], company=request.form["company"], location=request.form["location"], package=request.form["package"]))
            elif entity_type == "mentor":
                db.add(Mentor(name=request.form["name"], experience=request.form["experience"], speciality=request.form["speciality"]))
            db.commit()
            return redirect("/admin")
        except Exception as e:
            db.rollback()
            return render_page(f"<p class='text-red-400'>Error saving data: {e}</p>", "Admin Error")
        finally:
            db.close()

    form_fields = ""
    if entity_type == "college":
        form_fields = """
            <input name="name" placeholder="College Name (Hosp.)" required class="input-box">
            <input name="location" placeholder="Location" required class="input-box">
            <input name="fees" type="number" placeholder="Annual Fees (e.g., 320000)" required class="input-box">
            <input name="course" placeholder="Key Course (e.g., BSc in Hospitality)" required class="input-box">
            <input name="rating" type="number" step="0.1" placeholder="Rating (e.g., 4.6)" required class="input-box">
        """
    elif entity_type == "btech_course":
        form_fields = """
            <input name="name" placeholder="College Name (B.Tech)" required class="input-box">
            <input name="location" placeholder="Location" required class="input-box">
            <input name="fees" type="number" placeholder="Annual Fees (e.g., 220000)" required class="input-box">
            <input name="specialization" placeholder="Specialization (e.g., CSE or ECE)" required class="input-box">
            <input name="rating" type="number" step="0.1" placeholder="Rating (e.g., 4.8)" required class="input-box">
        """
    elif entity_type == "job":
        form_fields = """
            <input name="title" placeholder="Job Title (Hosp.)" required class="input-box">
            <input name="company" placeholder="Company/Recruiter" required class="input-box">
            <input name="location" placeholder="Location" required class="input-box">
            <input name="salary" placeholder="Avg Package/Salary (e.g., ~₹4.5–5.5 LPA)" required class="input-box">
        """
    elif entity_type == "btech_job":
        form_fields = """
            <input name="title" placeholder="Job Title (B.Tech SDE/DA)" required class="input-box">
            <input name="company" placeholder="Company/Recruiter" required class="input-box">
            <input name="location" placeholder="Location" required class="input-box">
            <input name="package" placeholder="Avg Package/Salary (e.g., ~₹15–25 LPA)" required class="input-box">
        """
    elif entity_type == "mentor":
        form_fields = """
            <input name="name" placeholder="Mentor Name" required class="input-box">
            <textarea name="experience" rows="3" placeholder="Experience summary..." class="input-box h-auto" required></textarea>
            <input name="speciality" placeholder="Speciality (e.g., CSE, Culinary, Front Office)" required class="input-box">
        """
    else:
        return redirect("/admin")
    
    content = f"""
    <h2 class="text-2xl font-bold mb-4">Add New {entity_type.replace('_', ' ').title()}</h2>
    <form method="POST" class="space-y-3">
        {form_fields}
        <button class="submit-btn">Add {entity_type.title()}</button>
    </form>
    """
    return render_page(content, f"Add {entity_type.title()}")
# -------------------- ADMIN PANEL (END) --------------------


# -------------------- HOME (Integrated Hosp & Tech Cards) --------------------
@app.route("/")
def home():
    ai_used = False
    user_id = session.get("user_id")
    logged_in = bool(user_id)

    if user_id:
        db = get_db()
        usage = db.query(AiUsage).filter_by(user_id=user_id).first()
        db.close()
        if usage and usage.ai_used >= 1:
            ai_used = True
            session["ai_used"] = True

    # CTA logic (logged-in vs not) - kept original logic
    if not ai_used:
        if logged_in:
            cta_html = """
              <div class="flex flex-wrap items-center gap-3 mt-3">
                <a href="/dashboard" class="primary-cta">🚀 Get started – ₹299 / year</a>
                <a href="/chatbot" class="px-4 py-2 rounded-full border border-emerald-400/70 text-xs md:text-sm hover:bg-emerald-500/10">🤖 Use your free AI career chat</a>
              </div>
              <p class="hero-footnote">You are logged in. You still have one free AI chat. After that, guidance continues inside the ₹299/year pass.</p>
            """
        else:
            cta_html = """
              <div class="flex flex-wrap items-center gap-3 mt-3">
                <a href="/signup" class="primary-cta">Create free account</a>
                <a href="/login" class="ghost-cta">Sign in</a>
                <a href="/chatbot" class="px-4 py-2 rounded-full border border-emerald-400/70 text-xs md:text-sm hover:bg-emerald-500/10">🤖 Try free AI career chat</a>
              </div>
              <p class="hero-footnote">First AI chat is free after login. After that, guidance continues inside the ₹299/year pass.</p>
            """
    else:
        cta_html = """
              <div class="flex flex-wrap items-center gap-4 mt-3">
                <a href="/subscribe" class="primary-cta">🚀 Get started – ₹299 / year</a>
                <a href="/login" class="ghost-cta">Already have an account?</a>
                <a href="/chatbot" class="px-4 py-2 rounded-full border border-emerald-400/70 text-xs md:text-sm hover:bg-emerald-500/10">🤖 Continue with AI guidance</a>
              </div>
              <p class="hero-footnote">₹299 per student (prototype – real data & payments can plug in later).</p>
            """

    content = f"""
    <div class="max-w-5xl mx-auto mt-6 md:mt-10 space-y-8 hero-shell">
      <section class="grid md:grid-cols-2 gap-10 items-center">
        <div class="space-y-4">
          <span class="pill-badge"><span class="dot"></span>Hospitality & Tech Careers · CareerInn</span>
          <h1 class="text-3xl md:text-4xl font-extrabold leading-tight">Plan your <span class="gradient-text">Hospitality or B.Tech</span> career path.</h1>
          <p class="text-sm md:text-[15px] text-slate-300">One simple yearly pass that puts colleges, mentors, jobs and an AI career guide in a single platform, serving both hotel management and B.Tech students.</p>
          {cta_html}
        </div>
        <div class="hero-card rounded-3xl p-7 md:p-9 space-y-5">
          <p class="text-sm text-slate-300 uppercase tracking-[0.22em]">Student pass</p>
          <div class="flex items-end gap-3">
            <span class="text-5xl font-extrabold text-emerald-300">₹299</span>
            <span class="text-sm text-slate-300 mb-2">per student / year</span>
          </div>
          <p class="text-[13px] md:text-sm text-slate-300">Students can explore careers, compare colleges, and get mentor & AI guidance in one simple space.</p>
        </div>
      </section>

      <section class="space-y-4">
        <h3 class="text-sm font-semibold text-slate-200">CareerInn Spaces:</h3>
        <div class="grid gap-4 md:grid-cols-3 lg:grid-cols-6">
          <a href="/courses" class="feature-card">🏨 Hosp. Courses<p class="sub">See key hospitality courses.</p></a>
          <a href="/btech-colleges" class="feature-card">💻 B.Tech Colleges<p class="sub">Hyderabad B.Tech colleges & specializations.</p></a> 
          <a href="/colleges" class="feature-card">🏫 Hosp. Colleges<p class="sub">Hyderabad hotel-management colleges.</p></a>
          <a href="/jobs" class="feature-card">💼 Hosp. Jobs<p class="sub">Hosp. avg packages & recruiters.</p></a>
          <a href="/btech-jobs" class="feature-card">⚙️ B.Tech Jobs<p class="sub">Tech avg packages & roles.</p></a> 
          <a href="/chatbot" class="feature-card">🤖 AI Career Bot<p class="sub">Chat to get a suggested path.</p></a>
        </div>
      </section>

      <section class="grid md:grid-cols-3 gap-4 mt-6">
        <div class="support-box">
          <h3 class="font-semibold mb-2">Top Skills (quick)</h3>
          <p class="text-sm text-slate-300">Free preview of important career skills. Subscribe to edit and get custom suggestions.</p>
          <div class="mt-3"><a href="/dashboard?tab=skills" class="px-3 py-2 rounded-full bg-indigo-600">View Skills</a></div>
        </div>

        <div class="support-box">
          <h3 class="font-semibold mb-2">Mock Interviews</h3>
          <p class="text-sm text-slate-300">Practice roleplay interviews (Hosp. or Tech). Subscribe to unlock AI mock interviewer and full practice list.</p>
          <div class="mt-3"><a href="/mock-interviews" class="px-3 py-2 rounded-full bg-emerald-500">Open Mock Interviews</a></div>
        </div>

        <div class="support-box">
          <h3 class="font-semibold mb-2">Previous Year Papers</h3>
          <p class="text-sm text-slate-300">Curated past papers (NCHM/JEE) from official sources (view-only).</p>
          <div class="mt-3"><a href="/prev-papers" class="px-3 py-2 rounded-full bg-indigo-600">View Papers</a></div>
        </div>
      </section>
    </div>
    """
    return render_page(content, "CareerInn | Home (Hosp & Tech)")

# -------------------- COURSES (Hospitality) --------------------
@app.route("/courses")
def courses():
    db = get_db()
    data = db.query(College.course).distinct().all()
    db.close()
    rows = ""
    for c in data:
        course_name = c[0] if isinstance(c, (list, tuple)) else c
        rows += f"<tr><td>{course_name}</td></tr>"
    if not rows:
        rows = "<tr><td>No hospitality courses found yet.</td></tr>"
    content = f"""
    <h2 class="text-3xl font-bold mb-4">Hospitality & Hotel Management Courses</h2>
    <p class="text-sm text-slate-300 mb-3">Below are example courses offered by different hotel-management colleges in and around Hyderabad.</p>
    <table class="table mt-2"><tr><th>Course</th></tr>{rows}</table>
    """
    return render_page(content, "Hosp. Courses")

# -------------------- COLLEGES (Hospitality) --------------------
@app.route("/colleges")
def colleges():
    budget = request.args.get("budget", "").strip()
    rating_min = request.args.get("rating", "").strip()
    db = get_db()
    query = db.query(College)
    if budget == "lt1": query = query.filter(College.fees < 100000)
    elif budget == "b1_2": query = query.filter(College.fees.between(100000, 200000))
    elif budget == "b2_3": query = query.filter(College.fees.between(200000, 300000))
    elif budget == "gt3": query = query.filter(College.fees > 300000)
    if rating_min:
        try:
            rating_val = float(rating_min)
            query = query.filter(College.rating >= rating_val)
        except ValueError:
            pass
    data = query.order_by(College.rating.desc()).all()
    db.close()
    rows = ""
    for col in data:
        rows += f"<tr><td>{col.name}</td><td>{col.course}</td><td>{col.location}</td><td>₹{col.fees:,}</td><td>{col.rating:.1f}★</td></tr>"
    if not rows:
        rows = "<tr><td colspan='5'>No colleges match this budget / rating yet.</td></tr>"
    sel_any_b = "selected" if budget == "" else ""
    sel_lt1   = "selected" if budget == "lt1" else ""
    sel_b1_2  = "selected" if budget == "b1_2" else ""
    sel_b2_3  = "selected" if budget == "b2_3" else ""
    sel_gt3   = "selected" if budget == "gt3" else ""
    sel_r_any = "selected" if rating_min == "" else ""
    sel_r_35  = "selected" if rating_min == "3.5" else ""
    sel_r_40  = "selected" if rating_min == "4.0" else ""
    sel_r_45  = "selected" if rating_min == "4.5" else ""
    content = f"""
    <h2 class="text-3xl font-bold mb-4">Hyderabad Hotel Management – Colleges</h2>
    <form method="GET" class="mb-3 grid md:grid-cols-3 gap-3 items-center">
      <select name="budget" class="search-bar">
        <option value="" {sel_any_b}>Any budget</option>
        <option value="lt1" {sel_lt1}>Below ₹1,00,000</option>
        <option value="b1_2" {sel_b1_2}>₹1,00,000 – ₹2,00,000</option>
        <option value="b2_3" {sel_b2_3}>₹2,00,000 – ₹3,00,000</option>
        <option value="gt3" {sel_gt3}>Above ₹3,00,000</option>
      </select>
      <select name="rating" class="search-bar">
        <option value="" {sel_r_any}>Any rating</option>
        <option value="3.5" {sel_r_35}>3.5★ &amp; above</option>
        <option value="4.0" {sel_r_40}>4.0★ &amp; above</option>
        <option value="4.5" {sel_r_45}>4.5★ &amp; above</option>
      </select>
      <button class="px-3 py-2 bg-indigo-600 rounded text-sm">Filter</button>
    </form>
    <table class="table mt-2"><tr><th>College</th><th>Key Course</th><th>Location</th><th>Approx. Annual Fees</th><th>Rating</th></tr>{rows}</table>
    """
    return render_page(content, "Hosp. Colleges")

# -------------------- B.TECH COLLEGES (NEW) --------------------
@app.route("/btech-colleges")
def btech_colleges():
    budget = request.args.get("budget", "").strip()
    rating_min = request.args.get("rating", "").strip()
    specialization = request.args.get("specialization", "").strip()
    
    db = get_db()
    query = db.query(BtechCourse)
    
    if budget == "lt1": query = query.filter(BtechCourse.fees < 100000)
    elif budget == "b1_2": query = query.filter(BtechCourse.fees.between(100000, 200000))
    elif budget == "b2_3": query = query.filter(BtechCourse.fees.between(200000, 300000))
    elif budget == "gt3": query = query.filter(BtechCourse.fees > 300000)
    
    if rating_min:
        try:
            rating_val = float(rating_min)
            query = query.filter(BtechCourse.rating >= rating_val)
        except ValueError:
            pass

    if specialization:
        query = query.filter(BtechCourse.specialization.like(f"%{specialization}%"))

    data = query.order_by(BtechCourse.rating.desc()).all()
    db.close()
    
    rows = ""
    for col in data:
        rows += f"<tr><td>{col.name}</td><td>{col.specialization}</td><td>{col.location}</td><td>₹{col.fees:,}</td><td>{col.rating:.1f}★</td></tr>"
    if not rows:
        rows = "<tr><td colspan='5'>No B.Tech colleges match this filter yet.</td></tr>"

    sel_any_b = "selected" if budget == "" else ""
    sel_r_any = "selected" if rating_min == "" else ""

    content = f"""
    <h2 class="text-3xl font-bold mb-4">Hyderabad B.Tech – Colleges & Courses</h2>
    <form method="GET" class="mb-3 grid md:grid-cols-4 gap-3 items-center">
        <select name="budget" class="search-bar">
            <option value="" {sel_any_b}>Any budget</option>
            <option value="lt1">Below ₹1,00,000</option>
            <option value="b1_2">₹1,00,000 – ₹2,00,000</option>
            <option value="b2_3">₹2,00,000 – ₹3,00,000</option>
            <option value="gt3">Above ₹3,00,000</option>
        </select>
        <select name="rating" class="search-bar">
            <option value="" {sel_r_any}>Any rating</option>
            <option value="4.0">4.0★ &amp; above</option>
            <option value="4.5">4.5★ &amp; above</option>
        </select>
        <input name="specialization" placeholder="E.g. CSE or ECE" class="search-bar" value="{specialization}">
        <button class="px-3 py-2 bg-indigo-600 rounded text-sm">Filter</button>
    </form>
    <table class="table mt-2"><tr><th>College</th><th>Key Specialization</th><th>Location</th><th>Approx. Annual Fees</th><th>Rating</th></tr>{rows}</table>
    """
    return render_page(content, "B.Tech Colleges")


# -------------------- JOBS (Hospitality) --------------------
@app.route("/jobs")
def jobs():
    db = get_db()
    data = db.query(Job).all()
    db.close()
    cards = ""
    for j in data:
        cards += f"""
        <div class="job-card">
          <h3 class="font-bold text-sm md:text-base mb-1"><a href="/jobs/{j.id}" class="hover:underline">{j.title}</a></h3>
          <p class="text-indigo-300 text-xs md:text-sm">Top recruiter: {j.company}</p>
          <p class="text-gray-400 text-xs md:text-sm">Location: {j.location}</p>
          <p class="text-green-300 font-semibold text-xs md:text-sm mt-1">{j.salary}</p>
        </div>
        """
    content = f"""
    <h2 class="text-3xl font-bold mb-4">Hospitality Placements & Recruiters Snapshot</h2>
    <div class="grid md:grid-cols-3 gap-6">{cards}</div>
    """
    return render_page(content, "Hosp. Jobs")

@app.route("/jobs/<int:job_id>")
def job_detail(job_id):
    db = get_db()
    job = db.query(Job).get(job_id)
    db.close()
    if not job:
        return redirect("/jobs")
    content = f"""
    <h2 class="text-2xl font-bold mb-3">{job.title}</h2>
    <p class="text-sm text-slate-300 mb-2">Company: <span class="text-indigo-300">{job.company}</span></p>
    <p class="text-sm text-slate-300 mb-2">Location: {job.location}</p>
    <p class="text-sm text-emerald-300 mb-4">Package / Salary: {job.salary}</p>
    <a href="/jobs" class="px-3 py-1 rounded-full bg-indigo-600">Back to jobs</a>
    """
    return render_page(content, "Job detail")


# -------------------- B.TECH JOBS (NEW) --------------------
@app.route("/btech-jobs")
def btech_jobs():
    db = get_db()
    data = db.query(BtechJob).all()
    db.close()
    cards = ""
    for j in data:
        # Note: BtechJob uses 'package' instead of 'salary'
        cards += f"""
        <div class="job-card">
          <h3 class="font-bold text-sm md:text-base mb-1">{j.title}</h3>
          <p class="text-indigo-300 text-xs md:text-sm">Recruiter: {j.company}</p>
          <p class="text-gray-400 text-xs md:text-sm">Location: {j.location}</p>
          <p class="text-green-300 font-semibold text-xs md:text-sm mt-1">Avg package: {j.package}</p>
        </div>
        """
    content = f"""
    <h2 class="text-3xl font-bold mb-4">B.Tech Placements & Recruiters Snapshot</h2>
    <div class="grid md:grid-cols-3 gap-6">{cards}</div>
    """
    return render_page(content, "B.Tech Jobs & Placements")


# -------------------- MENTORSHIP (subscription locked) --------------------
@app.route("/mentorship")
def mentorship():
    user_id = session.get("user_id")
    if not user_is_subscribed(user_id):
        content = """
        <h2 class="text-3xl font-bold mb-4">Find Mentors</h2>
        <p class="text-sm text-slate-300 mb-4">Mentorship is available to subscribed users only. Mentors cover both hospitality and tech domains.</p>
        <a href="/subscribe" class="px-4 py-2 bg-indigo-600 rounded">Subscribe to unlock</a>
        """
        return render_page(content, "Mentorship")
    db = get_db()
    data = db.query(Mentor).all()
    db.close()
    cards = ""
    for m in data:
        cards += f"<div class='mentor-card'><h3 class='text-lg font-bold mb-1'>{m.name}</h3><p class='text-sm text-gray-300'>{m.experience}</p><p class='text-sm text-indigo-300 mb-2'>{m.speciality}</p></div>"
    return render_page(f"<h2 class='text-3xl font-bold mb-4'>Find Mentors</h2><div class='grid md:grid-cols-3 gap-6'>{cards}</div>", "Mentorship")


# -------------------- Mock Interviews (subscription gated) --------------------
@app.route("/mock-interviews", methods=["GET", "POST"])
def mock_interviews():
    user_id = session.get("user_id")
    if not user_is_subscribed(user_id):
        content = """
        <h2 class="text-3xl font-bold mb-4">Mock Interviews & Practice</h2>
        <p class="text-sm text-slate-300 mb-4">Mock interview resources (Hosp. & Tech) are available to subscribed users only.</p>
        <a href="/subscribe" class="px-4 py-2 bg-indigo-600 rounded">Subscribe to unlock</a>
        """
        return render_page(content, "Mock Interviews (Locked)")

    db = get_db()
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        notes = request.form.get("notes", "").strip()
        link = request.form.get("link", "").strip()
        if title:
            db.add(MockInterview(title=title, notes=notes, link=link, uploader_id=user_id))
            db.commit()
            return redirect("/mock-interviews")
    items = db.query(MockInterview).order_by(MockInterview.id.desc()).all()
    db.close()
    cards = ""
    for it in items:
        uploader = " (by you)" if user_id and it.uploader_id == user_id else ""
        cards += f"<div class='support-box'><h3 class='font-semibold mb-1'>{it.title}{uploader}</h3><p class='text-xs text-slate-300 mb-2'>{it.notes or ''}</p>{(f'<a href=\"{it.link}\" target=\"_blank\" class=\"text-indigo-300 text-sm underline\">Open resource</a>' if it.link else '')}</div>"
    content = f"""
    <h2 class="text-3xl font-bold mb-4">Mock Interviews & Practice (Hosp. & Tech)</h2>
    <p class="text-sm text-slate-300 mb-4">Practice mock interviews for both hospitality and technical roles. You can also use the AI Mock Interview Bot below.</p>
    <form method="POST" class="mb-4 space-y-2">
      <input name="title" placeholder="Title (eg: Technical Interview - DSA Basics)" class="input-box" required>
      <input name="link" placeholder="Video / doc link (optional)" class="input-box">
      <textarea name="notes" rows="3" placeholder="Short notes..." class="input-box h-auto"></textarea>
      <button class="px-4 py-2 rounded-full bg-indigo-600">Add mock interview</button>
    </form>
    <div class="mb-4"><a href="/mock-interviews/ai" class="px-4 py-2 bg-emerald-500 rounded">Start AI Mock Interview</a></div>
    <div class="grid md:grid-cols-2 gap-4">{cards}</div>
    """
    return render_page(content, "Mock Interviews")

@app.route("/mock-interviews/ai", methods=["GET", "POST"])
def mock_interview_ai():
    user_id = session.get("user_id")
    if not user_is_subscribed(user_id):
        return render_page("<p class='text-sm text-slate-300'>AI Mock Interview requires subscription. <a href='/subscribe' class='text-indigo-300'>Subscribe</a></p>", "Mock Interview Bot")
    history = session.get("mock_ai_history", [])
    if request.method == "POST":
        user_msg = request.form.get("message", "").strip()
        if user_msg:
            history.append({"role":"user","content":user_msg})
            # System prompt updated to cover both domains
            messages = [{"role":"system","content":"You are an AI mock interviewer for hospitality and B.Tech roles. Ask scenario questions, give technical questions, and provide constructive feedback."}] + history
            groq_client = get_groq_client()
            if groq_client is None:
                reply = "AI not configured. Please set GROQ_API_KEY."
            else:
                try:
                    resp = groq_client.chat.completions.create(model="llama-3.1-8b-instant", messages=messages, temperature=0.7)
                    reply = resp.choices[0].message.content
                except Exception as e:
                    reply = f"AI error: {e}"
            history.append({"role":"assistant","content":reply})
            session["mock_ai_history"] = history
    # render chat
    html = "<div class='max-w-3xl mx-auto space-y-6'><h1 class='text-2xl font-bold'>AI Mock Interview</h1><div class='bg-slate-900/80 border border-slate-700 rounded-2xl p-4 h-[320px] overflow-y-auto mb-4'>"
    for m in history:
        who = "You" if m["role"]=="user" else "Interviewer"
        html += f"<div class='mb-3'><div class='text-xs text-slate-400 mb-0.5'>{who}</div><div class='inline-block px-3 py-2 rounded-2xl {'bg-indigo-600' if m['role']=='user' else 'bg-slate-800'} text-xs md:text-sm max-w-[90%]'>{m['content']}</div></div>"
    html += "</div><form method='POST' class='flex gap-2'><input name='message' autocomplete='off' placeholder='Start by stating your target role (e.g. Front Office or SDE)...' class='flex-1 input-box' required><button class='px-4 py-2 rounded-full bg-indigo-600 hover:bg-indigo-500 text-sm font-semibold'>Send</button></form></div>"
    return render_page(html, "AI Mock Interview")


# -------------------- Previous Papers --------------------
@app.route("/prev-papers")
def prev_papers():
    db = get_db()
    items = db.query(PrevPaper).order_by(PrevPaper.year.desc()).all()
    db.close()
    rows = ""
    for p in items:
        if p.is_upload and p.link:
            link_html = f"<a href='/uploads/{p.link}' target='_blank' class='text-indigo-300 underline'>Open PDF</a>"
        elif p.link:
            link_html = f"<a href='{p.link}' target='_blank' class='text-indigo-300 underline'>Open</a>"
        else:
            link_html = ""
        rows += f"<tr><td>{p.title}</td><td>{p.year or ''}</td><td>{link_html}</td></tr>"
    if not rows:
        rows = "<tr><td colspan='3'>No papers yet.</td></tr>"
    content = f"""
    <h2 class="text-3xl font-bold mb-4">Previous Year Question Papers (view-only)</h2>
    <p class="text-sm text-slate-300 mb-4">Curated past papers and official resources for both NCHM JEE and B.Tech entrance exams.</p>
    <table class="table mt-2"><tr><th>Title</th><th>Year</th><th>Link</th></tr>{rows}</table>
    """
    return render_page(content, "Previous Year Papers")

@app.route("/uploads/<path:filename>")
def uploaded_file(filename):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename, as_attachment=False)

# -------------------- GLOBAL MATCH (locked) --------------------
@app.route("/global-match")
def global_match():
    user_id = session.get("user_id")
    if not user_is_subscribed(user_id):
        content = """
        <h2 class="text-3xl font-bold mb-4">Global College & Internship Match</h2>
        <p class="text-sm text-slate-300 mb-4">Global matching info is for subscribed users. Subscribe to unlock guidance on abroad options for both Hospitality and Master's (Tech) degrees.</p>
        <a href="/subscribe" class="px-4 py-2 bg-indigo-600 rounded">Subscribe to unlock</a>
        """
        return render_page(content, "Global Match (Locked)")
    content = """
    <h2 class="text-3xl font-bold mb-4">Global College & Internship Match</h2>
    <p class="text-gray-300 mb-4 text-sm">Advice for students looking at abroad options after their base degree/diploma, covering both streams.</p>
    <div class="grid md:grid-cols-3 gap-5 mb-6">
      <div class="support-box"><h3 class="font-semibold mb-2">Hospitality Destinations</h3><ul class="text-sm text-slate-200"><li>Switzerland (Top M.Sc)</li><li>UAE (Luxury Jobs)</li><li>Canada (Immigration path)</li></ul></div>
      <div class="support-box"><h3 class="font-semibold mb-2">Tech Masters (MS) Options</h3><ul class="text-sm text-slate-200"><li>USA (CS/Data Science)</li><li>Germany (Engineering)</li><li>Canada (IT/AI)</li></ul></div>
      <div class="support-box"><h3 class="font-semibold mb-2">Typical Requirements</h3><ul class="text-sm text-slate-200"><li>Good English (IELTS/TOEFL)</li><li>Strong SOP/LORs</li><li>GMAT/GRE (for Masters)</li></ul></div>
    </div>
    """
    return render_page(content, "Global Match")

# -------------------- Chatbot and AI flows --------------------
CHATBOT_HTML = """
<div class="max-w-3xl mx-auto space-y-6">
  <h1 class="text-3xl font-bold mb-2">CareerInn AI Mentor</h1>
  {% if not locked %}
    <p class="text-sm text-slate-300 mb-4">This AI bot will ask about your goals, marks, and interests. You get <b>one free full chat session.</b></p>
  {% else %}
    <p class="text-sm text-slate-300 mb-4">Your <b>free AI career chat is finished</b> for this account. Please purchase the ₹299/year Student Pass and connect with a mentor for more guidance.</p>
  {% endif %}
  <form method="GET" action="/chatbot" class="mb-3"><input type="hidden" name="reset" value="1"><button class="px-3 py-1 rounded-full border border-slate-600 text-[11px] hover:bg-slate-800">🔄 Clear chat on screen</button></form>
  <div class="bg-slate-900/80 border border-slate-700 rounded-2xl p-4 h-[320px] overflow-y-auto mb-4">
    {% if history %}
      {% for m in history %}
        <div class="mb-3">
          {% if m.role == 'user' %}
            <div class="text-xs text-slate-400 mb-0.5">You</div>
            <div class="inline-block px-3 py-2 rounded-2xl bg-indigo-600 text-xs md:text-sm max-w-[90%]">{{ m.content }}</div>
          {% else %}
            <div class="text-xs text-slate-400 mb-0.5">CareerInn AI</div>
            <div class="inline-block px-3 py-2 rounded-2xl bg-slate-800 text-xs md:text-sm max-w-[90%]">{{ m.content }}</div>
          {% endif %}
        </div>
      {% endfor %}
    {% else %}
      <p class="text-sm text-slate-400">👋 Hi! I’m CareerInn AI. Tell me your name, which stream you are interested in (Hospitality or B.Tech), and your latest marks.</p>
    {% endif %}
  </div>
  {% if not locked %}
    <form method="POST" class="flex gap-2">
      <input name="message" autocomplete="off" placeholder="Type your message here..." class="flex-1 input-box" required>
      <button class="px-4 py-2 rounded-full bg-indigo-600 hover:bg-indigo-500 text-sm font-semibold">Send</button>
    </form>
    <form method="POST" action="/chatbot/end" class="mt-3"><button class="px-3 py-1.5 text-[11px] rounded-full border border-rose-500/70 text-rose-200 hover:bg-rose-500/10">🔒 End &amp; lock free AI chat</button></form>
  {% else %}
    <p class="text-xs text-slate-400 mt-2">Tip: Go back to the Home page to see the Student Pass and connect with mentors.</p>
  {% endif %}
</div>
"""

@app.route("/chatbot", methods=["GET", "POST"])
def chatbot():
    user_id = session.get("user_id")
    if not user_id:
        return redirect("/login")
    db = get_db()
    usage = db.query(AiUsage).filter_by(user_id=user_id).first()
    locked = bool(usage and usage.ai_used == 1 and not user_is_subscribed(user_id))
    
    if request.args.get("reset") == "1":
        session["ai_history"] = []
        db.close()
        return redirect("/chatbot")
        
    history = session.get("ai_history", [])
    if not isinstance(history, list):
        history = []
    session["ai_history"] = history
    
    if request.method == "POST":
        if locked:
            history.append({"role":"assistant","content":"⚠ Your free AI career chat session has ended and subscription is required to continue.\nPlease check the Student Pass (₹299/year) on the home page."})
            session["ai_history"] = history
            db.close()
            html = render_template_string(CHATBOT_HTML, history=history, locked=True)
            return render_page(html, "CareerInn AI Mentor")
            
        user_msg = request.form.get("message", "").strip()
        if user_msg:
            history.append({"role":"user","content":user_msg})
            messages = [{"role":"system","content":AI_SYSTEM_PROMPT}] + history
            groq_client = get_groq_client()
            if groq_client is None:
                reply = "AI is not configured yet. Please set GROQ_API_KEY."
            else:
                try:
                    resp = groq_client.chat.completions.create(model="llama-3.1-8b-instant", messages=messages, temperature=0.7)
                    reply = resp.choices[0].message.content
                except Exception as e:
                    reply = f"AI error: {e}"
                    
            history.append({"role":"assistant","content":reply})
            session["ai_history"] = history
            
    db.close()
    html = render_template_string(CHATBOT_HTML, history=history, locked=locked)
    return render_page(html, "CareerInn AI Mentor")

# Note: The /finish route is removed as /chatbot/end handles the same function more gracefully.

@app.route("/chatbot/end", methods=["POST"])
def end_chatbot():
    user_id = session.get("user_id")
    if not user_id:
        return redirect("/login")
    db = get_db()
    try:
        usage = db.query(AiUsage).filter_by(user_id=user_id).first()
        if usage is None:
            usage = AiUsage(user_id=user_id, ai_used=1)
            db.add(usage)
        else:
            usage.ai_used = 1
        db.commit()
    finally:
        db.close()
    session["ai_history"] = []
    session["ai_used"] = True
    return redirect("/chatbot")

# -------------------- AUTH (signup/login/forgot) --------------------
SIGNUP_FORM = """
<form method="POST" class="auth-card">
  <h2 class="text-xl font-bold mb-4">Create your CareerInn account</h2>
  <input name="name" placeholder="Full Name" required class="input-box">
  <input name="email" placeholder="Email" required class="input-box">
  <input name="password" type="password" placeholder="Password" required class="input-box">
  <button class="submit-btn">Signup</button>
  <p class="text-gray-400 mt-3 text-sm">Already registered? <a href="/login" class="text-indigo-400">Login</a></p>
</form>
"""

LOGIN_FORM = """
<form method="POST" class="auth-card">
  <h2 class="text-xl font-bold mb-2">Login to CareerInn</h2>
  <input name="email" placeholder="Email" required class="input-box">
  <input name="password" type="password" placeholder="Password" required class="input-box">
  <button class="submit-btn">Login</button>
  <p class="text-gray-400 mt-3 text-sm">New here? <a href="/signup" class="text-indigo-400">Create Account</a></p>
  <p class="mt-2 text-xs text-slate-400"><a href="/forgot-password" class="text-indigo-300 hover:underline">Forgot Password?</a></p>
</form>
"""

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "").strip()
        if not name or not email or not password:
            return render_page("<p class='text-red-400 text-sm mb-3'>All fields are required.</p>" + SIGNUP_FORM, "Signup")
        db = get_db()
        existing = db.query(User).filter(User.email == email).first()
        if existing:
            db.close()
            return render_page("<p class='text-red-400 text-sm mb-3'>An account with this email already exists. Please login.</p>" + SIGNUP_FORM, "Signup")
        hashed_password = generate_password_hash(password, method="pbkdf2:sha256", salt_length=16)
        user = User(name=name, email=email, password=hashed_password)
        db.add(user)
        db.commit()
        db.close()
        return redirect("/login")
    return render_page(SIGNUP_FORM, "Signup")

@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        db = get_db()
        user = db.query(User).filter(User.email == email).first()
        db.close()
        if user:
            return render_page("<p class='text-emerald-300'>Password-reset link would be sent (demo).</p><p class='mt-2'><a href='/login' class='text-indigo-300'>Back to login</a></p>", "Forgot Password")
        return render_page("<p class='text-red-400'>Email not found.</p>" + FORGOT_FORM, "Forgot Password")
    FORGOT_FORM = """
    <form method="POST" class="auth-card">
      <h2 class="text-xl font-bold mb-4">Forgot Password</h2>
      <input name="email" placeholder="Enter your registered email" required class="input-box">
      <button class="submit-btn">Send reset link (demo)</button>
      <p class="text-gray-400 mt-3 text-sm"><a href="/login" class="text-indigo-400">Back to login</a></p>
    </form>
    """
    return render_page(FORGOT_FORM, "Forgot Password")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "").strip()
        db = get_db()
        user = db.query(User).filter(User.email == email).first()
        db.close()
        authenticated = False
        if user:
            try:
                authenticated = check_password_hash(user.password, password)
            except Exception:
                authenticated = (user.password == password)
        if authenticated:
            session["user"] = user.name
            session["user_id"] = user.id
            session["ai_history"] = []
            if session.get("first_time_login") is None:
                session["first_time_login"] = True
            return redirect("/dashboard")
        return render_page("<p class='text-red-400 text-sm mb-3'>Invalid email or password.</p>" + LOGIN_FORM, "Login")
    return render_page(LOGIN_FORM, "Login")

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

# -------------------- Subscribe (demo) --------------------
@app.route("/subscribe", methods=["GET", "POST"])
def subscribe():
    if "user_id" not in session:
        return redirect("/login")
    user_id = session["user_id"]
    db = get_db()
    sub = db.query(Subscription).filter_by(user_id=user_id).first()
    if request.method == "POST":
        if not sub:
            sub = Subscription(user_id=user_id, active=True)
            db.add(sub)
        else:
            sub.active = True
        db.commit()
        db.close()
        return redirect("/dashboard")
    db.close()
    content = """
    <h2 class="text-2xl font-bold mb-4">Subscribe to CareerInn Student Pass</h2>
    <p class="text-sm text-slate-300 mb-3">Demo payment flow. Click Subscribe to enable locked sections for your account.</p>
    <form method="POST"><button class="px-4 py-2 bg-indigo-600 rounded">Subscribe – ₹299 / year (demo)</button></form>
    """
    return render_page(content, "Subscribe")

# -------------------- DASHBOARD (user workspace) --------------------
@app.route("/dashboard", methods=["GET", "POST"])
def dashboard():
    if "user_id" not in session:
        return redirect("/login")
    user_id = session["user_id"]
    user_name = session["user"]
    tab = request.args.get("tab")
    if request.method == "POST":
        tab = request.form.get("tab", tab)
    if not tab:
        tab = "home"

    db = get_db()
    profile = db.query(UserProfile).filter_by(user_id=user_id).first()
    if profile is None:
        profile = UserProfile(user_id=user_id, skills_text="", target_roles="", self_rating=0, resume_link="", notes="")
        db.add(profile)
        db.commit()

    # handle saves (skills/resume)
    if request.method == "POST":
        if tab == "skills" or tab == "skills_add":
            if not user_is_subscribed(user_id):
                db.close()
                return redirect("/dashboard?tab=skills")
            if tab == "skills":
                profile.skills_text = request.form.get("skills_text", "").strip()
                profile.target_roles = request.form.get("target_roles", "").strip()
                rating_val = request.form.get("self_rating", "").strip()
                try:
                    profile.self_rating = int(rating_val) if rating_val else 0
                except ValueError:
                    profile.self_rating = 0
                db.commit()
                db.close()
                return redirect("/dashboard?tab=skills")
            else:
                new_skill = request.form.get("new_skill", "").strip()
                if new_skill:
                    skills_list = [s.strip() for s in (profile.skills_text or "").split(",") if s.strip()]
                    if new_skill not in skills_list:
                        skills_list.append(new_skill)
                        profile.skills_text = ", ".join(skills_list)
                        db.commit()
                db.close()
                return redirect("/dashboard?tab=skills")
        if tab == "resume":
            profile.resume_link = request.form.get("resume_link", "").strip()
            profile.notes = request.form.get("notes", "").strip()
            db.commit()
            db.close()
            return redirect("/dashboard?tab=resume")

    remove_skill = request.args.get("remove_skill")
    if remove_skill:
        if user_is_subscribed(user_id):
            skills_list = [s.strip() for s in (profile.skills_text or "").split(",") if s.strip()]
            skills_list = [s for s in skills_list if s.lower() != remove_skill.strip().lower()]
            profile.skills_text = ", ".join(skills_list)
            db.commit()
        db.close()
        return redirect("/dashboard?tab=skills")

    skills_text = profile.skills_text or ""
    target_roles = profile.target_roles or ""
    self_rating = profile.self_rating or 0
    resume_link = profile.resume_link or ""
    notes = profile.notes or ""
    db.close()

    # Greeting
    if session.get("first_time_login", False):
        greeting = "CareerInn welcomes you 🎉"
        session["first_time_login"] = False
    else:
        greeting = "Welcome back 👋"

    # Prefill skills for subscribed users if empty
    if not skills_text and user_is_subscribed(user_id):
        skills_text = ", ".join([
            "English communication", "Customer service", "Food safety (HACCP basics)", "Table service & etiquette", 
            "Culinary basics", "Python/Java basics", "Data Structures", "POS & billing", "Teamwork", 
            "Time management"
        ])
        db = get_db()
        profile = db.query(UserProfile).filter_by(user_id=user_id).first()
        if profile and not profile.skills_text:
            profile.skills_text = skills_text
            db.commit()
        db.close()

    career_guidance = """
      <div class="bg-slate-900/70 border border-slate-800 rounded-2xl p-4">
        <h3 class="font-semibold mb-2">CareerInn guidance</h3>
        <ul class="text-xs text-slate-300">
          <li>• **Hosp:** Focus on English & grooming for front-office roles.</li>
          <li>• **Tech:** Build projects using Python/Java for SDE roles.</li>
          <li>• Build a 1-page resume highlighting internships & key skills (Hosp. or Tech).</li>
          <li>• Use the AI bot to prepare for interviews and SOPs.</li>
        </ul>
      </div>
    """

    def render_skill_chips(skills_csv):
        skills = [s.strip() for s in skills_csv.split(",") if s.strip()]
        if not skills:
            return "<p class='text-xs text-slate-400'>No skills yet. Add in Skills tab.</p>"
        chips = ""
        for s in skills:
            chips += f"<span class='inline-block px-2 py-1 mr-2 mb-2 rounded-full bg-slate-800 text-xs'>{s}</span>"
        return chips

    home_panel = f"""
      <div class="space-y-4">
        <h2 class="text-2xl md:text-3xl font-bold">{greeting}, {user_name}</h2>
        <p class="text-sm text-slate-300">This is your personal career dashboard. Track your skills, upload your resume link, and see how ready you are for hotel & B.Tech careers.</p>

        <div class="grid md:grid-cols-3 gap-4 mt-4">
          <div class="dash-box"><p class="text-xs text-slate-400">Career readiness rating</p><p class="text-2xl font-bold mt-1">{self_rating}/5</p></div>
          <div class="dash-box"><p class="text-xs text-slate-400">Target roles set</p><p class="text-2xl font-bold mt-1">{"Yes" if target_roles else "No"}</p></div>
          <div class="dash-box"><p class="text-xs text-slate-400">Resume link added</p><p class="text-2xl font-bold mt-1">{"Yes" if resume_link else "No"}</p></div>
        </div>

        <div class="mt-6 bg-slate-900/70 border border-slate-700 rounded-2xl p-4">
          <h3 class="font-semibold mb-2">Top skills (quick view)</h3>
          <div class="mb-3">{render_skill_chips(skills_text)}</div>
          <a href="/dashboard?tab=skills" class="inline-block px-3 py-1 rounded-full border border-indigo-500 text-xs">Edit skills</a>
        </div>

        <div class="mt-4">{career_guidance}</div>
      </div>
    """

    if not user_is_subscribed(user_id):
        mentors_panel = """
          <div class="space-y-4">
            <h2 class="text-2xl md:text-3xl font-bold">Mentor connections 🧑‍🏫</h2>
            <p class="text-sm text-slate-300">This area requires a subscription. Please subscribe to access mentor details and booking (mentors cover both Hosp. and Tech).</p>
            <a href="/subscribe" class="px-4 py-2 bg-indigo-600 rounded text-sm">Subscribe to unlock</a>
          </div>
        """
        skills_panel = """
          <div class="space-y-4">
            <h2 class="text-2xl md:text-3xl font-bold">Skills & strengths ⭐</h2>
            <p class="text-sm text-slate-300">This section requires a subscription. Subscribe to unlock skills editing and suggestions.</p>
            <a href="/subscribe" class="px-4 py-2 rounded-full bg-indigo-600">Subscribe to unlock</a>
          </div>
        """
    else:
        def skills_chips_with_remove(skills_csv):
            skills = [s.strip() for s in skills_csv.split(",") if s.strip()]
            if not skills:
                return "<p class='text-xs text-slate-400'>No skills yet. Add some below.</p>"
            out = "<div class='flex flex-wrap gap-2'>"
            for s in skills:
                out += f"<div class='inline-flex items-center gap-2 px-2 py-1 rounded-full bg-slate-800 text-xs'>{s} <a href='/dashboard?tab=skills&remove_skill={s}' class='ml-2 text-rose-400'>✕</a></div>"
            out += "</div>"
            return out
        skills_panel = f"""
          <div class="space-y-4">
            <h2 class="text-2xl md:text-3xl font-bold">Skills & strengths ⭐</h2>
            <p class="text-xs text-slate-300">Manage skills for Hospitality or B.Tech roles. Separate with commas.</p>
            <div class="mt-3"><label class="block text-xs text-slate-300 mb-1">Your skills (quick chips)</label>{skills_chips_with_remove(skills_text)}</div>
            <form method="POST" action="/dashboard" class="flex gap-2 mt-3">
              <input type="hidden" name="tab" value="skills_add">
              <input name="new_skill" placeholder="Add a skill (e.g. Grooming, Python, DSA)" class="input-box flex-1" />
              <button class="px-3 py-1 rounded-full bg-indigo-600">Add</button>
            </form>
            <form method="POST" class="space-y-4 mt-4">
              <input type="hidden" name="tab" value="skills">
              <div>
                <label class="block text-xs text-slate-300 mb-1">Full skill list (comma-separated)</label>
                <textarea name="skills_text" rows="4" class="input-box h-auto">{skills_text}</textarea>
              </div>
              <div><label class="block text-xs text-slate-300 mb-1">Target roles (e.g., F&B Associate, SDE)</label><textarea name="target_roles" rows="3" class="input-box h-auto">{target_roles}</textarea></div>
              <div class="grid md:grid-cols-2 gap-4 items-center"><div><label class="block text-xs text-slate-300 mb-1">Rate readiness (0–5)</label><input name="self_rating" type="number" min="0" max="5" value="{self_rating}" class="input-box" /></div></div>
              <button class="submit-btn mt-2">Save skills</button>
            </form>
          </div>
        """

    rating_panel = f"""
      <div class="space-y-4">
        <h2 class="text-2xl md:text-3xl font-bold">Career rating overview 📊</h2>
        <p class="text-sm text-slate-300">Your self-assessment. Use the Skills tab to update this rating.</p>
        <div class="mt-4 bg-slate-900/70 border border-slate-700 rounded-2xl p-4">
          <p class="text-xs text-slate-400">Self-rating (0–5)</p>
          <div class="flex items-center gap-3"><div class="flex gap-1">
          {''.join('<span>⭐</span>' for _ in range(self_rating))}
          {''.join('<span class=\"text-slate-600\">⭐</span>' for _ in range(5 - self_rating))}
          </div><span class="text-sm text-slate-200">{self_rating}/5</span></div>
        </div>
      </div>
    """

    resume_panel = f"""
      <div class="space-y-4">
        <h2 class="text-2xl md:text-3xl font-bold">Resume & profile link 📄</h2>
        <form method="POST" class="space-y-4 mt-4">
          <input type="hidden" name="tab" value="resume">
          <div><label class="block text-xs text-slate-300 mb-1">Resume link (Google Drive / GitHub / Portfolio)</label><input name="resume_link" class="input-box" placeholder="https://drive.google.com/..." value="{resume_link}"></div>
          <div><label class="block text-xs text-slate-300 mb-1">Notes for mentor (e.g., which roles you applied for)</label><textarea name="notes" rows="3" class="input-box h-auto">{notes}</textarea></div>
          <button class="submit-btn mt-2">Save resume details</button>
        </form>
        {"<p class='text-xs text-emerald-300 mt-2'>Current resume link: <a href='" + resume_link + "' target='_blank' class='underline'>" + resume_link + "</a></p>" if resume_link else ""}
      </div>
    """

    faqs_panel = """
      <div class="space-y-4">
        <h2 class="text-2xl md:text-3xl font-bold">FAQs ❓</h2>
        <div class="space-y-3 text-sm text-slate-200">
          <div><p class="font-semibold">Is ₹299 / year a real payment?</p><p class="text-slate-300 text-xs">Prototype demo; payment not live.</p></div>
          <div><p class="font-semibold">Are college details official?</p><p class="text-slate-300 text-xs">No. Always confirm with college. Data is seeded for demonstration.</p></div>
        </div>
      </div>
    """

    about_panel = """
      <div class="space-y-4">
        <h2 class="text-2xl md:text-3xl font-bold">About CareerInn 🏨💻</h2>
        <p class="text-sm text-slate-300">CareerInn helps students plan careers in two high-growth areas: Hospitality/Hotel Management and B.Tech/Engineering, recognizing the synergy between them.</p>
      </div>
    """

    # choose panel
    if tab == "home":
        panel_html = home_panel
    elif tab == "mentors":
        panel_html = mentors_panel
    elif tab == "skills":
        panel_html = skills_panel
    elif tab == "rating":
        panel_html = rating_panel
    elif tab == "resume":
        panel_html = resume_panel
    elif tab == "faqs":
        panel_html = faqs_panel
    else:
        panel_html = about_panel

    base_tab_cls = "block w-full text-left px-3 py-2 rounded-lg text-xs md:text-sm"
    def cls(name):
        return (base_tab_cls + " bg-indigo-600 text-white border border-indigo-500" if tab == name else base_tab_cls + " text-slate-300 hover:bg-slate-800 border border-transparent")

    content = f"""
    <div class="max-w-6xl mx-auto">
      <div class="mb-4"><p class="text-xs text-slate-400">Profile · Hotel & Hospitality & Tech</p><h1 class="text-2xl md:text-3xl font-bold">Student Dashboard</h1></div>
      <div class="grid md:grid-cols-[220px,1fr] gap-6">
        <aside class="bg-slate-900/80 border border-slate-800 rounded-2xl p-4 h-max">
          <p class="text-[11px] text-slate-400 mb-2">Your space</p>
          <p class="text-sm font-semibold mb-4 truncate">{user_name}</p>
          <nav class="flex flex-col gap-2">
            <a href="/dashboard?tab=home" class="{cls('home')}">🏠 Home</a>
            <a href="/dashboard?tab=mentors" class="{cls('mentors')}">🧑‍🏫 Mentors</a>
            <a href="/dashboard?tab=skills" class="{cls('skills')}">⭐ Skills</a>
            <a href="/dashboard?tab=rating" class="{cls('rating')}">📊 Rating</a>
            <a href="/dashboard?tab=resume" class="{cls('resume')}">📄 Resume</a>
            <a href="/mock-interviews" class="{base_tab_cls} text-slate-300 hover:bg-slate-800">🎤 Mock Interviews</a>
            <a href="/prev-papers" class="{base_tab_cls} text-slate-300 hover:bg-slate-800">📚 Question Papers</a>
            <a href="/dashboard?tab=faqs" class="{cls('faqs')}">❓ FAQs</a>
            <a href="/dashboard?tab=about" class="{cls('about')}">ℹ️ About us</a>
          </nav>
        </aside>
        <section class="bg-slate-900/70 border border-slate-800 rounded-2xl p-5 md:p-6">{panel_html}</section>
      </div>
    </div>
    """
    return render_page(content, "Dashboard")

# -------------------- PROFILE (user-facing profile page with guidance & usage video placeholder) --------------------
@app.route("/profile")
def profile():
    if "user_id" not in session:
        return redirect("/login")
    user_name = session["user"]
    # show career guidance + usage video placeholder (developer must place video at static/usage.mp4)
    content = f"""
    <div class="max-w-4xl mx-auto">
      <h1 class="text-2xl font-bold mb-3">Profile — {user_name}</h1>
      <div class="grid md:grid-cols-2 gap-4">
        <div>
          <h3 class="font-semibold mb-2">CareerInn guidance</h3>
          <ul class="text-sm text-slate-300 space-y-1">
            <li>• Focus on English & grooming for front-office roles.</li>
            <li>• Take short F&B internships to learn service flow.</li>
            <li>• Build a one-page resume highlighting internships & skills.</li>
            <li>• Use the AI bot to prepare for interviews and SOPs.</li>
            <li>• **B.Tech:** Start coding projects on GitHub early.</li>
          </ul>
        </div>
        <div>
          <h3 class="font-semibold mb-2">How to use this website (video)</h3>
          <p class="text-xs text-slate-400 mb-2">Place a tutorial video file at <code>/static/usage.mp4</code> or update the URL below.</p>
          <video controls style="width:100%;border-radius:10px;background:#000;">
            <source src="/static/usage.mp4" type="video/mp4">
            Your browser does not support the video tag.
          </video>
        </div>
      </div>
      <div class="mt-6"><a href="/dashboard" class="px-3 py-2 bg-indigo-600 rounded">Back to dashboard</a></div>
    </div>
    """
    return render_page(content, "Profile")

# -------------------- SUPPORT --------------------
@app.route("/support")
def support():
    content = """
    <h2 class="text-3xl font-bold mb-6">Support & Help</h2>
    <p class="mb-4 text-gray-300">Need assistance? Contact us anytime.</p>
    <div class="support-box"><p>📧 support@careerinn.com</p><p>📞 +91 98... ... ...</p></div>
    """
    return render_page(content, "Support")

# -------------------- MAIN --------------------
if __name__ == "__main__":
    # WARNING: Do NOT use app.run(debug=True) in a live Render environment.
    # The Procfile command `gunicorn app:app` handles production deployment.
    app.run(debug=True)
