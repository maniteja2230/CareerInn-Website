# app.py
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
try:
    from groq import Groq
except Exception:
    Groq = None  # groq optional

# -------------------- CONFIG --------------------
app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "careerinn_secure_key")

# Uploads (kept for compatibility but prev-papers upload is disabled by default)
UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
ALLOWED_EXTENSIONS = {"pdf"}

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

# -------------------- GROQ CLIENT HELPER --------------------
def get_groq_client():
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key or Groq is None:
        return None
    return Groq(api_key=api_key)

# -------------------- DB SETUP --------------------
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///careerinn.db")
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

class College(Base):
    __tablename__ = "colleges"
    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    location = Column(String(255), nullable=False)
    fees = Column(Integer, nullable=False)
    course = Column(String(255), nullable=False)
    rating = Column(Float, nullable=False)
    domain = Column(String(80), nullable=True)  # "hospitality" or "btech"

class Mentor(Base):
    __tablename__ = "mentors"
    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    experience = Column(Text, nullable=False)
    speciality = Column(String(255), nullable=False)
    domain = Column(String(80), nullable=True)

class Job(Base):
    __tablename__ = "jobs"
    id = Column(Integer, primary_key=True)
    title = Column(Text, nullable=False)
    company = Column(String(255), nullable=False)
    location = Column(String(255), nullable=False)
    salary = Column(String(255), nullable=False)
    domain = Column(String(80), nullable=True)

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
    domain = Column(String(80), nullable=True)

class PrevPaper(Base):
    __tablename__ = "prev_papers"
    id = Column(Integer, primary_key=True)
    title = Column(String(300), nullable=False)
    year = Column(String(20), nullable=True)
    link = Column(String(1000), nullable=True)
    uploader_id = Column(Integer, nullable=True)
    is_upload = Column(Boolean, nullable=False, default=False)
    domain = Column(String(80), nullable=True)

# -------------------- DB INIT & SEED --------------------
def get_db():
    return SessionLocal()

def init_db():
    db = get_db()
    Base.metadata.create_all(bind=engine)

    # seed colleges if empty (both hospitality & btech items)
    if db.query(College).count() == 0:
        colleges_seed = [
            # hospitality
            ("IHM Hyderabad (IHMH)", "DD Colony, Hyderabad", 320000, "BSc in Hospitality & Hotel Administration", 4.6, "hospitality"),
            ("NITHM Hyderabad", "Gachibowli, Hyderabad", 280000, "BBA in Tourism & Hospitality", 4.3, "hospitality"),
            ("IIHM Hyderabad", "Somajiguda, Hyderabad", 350000, "BA in Hospitality Management", 4.5, "hospitality"),
            # btech examples
            ("JNTU Hyderabad", "Kukatpally, Hyderabad", 60000, "B.Tech - CSE", 4.0, "btech"),
            ("Osmania University", "Hyderabad", 50000, "B.Tech - ECE", 3.8, "btech"),
            ("VNR VJIET", "Ghatkesar, Hyderabad", 90000, "B.Tech - CSE", 4.1, "btech"),
            ("Institute of Aeronautical Engineering", "Hyderabad", 120000, "B.Tech - Mechanical", 3.9, "btech"),
        ]
        for name, loc, fees, course, rating, domain in colleges_seed:
            db.add(College(name=name, location=loc, fees=fees, course=course, rating=rating, domain=domain))

    # seed mentors (mixed)
    if db.query(Mentor).count() == 0:
        mentors_seed = [
            ("Priya Sharma", "10+ years hospitality operations", "Hotel Ops / Front Office", "hospitality"),
            ("Ravi Kumar", "8+ years software engineering hiring", "CSE recruiter & interview coach", "btech"),
            ("Anita Das", "Ex-Resort F&B head", "Culinary / F&B", "hospitality"),
        ]
        for n, exp, spec, domain in mentors_seed:
            db.add(Mentor(name=n, experience=exp, speciality=spec, domain=domain))

    # seed jobs (mixed)
    if db.query(Job).count() == 0:
        jobs_seed = [
            ("Management Trainee - Hotel Ops", "Taj / IHCL", "Pan India", "₹4.5–5.5 LPA", "hospitality"),
            ("F&B Associate", "Marriott Hotels", "Hyderabad", "₹3–4 LPA", "hospitality"),
            ("Software Engineer - Intern", "Startup X", "Hyderabad", "Stipend", "btech"),
            ("Embedded Systems Intern", "Hardware Co", "Bengaluru", "Stipend", "btech"),
        ]
        for t, c_, loc, sal, domain in jobs_seed:
            db.add(Job(title=t, company=c_, location=loc, salary=sal, domain=domain))

    # seed mock interviews
    if db.query(MockInterview).count() == 0:
        db.add(MockInterview(title="Front Office Mock - Common Questions",
                             notes="Roleplay: guest complains about late check-in. Practice answers for grooming & upsell.",
                             link="https://www.example.com/mock-frontoffice", uploader_id=None, domain="hospitality"))
        db.add(MockInterview(title="CSE Intern Interview - Sample", notes="Data structures & resume walk-through.",
                             link="https://www.example.com/mock-cse", uploader_id=None, domain="btech"))

    # seed previous papers (curated public links - view-only)
    if db.query(PrevPaper).count() == 0:
        db.add(PrevPaper(title="NCHM JEE - PYQ Collection (Aglasem)", year="all",
                         link="https://admission.aglasem.com/nchmct-jee-question-paper/", uploader_id=None, is_upload=False, domain="hospitality"))
        db.add(PrevPaper(title="GATE Papers (Archive)", year="all",
                         link="https://gate.iitm.ac.in/", uploader_id=None, is_upload=False, domain="btech"))

    db.commit()
    db.close()

