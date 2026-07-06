"""
Fetch top 5 scored opportunities from Snowflake and send an email digest.
Called as the final step of the daily pipeline.
"""
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "ingestion"))
from snowflake_conn import get_connection


def send_top_opportunities():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            TITLE,
            AGENCY,
            FIT_SCORE,
            RESPONSE_DEADLINE,
            UI_LINK,
            SET_ASIDE,
            ESTIMATED_VALUE
        FROM GOVCONTRACT.MARTS.MART_OPPORTUNITY_FEATURES
        WHERE ACTIVE = TRUE
          AND RESPONSE_DEADLINE >= CURRENT_DATE
        ORDER BY FIT_SCORE DESC NULLS LAST
        LIMIT 5
    """)
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        print("No active opportunities to digest.")
        return

    rows_html = ""
    for i, row in enumerate(rows, 1):
        title, agency, score, deadline, link, set_aside, value = row
        score_display = f"{score:.0f}" if score else "N/A"
        value_display = f"${value:,.0f}" if value else "Unknown"
        deadline_display = str(deadline)[:10] if deadline else "Unknown"
        rows_html += f"""
        <tr>
          <td style="padding:8px;font-weight:bold;">#{i}</td>
          <td style="padding:8px;"><a href="{link}">{title}</a></td>
          <td style="padding:8px;">{agency or ''}</td>
          <td style="padding:8px;text-align:center;font-size:18px;font-weight:bold;color:#1a6c2e;">{score_display}</td>
          <td style="padding:8px;">{value_display}</td>
          <td style="padding:8px;">{set_aside or '—'}</td>
          <td style="padding:8px;">{deadline_display}</td>
        </tr>
        """

    html = f"""
    <html><body style="font-family:Arial,sans-serif;max-width:900px;margin:auto;">
    <h2 style="color:#1a3c6e;">GovContract Radar — Daily Digest</h2>
    <p>Top {len(rows)} opportunities scored today:</p>
    <table border="0" cellspacing="0" cellpadding="0" style="border-collapse:collapse;width:100%;">
      <thead>
        <tr style="background:#1a3c6e;color:white;">
          <th style="padding:8px;">#</th>
          <th style="padding:8px;text-align:left;">Title</th>
          <th style="padding:8px;text-align:left;">Agency</th>
          <th style="padding:8px;">Score</th>
          <th style="padding:8px;text-align:left;">Est. Value</th>
          <th style="padding:8px;text-align:left;">Set-Aside</th>
          <th style="padding:8px;text-align:left;">Deadline</th>
        </tr>
      </thead>
      <tbody>
        {rows_html}
      </tbody>
    </table>
    <p style="margin-top:20px;font-size:12px;color:#888;">
      Powered by GovContract Radar · <a href="{os.getenv('STREAMLIT_URL', '#')}">View full dashboard</a>
    </p>
    </body></html>
    """

    _send_email(
        subject=f"GovContract Radar — {len(rows)} Top Opportunities",
        html=html,
    )
    print(f"Digest sent with {len(rows)} opportunities.")


def _send_email(subject: str, html: str):
    smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER")
    smtp_pass = os.getenv("SMTP_PASS")
    to_email = os.getenv("DIGEST_EMAIL", "yezavit@yahoo.com")

    if not smtp_user or not smtp_pass:
        print("SMTP credentials not configured — skipping email send.")
        print(f"Would have sent to: {to_email}")
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = smtp_user
    msg["To"] = to_email
    msg.attach(MIMEText(html, "html"))

    with smtplib.SMTP(smtp_host, smtp_port) as server:
        server.starttls()
        server.login(smtp_user, smtp_pass)
        server.sendmail(smtp_user, to_email, msg.as_string())
