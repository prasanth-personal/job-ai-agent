import os
from dotenv import load_dotenv

load_dotenv()

RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GMAIL_FROM = os.getenv("GMAIL_FROM")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")
ADZUNA_APP_ID = os.getenv("ADZUNA_APP_ID")
ADZUNA_APP_KEY = os.getenv("ADZUNA_APP_KEY")
ADZUNA_ENABLED = bool(ADZUNA_APP_ID and ADZUNA_APP_KEY)

RESUME_FILE = "my_resume.txt"
DB_FILE = "job_agent.db"
MAX_SEARCHES = 2

TRUSTED_BOARDS = [
    "linkedin.com", "glassdoor.co.in", "indeed.com", "naukri.com", "glassdoor.com",
    "wellfound.com", "lever.co", "greenhouse.io", "workday.com", "taleo.net",
    "icims.com", "myworkdayjobs.com", "bamboohr.com", "instahyre.com", "foundit.in",
    "oracle.com", "careers.", "shine.com", "timesjobs.com", "monsterindia.com",
    "recruit.net", "in.talent.com", "expertini.com", "hirist.tech", "cutshort.io",
    "applygateway.com", "smartrecruiters.com", "careers.tcs.com", "infosys.com",
    "wipro.com", "persistent.com", "coforge.com", "mphasis.com", "hexaware.com",
    "birlasoft.com", "genpact.com", "jobleads.com", "kornferry.com",
    "adzuna.in", "adzuna.com",
]
SUSPICIOUS_BOARDS = ["telegram", "whatsapp", "bit.ly", "tinyurl","bebee.com"]
SPAM_KEYWORDS = [
    "manpower", "placement", "staffing solutions", "hr services", "job consultancy",
    "fresherslive", "wisdomjobs", "placementindia", "mnc jobs", "walkin",
    "mass hiring", "immediate joiners only", "0-0 yrs",
]
# Real target search queries — ported from v3.2's config.yaml jsearch_queries.
# Based on MY_SKILLS: 8 years Salesforce, Agentforce/AI-engineering transition.
# Edit this list directly as your target roles evolve.
SEARCH_QUERIES = [
    "Salesforce Senior Consultant",
    "Agentforce Developer India",
    "Salesforce Technical Lead India",
    "AI Engineer Salesforce India",
    "Generative AI Engineer India",
    "LangChain Developer India",
    "Salesforce AI Consultant India",
    
]
ROLE_FAMILIES = {
    "Salesforce": "Salesforce development, consulting, architecture, and technical leadership roles",
    "GenAI Engineer": "Generative AI / LLM application engineering, AI agent development, and applied AI roles",
}


def load_resume() -> str:
    """Reads the resume file if present; returns empty string with a
    warning printed if it's missing, instead of crashing at import time."""
    if os.path.exists(RESUME_FILE):
        with open(RESUME_FILE, "r", encoding="utf-8") as f:
            return f.read()
    print(f"WARNING: {RESUME_FILE} not found — create it with your resume text before running scoring.")
    return ""


MY_RESUME = load_resume()