@app.teardown_appcontext
def shutdown_session(exception=None):
    SessionLocal.remove()

# initialize db
init_db()

# -------------------- AI SYSTEM PROMPT --------------------
AI_SYSTEM_PROMPT = """
You are CareerInn-Tech's AI career guide. Talk friendly and act like a mentor. Ask questions step-by-step.
"""

# -------------------- BASE LAYOUT (navbar reduced as requested) --------------------
BASE_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>{{ title or 'CareerInn-Tech' }}</title>
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

  <!-- NAVBAR: only Home | About Us | Contact | Support -->
  <nav class="flex justify-between items-center px-6 md:px-10 py-4 bg-black/40 backdrop-blur-md border-b border-slate-800">
    <div class="flex items-center gap-3">
      <div class="w-12 h-12 rounded-2xl bg-slate-900 flex items-center justify-center overflow-hidden shadow-lg">
        <img src="/static/logo.png" class="w-11 h-11 object-contain" alt="logo">
      </div>
      <div>
        <p class="font-bold text-lg md:text-xl tracking-tight">CareerInn-Tech</p>
        <p class="text-[11px] text-slate-400">Hospitality · BTech · Careers</p>
      </div>
    </div>

    <div class="hidden md:flex items-center gap-6">
      <a href="/" class="hover:text-indigo-400">Home</a>
      <a href="/about" class="hover:text-indigo-400">About Us</a>
      <a href="/contact" class="hover:text-indigo-400">Contact</a>
      <a href="/support" class="hover:text-indigo-400">Support</a>

      {% if session.get('user') %}
        <div class="flex items-center gap-3">
          <a href="/profile" class="flex items-center gap-2 px-3 py-1.5 rounded-full bg-slate-800 border border-slate-700">
            <div class="w-8 h-8 rounded-full bg-indigo-600 flex items-center justify-center font-semibold text-sm">{{ session.get('user')[0]|upper }}</div>
            <div class="text-xs text-slate-300">{{ session.get('user') }}</div>
          </a>
          <a href="/logout" class="px-4 py-1.5 rounded-full bg-rose-500 hover:bg-rose-600 text-xs font-semibold">Logout</a>
        </div>
      {% else %}
        <a href="/login" class="px-4 py-1.5 rounded-full bg-indigo-500 hover:bg-indigo-600 text-xs font-semibold">Login</a>
      {% endif %}
    </div>
  </nav>

  <!-- PAGE CONTENT -->
  <main class="px-5 md:px-10 py-8">
      {{ content|safe }}
  </main>
</div>

<!-- Animated AI FAB -->
<button id="aiFab" class="ai-fab bg-gradient-to-br from-indigo-500 to-emerald-400" aria-label="Open AI bot">
  <span class="emoji">👩‍🍳</span>
</button>

<div id="aiModalBg" class="ai-modal-bg"></div>

<div id="aiModal" class="ai-modal">
  <div class="flex items-center justify-between mb-2">
    <div class="font-semibold">CareerInn AI</div>
    <button id="closeAi" class="text-slate-400 hover:text-white">✕</button>
  </div>
  <p class="text-xs text-slate-300 mb-3">Try AI Career Chat or start a mock interview. Friendly mentor-style guidance.</p>
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

def render_page(content_html, title="CareerInn-Tech"):
    return render_template_string(BASE_HTML, content=content_html, title=title)

# -------------------- Helpers --------------------
def user_is_subscribed(user_id):
    if not user_id:
        return False
    db = get_db()
    sub = db.query(Subscription).filter_by(user_id=user_id).first()
    db.close()
    return bool(sub and sub.active)

