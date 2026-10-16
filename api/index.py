"""Vercel Serverless Function entry point for DataGuard.

Serves the DataGuard cloud portal and documentation overview.
"""

from http.server import BaseHTTPRequestHandler
import json

HTML_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>DataGuard — Data Quality & ETL Platform</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
      background: #0f172a;
      color: #f8fafc;
      min-height: 100vh;
      display: flex;
      flex-direction: column;
    }
    .hero {
      background: radial-gradient(circle at 50% 0%, #1e3a5f 0%, #0f172a 75%);
      padding: 4rem 2rem 3rem;
      text-align: center;
      border-bottom: 1px solid rgba(255,255,255,0.08);
    }
    .badge {
      display: inline-block;
      background: rgba(20, 160, 133, 0.15);
      border: 1px solid rgba(20, 160, 133, 0.4);
      color: #2dd4bf;
      padding: 0.35rem 1rem;
      border-radius: 999px;
      font-size: 0.85rem;
      font-weight: 600;
      margin-bottom: 1.2rem;
      letter-spacing: 0.5px;
    }
    h1 {
      font-size: 2.75rem;
      font-weight: 800;
      letter-spacing: -1px;
      margin-bottom: 1rem;
      background: linear-gradient(135deg, #ffffff 0%, #cbd5e1 100%);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
    }
    p.subtitle {
      font-size: 1.15rem;
      color: #94a3b8;
      max-width: 680px;
      margin: 0 auto 2rem;
      line-height: 1.6;
    }
    .btn-group {
      display: flex;
      justify-content: center;
      gap: 1rem;
      flex-wrap: wrap;
    }
    .btn {
      padding: 0.75rem 1.6rem;
      border-radius: 8px;
      font-weight: 600;
      font-size: 0.95rem;
      text-decoration: none;
      transition: all 0.2s ease;
      display: inline-flex;
      align-items: center;
      gap: 0.5rem;
    }
    .btn-primary {
      background: #14a085;
      color: white;
    }
    .btn-primary:hover {
      background: #0d7377;
      transform: translateY(-2px);
      box-shadow: 0 8px 20px rgba(20, 160, 133, 0.3);
    }
    .btn-secondary {
      background: rgba(255,255,255,0.08);
      color: #f8fafc;
      border: 1px solid rgba(255,255,255,0.15);
    }
    .btn-secondary:hover {
      background: rgba(255,255,255,0.12);
      transform: translateY(-2px);
    }
    .container {
      max-width: 1040px;
      margin: 0 auto;
      padding: 3rem 1.5rem;
      flex: 1;
    }
    .grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
      gap: 1.5rem;
      margin-bottom: 3rem;
    }
    .card {
      background: rgba(30, 41, 59, 0.7);
      border: 1px solid rgba(255, 255, 255, 0.08);
      border-radius: 12px;
      padding: 1.75rem;
      backdrop-filter: blur(8px);
      transition: border-color 0.2s;
    }
    .card:hover {
      border-color: rgba(20, 160, 133, 0.4);
    }
    .card-icon {
      font-size: 1.75rem;
      margin-bottom: 1rem;
    }
    .card h3 {
      font-size: 1.25rem;
      font-weight: 700;
      margin-bottom: 0.6rem;
      color: #f1f5f9;
    }
    .card p {
      color: #94a3b8;
      font-size: 0.92rem;
      line-height: 1.55;
    }
    .code-box {
      background: #020617;
      border: 1px solid rgba(255, 255, 255, 0.1);
      border-radius: 8px;
      padding: 1.2rem;
      font-family: 'Consolas', monospace;
      font-size: 0.88rem;
      color: #38bdf8;
      overflow-x: auto;
      margin: 1.5rem 0;
    }
    footer {
      text-align: center;
      padding: 2rem;
      color: #64748b;
      font-size: 0.85rem;
      border-top: 1px solid rgba(255, 255, 255, 0.05);
    }
  </style>
</head>
<body>
  <div class="hero">
    <span class="badge">🛡️ Antigravity & Vercel Deployed</span>
    <h1>DataGuard Platform</h1>
    <p class="subtitle">End-to-end Data Quality Monitoring & ETL Pipeline with PostgreSQL storage, quarantine isolation, and an interactive Streamlit dashboard.</p>
    <div class="btn-group">
      <a href="https://github.com/TalariLakshmiNarasimha/DataGuard" class="btn btn-primary" target="_blank">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0024 12c0-6.63-5.37-12-12-12z"/></svg>
        GitHub Repository
      </a>
      <a href="https://share.streamlit.io" class="btn btn-secondary" target="_blank">
        🚀 Launch Streamlit Cloud
      </a>
    </div>
  </div>

  <div class="container">
    <div class="grid">
      <div class="card">
        <div class="card-icon">⚡</div>
        <h3>Repeatable ETL Pipeline</h3>
        <p>Ingests business orders from CSV, enforces schema validation, normalizes data, and performs idempotent upserts into PostgreSQL.</p>
      </div>
      <div class="card">
        <div class="card-icon">🔒</div>
        <h3>Automated Quarantine</h3>
        <p>Invalid records are never silently dropped. They are stored with line numbers and human-readable rejection reasons for full auditability.</p>
      </div>
      <div class="card">
        <div class="card-icon">📊</div>
        <h3>Live Monitoring Dashboard</h3>
        <p>Streamlit interface featuring drag & drop CSV upload, schema compliance checklists, acceptance charts, and quarantine exploration.</p>
      </div>
    </div>

    <h2 style="font-size: 1.5rem; margin-bottom: 0.8rem;">⚡ Quick Start (Local Execution)</h2>
    <div class="code-box">
      # Clone repository<br>
      git clone https://github.com/TalariLakshmiNarasimha/DataGuard.git<br>
      cd DataGuard<br><br>
      # Start PostgreSQL & install dependencies<br>
      docker-compose up -d<br>
      pip install -r requirements.txt<br><br>
      # Initialize database schema & run pipeline<br>
      python scripts/init_db.py<br>
      python -m app --input data/sample_orders.csv<br><br>
      # Launch interactive Streamlit dashboard<br>
      streamlit run app/dashboard/streamlit_app.py
    </div>
  </div>

  <footer>
    DataGuard &copy; 2026 &bull; Developed by Talari Lakshmi Narasimha &bull; Portfolio Data Engineering Platform
  </footer>
</body>
</html>
"""

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(HTML_PAGE.encode("utf-8"))
        return
