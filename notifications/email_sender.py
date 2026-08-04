import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from config.settings import GMAIL_FROM, GMAIL_APP_PASSWORD
from utils.logger import get_logger

log = get_logger()


def _attach_file(msg: MIMEMultipart, filepath: str):
    """Attaches one file to the email if it exists. Skips silently with a
    log warning if the file is missing, rather than crashing the whole
    email send over one missing attachment."""
    if not filepath or not os.path.exists(filepath):
        log.warning(f"Email attachment skipped — {filepath} not found")
        return
    with open(filepath, "rb") as f:
        part = MIMEBase("application", "octet-stream")
        part.set_payload(f.read())
        encoders.encode_base64(part)
        part.add_header("Content-Disposition", f"attachment; filename={os.path.basename(filepath)}")
        msg.attach(part)


def send_daily_report(summary_text: str, excel_path: str = None,
                       skill_gap_path: str = None,all_time_skill_gap_path: str = None,
                       log_path: str = "job_agent.log"):
    """Sends one email with the job results Excel, skill gap Excel, and
    log file attached. Missing files are skipped individually rather than
    blocking the whole email — e.g. if no High/Medium matches exist yet,
    skill_gap_report.xlsx might not have been created that run."""
    if not GMAIL_FROM or not GMAIL_APP_PASSWORD:
        log.warning("Email skipped — GMAIL_FROM / GMAIL_APP_PASSWORD not set in .env")
        return

    msg = MIMEMultipart()
    msg["From"] = GMAIL_FROM
    msg["To"] = GMAIL_FROM
    msg["Subject"] = "Job Search Agent — Daily Report"

    msg.attach(MIMEText(summary_text, "plain"))

    for path in [excel_path, skill_gap_path, all_time_skill_gap_path, log_path]:
        _attach_file(msg, path)

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(GMAIL_FROM, GMAIL_APP_PASSWORD)
            server.send_message(msg)
        log.info(f"Email sent to {GMAIL_FROM}")
    except Exception as e:
        log.error(f"Email error: {e}")