# -------------------- HOME (main page with boxes for everything) --------------------
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

    if logged_in:
        cta_html = """
            <div class="flex gap-3 mt-3">
              <a href="/dashboard" class="px-4 py-2 rounded-full bg-indigo-600">Open Dashboard</a>
              <a href="/chatbot" class="px-4 py-2 rounded-full border border-emerald-400/70">Try AI Chat</a>
            </div>
        """
    else:
        cta_html = """
            <div class="flex gap-3 mt-3">
              <a href="/signup" class="px-4 py-2 rounded-full bg-indigo-600">Create free account</a>
              <a href="/login" class="px-4 py-2 rounded-full border border-slate-700">Login</a>
            </div>
        """

    content = f"""
    <div class="max-w-6xl mx-auto space-y-8">
      <section class="grid md:grid-cols-2 gap-8 items-center">
        <div>
          <h1 class="text-4xl font-extrabold">CareerInn-Tech — Career platform for Hospitality & B.Tech</h1>
          <p class="text-slate-300 mt-3">Personalized roadmaps, mentors, placements and an AI career guide — all in one place.</p>
          {cta_html}
        </div>
        <div class="hero-card rounded-2xl p-6 bg-slate-900/60 border border-slate-800">
          <h3 class="font-semibold">Student Pass</h3>
          <div class="flex items-end gap-4 mt-3">
            <div class="text-4xl font-extrabold text-emerald-300">₹299</div>
            <div class="text-sm text-slate-300">per student / year</div>
          </div>
          <p class="text-slate-300 mt-3 text-xs">Subscribe to unlock AI mock interviews, mentor booking and full guides.</p>
        </div>
      </section>

      <!-- Feature boxes row -->
      <section class="grid md:grid-cols-3 gap-4">
        <a href="/courses" class="feature-card">📘 Courses<p class="sub">Branch-based & useful courses for Hospitality & B.Tech.</p></a>
        <a href="/colleges" class="feature-card">🏫 Colleges<p class="sub">Filter by domain, budget & rating.</p></a>
        <a href="/mentorship" class="feature-card">🧑‍🏫 Mentors<p class="sub">Book domain experts (subscription).</p></a>
        <a href="/jobs" class="feature-card">💼 Jobs & Placements<p class="sub">Latest roles & placement snapshots.</p></a>
        <a href="/global-match" class="feature-card">🌍 Global Match<p class="sub">Abroad options & internship patterns.</p></a>
        <a href="/chatbot" class="feature-card">🤖 AI Career Bot<p class="sub">Get a personalized learning path.</p></a>
      </section>

      <!-- Spotlight row -->
      <section class="grid md:grid-cols-3 gap-4">
        <div class="support-box">
          <h3 class="font-semibold">Top Skills (preview)</h3>
          <p class="text-slate-300 text-sm">View curated skills for hospitality & engineering students.</p>
          <div class="mt-3"><a href="/dashboard?tab=skills" class="px-3 py-2 rounded bg-indigo-600">View Skills</a></div>
        </div>
        <div class="support-box">
          <h3 class="font-semibold">Mock Interviews</h3>
          <p class="text-slate-300 text-sm">Roleplay & AI mock interviews (subscription required for full access).</p>
          <div class="mt-3"><a href="/mock-interviews" class="px-3 py-2 rounded bg-emerald-500">Open Mock Interviews</a></div>
        </div>
        <div class="support-box">
          <h3 class="font-semibold">Previous Year Papers</h3>
          <p class="text-slate-300 text-sm">Curated official & public sources — view only.</p>
          <div class="mt-3"><a href="/prev-papers" class="px-3 py-2 rounded bg-indigo-600">View Papers</a></div>
        </div>
      </section>

      <section class="mt-6">
        <h3 class="text-lg font-semibold">Why CareerInn-Tech?</h3>
        <p class="text-slate-300 text-sm">Branch-specific roadmaps, project bank, internships, mentors, and a friendly AI to guide each step.</p>
      </section>
    </div>
    """
    return render_page(content, "CareerInn-Tech | Home")

# -------------------- COURSES --------------------
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
        rows = "<tr><td>No courses found yet.</td></tr>"
    content = f"""
    <div class="max-w-4xl mx-auto">
      <h2 class="text-3xl font-bold mb-4">Courses (branch-wise)</h2>
      <p class="text-slate-300 mb-3">Key courses and specializations for Hospitality and B.Tech students.</p>
      <table class="table mt-2"><tr><th>Course</th></tr>{rows}</table>
      <div class="mt-4"><a href='/' class='px-3 py-2 bg-indigo-600 rounded'>Back</a></div>
    </div>
    """
    return render_page(content, "Courses")

# -------------------- COLLEGES (filter by domain, budget, rating) --------------------
@app.route("/colleges")
def colleges():
    domain = request.args.get("domain", "").strip()  # hospitality / btech / blank
    budget = request.args.get("budget", "").strip()
    rating_min = request.args.get("rating", "").strip()
    db = get_db()
    query = db.query(College)
    if domain in ("hospitality", "btech"):
        query = query.filter(College.domain == domain)
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
        rows = "<tr><td colspan='5'>No colleges match this filter yet.</td></tr>"
    sel_dom_any = "selected" if domain == "" else ""
    sel_dom_h = "selected" if domain == "hospitality" else ""
    sel_dom_b = "selected" if domain == "btech" else ""
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
    <div class="max-w-6xl mx-auto">
      <h2 class="text-3xl font-bold mb-4">Colleges & Programs</h2>
      <form method="GET" class="mb-3 grid md:grid-cols-4 gap-3 items-center">
        <select name="domain" class="search-bar">
          <option value="" {sel_dom_any}>All domains</option>
          <option value="hospitality" {sel_dom_h}>Hospitality</option>
          <option value="btech" {sel_dom_b}>B.Tech / Engineering</option>
        </select>
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
      <div class="mt-4"><a href='/' class='px-3 py-2 bg-indigo-600 rounded'>Back</a></div>
    </div>
    """
    return render_page(content, "Colleges")

# -------------------- JOBS --------------------
@app.route("/jobs")
def jobs():
    domain = request.args.get("domain", "").strip()
    db = get_db()
    query = db.query(Job)
    if domain in ("hospitality", "btech"):
        query = query.filter(Job.domain == domain)
    data = query.all()
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
    <div class="max-w-6xl mx-auto">
      <h2 class="text-3xl font-bold mb-4">Placements & Recruiters Snapshot</h2>
      <div class="grid md:grid-cols-3 gap-6">{cards}</div>
      <div class="mt-4"><a href='/' class='px-3 py-2 bg-indigo-600 rounded'>Back</a></div>
    </div>
    """
    return render_page(content, "Jobs & Placements")

@app.route("/jobs/<int:job_id>")
def job_detail(job_id):
    db = get_db()
    job = db.query(Job).get(job_id)
    db.close()
    if not job:
        return redirect("/jobs")
    content = f"""
    <div class="max-w-4xl mx-auto">
      <h2 class="text-2xl font-bold mb-3">{job.title}</h2>
      <p class="text-sm text-slate-300 mb-2">Company: <span class="text-indigo-300">{job.company}</span></p>
      <p class="text-sm text-slate-300 mb-2">Location: {job.location}</p>
      <p class="text-sm text-emerald-300 mb-4">Package / Salary: {job.salary}</p>
      <a href="/jobs" class="px-3 py-1 rounded-full bg-indigo-600">Back to jobs</a>
    </div>
    """
    return render_page(content, "Job detail")

# -------------------- MENTORSHIP (locked) --------------------
@app.route("/mentorship")
def mentorship():
    user_id = session.get("user_id")
    if not user_is_subscribed(user_id):
        content = """
        <div class="max-w-4xl mx-auto">
          <h2 class="text-3xl font-bold mb-4">Find Mentors</h2>
          <p class="text-slate-300">Mentorship is available to subscribed users only.</p>
          <div class="mt-4"><a href="/subscribe" class="px-3 py-2 bg-indigo-600 rounded">Subscribe to unlock</a></div>
        </div>
        """
        return render_page(content, "Mentorship")
    db = get_db()
    data = db.query(Mentor).all()
    db.close()
    cards = ""
    for m in data:
        cards += f"<div class='mentor-card'><h3 class='text-lg font-bold mb-1'>{m.name}</h3><p class='text-sm text-gray-300'>{m.experience}</p><p class='text-sm text-indigo-300 mb-2'>{m.speciality}</p></div>"
    return render_page(f"<div class='max-w-6xl mx-auto'><h2 class='text-3xl font-bold mb-4'>Find Mentors</h2><div class='grid md:grid-cols-3 gap-6'>{cards}</div></div>", "Mentorship")

# -------------------- MOCK INTERVIEWS --------------------
@app.route("/mock-interviews", methods=["GET", "POST"])
def mock_interviews():
    user_id = session.get("user_id")
    if not user_is_subscribed(user_id):
        content = """
        <div class="max-w-4xl mx-auto">
          <h2 class="text-3xl font-bold mb-4">Mock Interviews & Practice</h2>
          <p class="text-slate-300">Mock interview resources are available to subscribed users only.</p>
          <div class="mt-4"><a href="/subscribe" class="px-3 py-2 bg-indigo-600 rounded">Subscribe to unlock</a></div>
        </div>
        """
        return render_page(content, "Mock Interviews")
    db = get_db()
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        notes = request.form.get("notes", "").strip()
        link = request.form.get("link", "").strip()
        domain = request.form.get("domain", "").strip()
        if title:
            db.add(MockInterview(title=title, notes=notes, link=link, uploader_id=user_id, domain=domain))
            db.commit()
            return redirect("/mock-interviews")
    items = db.query(MockInterview).order_by(MockInterview.id.desc()).all()
    db.close()
    cards = ""
    for it in items:
        uploader = " (by you)" if user_id and it.uploader_id == user_id else ""
        cards += f"<div class='support-box'><h3 class='font-semibold mb-1'>{it.title}{uploader}</h3><p class='text-xs text-slate-300 mb-2'>{it.notes or ''}</p>{(f'<a href=\"{it.link}\" target=\"_blank\" class=\"text-indigo-300 text-sm underline\">Open resource</a>' if it.link else '')}</div>"
    content = f"""
    <div class="max-w-6xl mx-auto">
      <h2 class="text-3xl font-bold mb-4">Mock Interviews & Practice</h2>
      <form method="POST" class="mb-4 space-y-2">
        <input name="title" placeholder="Title (eg: Front Office - Live Roleplay)" class="input-box" required>
        <input name="link" placeholder="Video / doc link (optional)" class="input-box">
        <input name="domain" placeholder="domain (hospitality / btech)" class="input-box">
        <textarea name="notes" rows="3" placeholder="Short notes..." class="input-box h-auto"></textarea>
        <button class="px-4 py-2 rounded-full bg-indigo-600">Add mock interview</button>
      </form>
      <div class="grid md:grid-cols-2 gap-4">{cards}</div>
      <div class="mt-4"><a href='/' class='px-3 py-2 bg-indigo-600 rounded'>Back</a></div>
    </div>
    """
    return render_page(content, "Mock Interviews")

@app.route("/mock-interviews/ai", methods=["GET", "POST"])
def mock_interview_ai():
    user_id = session.get("user_id")
    if not user_is_subscribed(user_id):
        return render_page("<div class='max-w-4xl mx-auto'><p class='text-slate-300'>AI Mock Interview requires subscription. <a href='/subscribe' class='text-indigo-300'>Subscribe</a></p></div>", "Mock Interview Bot")
    history = session.get("mock_ai_history", [])
    if request.method == "POST":
        user_msg = request.form.get("message", "").strip()
        if user_msg:
            history.append({"role":"user","content":user_msg})
            messages = [{"role":"system","content":"You are an AI mock interviewer. Ask scenario questions, give feedback."}] + history
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
    html = "<div class='max-w-3xl mx-auto space-y-6'><h1 class='text-2xl font-bold'>AI Mock Interview</h1><div class='bg-slate-900/80 border border-slate-700 rounded-2xl p-4 h-[320px] overflow-y-auto mb-4'>"
    for m in history:
        who = "You" if m["role"]=="user" else "Interviewer"
        bubble_cls = "bg-indigo-600" if m["role"]=="user" else "bg-slate-800"
        html += f"<div class='mb-3'><div class='text-xs text-slate-400 mb-0.5'>{who}</div><div class='inline-block px-3 py-2 rounded-2xl {bubble_cls} text-xs md:text-sm max-w-[90%]'>{m['content']}</div></div>"
    html += "</div><form method='POST' class='flex gap-2'><input name='message' autocomplete='off' placeholder='Answer a question or type start...' class='flex-1 input-box' required><button class='px-4 py-2 rounded-full bg-indigo-600 hover:bg-indigo-500 text-sm font-semibold'>Send</button></form></div>"
    return render_page(html, "AI Mock Interview")

# -------------------- PREVIOUS PAPERS (view-only) --------------------
@app.route("/prev-papers")
def prev_papers():
    domain = request.args.get("domain", "").strip()
    db = get_db()
    query = db.query(PrevPaper)
    if domain in ("hospitality", "btech"):
        query = query.filter(PrevPaper.domain == domain)
    items = query.order_by(PrevPaper.year.desc()).all()
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
    <div class="max-w-6xl mx-auto">
      <h2 class="text-3xl font-bold mb-4">Previous Year Question Papers (view-only)</h2>
      <p class="text-slate-300 mb-4">Curated past papers and official resources — uploading is disabled.</p>
      <table class="table mt-2"><tr><th>Title</th><th>Year</th><th>Link</th></tr>{rows}</table>
      <div class="mt-4"><a href='/' class='px-3 py-2 bg-indigo-600 rounded'>Back</a></div>
    </div>
    """
    return render_page(content, "Previous Year Papers")

@app.route("/uploads/<path:filename>")
def uploaded_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename, as_attachment=False)

# -------------------- GLOBAL MATCH --------------------
@app.route("/global-match")
def global_match():
    user_id = session.get("user_id")
    if not user_is_subscribed(user_id):
        content = """
        <div class="max-w-6xl mx-auto">
          <h2 class="text-3xl font-bold mb-4">Global College & Internship Match</h2>
          <p class="text-slate-300 mb-4">Global matching info is for subscribed users. Subscribe to unlock guidance on abroad options and internships.</p>
          <div class="mt-4"><a href="/subscribe" class="px-3 py-2 bg-indigo-600 rounded">Subscribe to unlock</a></div>
        </div>
        """
        return render_page(content, "Global Match (Locked)")
    content = """
    <div class="max-w-6xl mx-auto">
      <h2 class="text-3xl font-bold mb-4">Global College & Internship Match</h2>
      <div class="grid md:grid-cols-3 gap-5 mb-6">
        <div class="support-box"><h3 class="font-semibold mb-2">Popular Countries</h3><ul class="text-sm text-slate-200"><li>Switzerland</li><li>UAE</li><li>Singapore</li><li>Canada</li></ul></div>
        <div class="support-box"><h3 class="font-semibold mb-2">Typical Requirements</h3><ul class="text-sm text-slate-200"><li>Good English</li><li>IELTS / language tests</li><li>Clear SOP</li></ul></div>
        <div class="support-box"><h3 class="font-semibold mb-2">Internship Patterns</h3><ul class="text-sm text-slate-200"><li>6–12 month internships</li><li>Front office, F&B, culinary, engineering roles</li></ul></div>
      </div>
    </div>
    """
    return render_page(content, "Global Match")

# -------------------- Chatbot (AI career bot) --------------------
CHATBOT_HTML = """
<div class="max-w-3xl mx-auto space-y-6">
  <h1 class="text-3xl font-bold mb-2">CareerInn-Tech AI Mentor</h1>
  {% if not locked %}
    <p class="text-sm text-slate-300 mb-4">This AI bot will ask about your background and provide a step-by-step plan. One free full chat per account.</p>
  {% else %}
    <p class="text-sm text-slate-300 mb-4">Your free AI career chat is finished. Please subscribe for more guidance.</p>
  {% endif %}
  <form method="GET" action="/chatbot" class="mb-3"><input type="hidden" name="reset" value="1"><button class="px-3 py-1 rounded-full border border-slate-600 text-[11px] hover:bg-slate-800">🔄 Clear chat</button></form>
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
      <p class="text-sm text-slate-400">👋 Hi! Tell me your name, current year/qualification, and your goal (placements / internships / abroad).</p>
    {% endif %}
  </div>
  {% if not locked %}
    <form method="POST" class="flex gap-2">
      <input name="message" autocomplete="off" placeholder="Type your message here..." class="flex-1 input-box" required>
      <button class="px-4 py-2 rounded-full bg-indigo-600 hover:bg-indigo-500 text-sm font-semibold">Send</button>
    </form>
    <form method="POST" action="/chatbot/end" class="mt-3"><button class="px-3 py-1.5 text-[11px] rounded-full border border-rose-500/70 text-rose-200 hover:bg-rose-500/10">🔒 End & lock free AI chat</button></form>
  {% else %}
    <p class="text-xs text-slate-400 mt-2">Tip: Subscribe to access extended AI guidance and mock interviews.</p>
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
    locked = bool(usage and usage.ai_used == 1)
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
            history.append({"role":"assistant","content":"⚠ Your free AI career chat session has ended. Please subscribe for more."})
            session["ai_history"] = history
            db.close()
            html = render_template_string(CHATBOT_HTML, history=history, locked=True)
            return render_page(html, "AI Mentor")
        user_msg = request.form.get("message", "").strip()
        if user_msg:
            history.append({"role":"user","content":user_msg})
            messages = [{"role":"system","content":AI_SYSTEM_PROMPT}] + history
            groq_client = get_groq_client()
            if groq_client is None:
                reply = "AI is not configured. Please set GROQ_API_KEY in environment (demo mode)."
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
    return render_page(html, "CareerInn-Tech AI Mentor")

@app.route("/finish")
def finish():
    user_id = session.get("user_id")
    if not user_id:
        return redirect("/login")
    db = get_db()
    usage = db.query(AiUsage).filter_by(user_id=user_id).first()
    if usage is None:
        usage = AiUsage(user_id=user_id, ai_used=1)
        db.add(usage)
    else:
        usage.ai_used = 1
    db.commit()
    db.close()
    return redirect("/chatbot")

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
  <h2 class="text-xl font-bold mb-4">Create your CareerInn-Tech account</h2>
  <input name="name" placeholder="Full Name" required class="input-box">
  <input name="email" placeholder="Email" required class="input-box">
  <input name="password" type="password" placeholder="Password" required class="input-box">
  <button class="submit-btn">Signup</button>
  <p class="text-gray-400 mt-3 text-sm">Already registered? <a href="/login" class="text-indigo-400">Login</a></p>
</form>
"""

LOGIN_FORM = """
<form method="POST" class="auth-card">
  <h2 class="text-xl font-bold mb-2">Login to CareerInn-Tech</h2>
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

# -------------------- SUBSCRIBE (demo flow) --------------------
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
    <div class="max-w-3xl mx-auto">
      <h2 class="text-2xl font-bold mb-4">Subscribe to CareerInn-Tech Student Pass</h2>
      <p class="text-slate-300 mb-3">Demo payment flow. Click Subscribe to enable locked sections for your account.</p>
      <form method="POST"><button class="px-4 py-2 bg-indigo-600 rounded">Subscribe – ₹299 / year (demo)</button></form>
    </div>
    """
    return render_page(content, "Subscribe")

# -------------------- DASHBOARD --------------------
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

    if session.get("first_time_login", False):
        greeting = "CareerInn-Tech welcomes you 🎉"
        session["first_time_login"] = False
    else:
        greeting = "Welcome back 👋"

    # prefill skills for subscribed users if empty
    if not skills_text and user_is_subscribed(user_id):
        skills_text = ", ".join([
            "Communication",
            "Domain fundamentals",
            "Internship experience",
            "Project & Git",
            "Teamwork",
            "Problem solving",
        ])
        db = get_db()
        profile = db.query(UserProfile).filter_by(user_id=user_id).first()
        if profile and not profile.skills_text:
            profile.skills_text = skills_text
            db.commit()
        db.close()

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
        <p class="text-slate-300">This is your student workspace to track skills, projects and placement readiness.</p>

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

      </div>
    """

    # panels
    if not user_is_subscribed(user_id):
        mentors_panel = """
          <div class="space-y-4">
            <h2 class="text-2xl font-bold">Mentor connections</h2>
            <p class="text-slate-300">Subscribe to access mentor booking and personalized reviews.</p>
            <a href="/subscribe" class="px-3 py-2 bg-indigo-600 rounded">Subscribe</a>
          </div>
        """
        skills_panel = """
          <div class="space-y-4">
            <h2 class="text-2xl font-bold">Skills & strengths</h2>
            <p class="text-slate-300">Subscribe to unlock skills editing and personalised suggestions.</p>
            <a href="/subscribe" class="px-3 py-2 bg-indigo-600 rounded">Subscribe</a>
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
            <h2 class="text-2xl font-bold">Skills & strengths</h2>
            <div class="mt-3"><label class="block text-xs text-slate-300 mb-1">Your skills</label>{skills_chips_with_remove(skills_text)}</div>
            <form method="POST" action="/dashboard" class="flex gap-2 mt-3">
              <input type="hidden" name="tab" value="skills_add">
              <input name="new_skill" placeholder="Add a skill (e.g. Grooming, Git)" class="input-box flex-1" />
              <button class="px-3 py-1 rounded-full bg-indigo-600">Add</button>
            </form>
            <form method="POST" class="space-y-4 mt-4">
              <input type="hidden" name="tab" value="skills">
              <div>
                <label class="block text-xs text-slate-300 mb-1">Full skill list</label>
                <textarea name="skills_text" rows="4" class="input-box h-auto">{skills_text}</textarea>
              </div>
              <div><label class="block text-xs text-slate-300 mb-1">Target roles</label><textarea name="target_roles" rows="3" class="input-box h-auto">{target_roles}</textarea></div>
              <div class="grid md:grid-cols-2 gap-4 items-center"><div><label class="block text-xs text-slate-300 mb-1">Rate readiness (0–5)</label><input name="self_rating" type="number" min="0" max="5" value="{self_rating}" class="input-box" /></div></div>
              <button class="submit-btn mt-2">Save skills</button>
            </form>
          </div>
        """

    rating_panel = f"""
      <div class="space-y-4">
        <h2 class="text-2xl font-bold">Career rating overview</h2>
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
        <h2 class="text-2xl font-bold">Resume & profile link</h2>
        <form method="POST" class="space-y-4 mt-4">
          <input type="hidden" name="tab" value="resume">
          <div><label class="block text-xs text-slate-300 mb-1">Resume link</label><input name="resume_link" class="input-box" placeholder="https://drive.google.com/..." value="{resume_link}"></div>
          <div><label class="block text-xs text-slate-300 mb-1">Notes for mentor</label><textarea name="notes" rows="3" class="input-box h-auto">{notes}</textarea></div>
          <button class="submit-btn mt-2">Save resume details</button>
        </form>
        {"<p class='text-xs text-emerald-300 mt-2'>Current resume link: <a href='" + resume_link + "' target='_blank' class='underline'>" + resume_link + "</a></p>" if resume_link else ""}
      </div>
    """

    faqs_panel = """
      <div class="space-y-4">
        <h2 class="text-2xl font-bold">FAQs</h2>
        <div class="space-y-3 text-sm text-slate-200">
          <div><p class="font-semibold">Is ₹299 / year real?</p><p class="text-slate-300 text-xs">Prototype; payment not live in this demo.</p></div>
          <div><p class="font-semibold">Are college details official?</p><p class="text-slate-300 text-xs">No. Confirm with college websites before applying.</p></div>
        </div>
      </div>
    """

    about_panel = """
      <div class="space-y-4">
        <h2 class="text-2xl font-bold">About CareerInn-Tech</h2>
        <p class="text-slate-300">Merged platform for Hospitality & B.Tech career planning.</p>
      </div>
    """

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
      <div class="mb-4"><p class="text-xs text-slate-400">Profile · Student Workspace</p><h1 class="text-2xl md:text-3xl font-bold">Student Dashboard</h1></div>
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

# -------------------- PROFILE --------------------
@app.route("/profile")
def profile():
    if "user_id" not in session:
        return redirect("/login")
    user_name = session["user"]
    content = f"""
    <div class="max-w-4xl mx-auto">
      <h1 class="text-2xl font-bold mb-3">Profile — {user_name}</h1>
      <div class="grid md:grid-cols-2 gap-4">
        <div>
          <h3 class="font-semibold mb-2">CareerInn-Tech guidance</h3>
          <ul class="text-sm text-slate-300 space-y-1">
            <li>• Focus on foundational skills & communication.</li>
            <li>• Do short internships and mini projects.</li>
            <li>• Keep a one-page resume for mentors & recruiters.</li>
            <li>• Use AI bot to prepare for interviews and SOPs.</li>
          </ul>
        </div>
        <div>
          <h3 class="font-semibold mb-2">How to use this website (video)</h3>
          <p class="text-xs text-slate-400 mb-2">Place a tutorial video at <code>/static/usage.mp4</code> to display here.</p>
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

# -------------------- ABOUT / CONTACT / SUPPORT --------------------
@app.route("/about")
def about():
    content = """
    <div class="max-w-4xl mx-auto">
      <h1 class="text-3xl font-bold mb-4">About CareerInn-Tech</h1>
      <p class="text-slate-300">CareerInn-Tech merges Hospitality and B.Tech career planning into a single platform with AI & mentor guidance.</p>
    </div>
    """
    return render_page(content, "About Us")

@app.route("/contact", methods=["GET", "POST"])
def contact():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        msg = request.form.get("message", "").strip()
        # demo: in prod save or email this
        return render_page("<p class='text-emerald-300'>Thanks — we received your message (demo).</p><a href='/' class='px-3 py-2 bg-indigo-600 rounded mt-3 inline-block'>Back</a>", "Contact")
    content = """
    <div class="max-w-3xl mx-auto">
      <h1 class="text-2xl font-bold mb-4">Contact Us</h1>
      <form method="POST" class="space-y-3">
        <input name="name" placeholder="Your name" class="input-box" required>
        <input name="email" placeholder="Email" class="input-box" required>
        <textarea name="message" rows="4" class="input-box" placeholder="Message..." required></textarea>
        <button class="px-4 py-2 bg-indigo-600 rounded">Send</button>
      </form>
    </div>
    """
    return render_page(content, "Contact")

@app.route("/support")
def support():
    content = """
    <div class="max-w-3xl mx-auto">
      <h2 class="text-3xl font-bold mb-6">Support & Help</h2>
      <p class="mb-4 text-slate-300">Need assistance? Contact us anytime.</p>
      <div class="support-box"><p>📧 support@careerinn-tech.com</p><p>📞 +91 98... ... ...</p></div>
    </div>
    """
    return render_page(content, "Support")

# -------------------- MAIN --------------------
if __name__ == "__main__":
    # When running locally, use port 5000. On platforms like Render, they set their own env vars.
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=True, host="0.0.0.0", port=port)
