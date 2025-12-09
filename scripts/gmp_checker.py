import requests
import json
from utils.email_sender import send_email
import os
import re
from html import unescape
from datetime import datetime
from dotenv import load_dotenv
load_dotenv()

GMP_API_URL = "https://webnodejs.investorgain.com/cloud/report/data-read/331/1/8/2000/abc/00/all"

def parse_gmp(gmp_str):
    if not gmp_str:
        return 0.0
    gmp_str = unescape(gmp_str)
    match = re.search(r'\(([\d\.]+)%\)', gmp_str)
    if match:
        try:
            return float(match.group(1))
        except ValueError:
            return 0.0
    return 0.0



HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.google.com/",
    "Origin": "https://www.google.com",
    "Accept-Encoding": "gzip, deflate, br",
}

def fetch_gmp_data():
    resp = requests.get(GMP_API_URL, headers=HEADERS, timeout=10)

    # If server returns HTML instead of JSON → bot-block
    content_type = resp.headers.get("Content-Type", "").lower()

    if "json" not in content_type:
        print("⚠️ Server did NOT return JSON. Dumping first 300 chars:")
        print(resp.text[:300])
        raise ValueError("Blocked or unexpected response returned")

    try:
        data = resp.json()
    except json.JSONDecodeError:
        print("⚠️ JSON decode failed — likely blocked. Dumping first 300 chars:")
        print(resp.text[:300])
        raise

    return data.get("reportTableData", [])
def parse_close_date_iso(close_str_iso):
    try:
        return datetime.strptime(close_str_iso, "%Y-%m-%d").date()
    except Exception:
        return None

def filter_ipos(ipos):
    filtered = []
    today = datetime.today().date()

    for ipo in ipos:
        category = ipo.get("~IPO_Category", "")
        gmp_raw = ipo.get("GMP", "")
        gmp = parse_gmp(gmp_raw) 
        close_date = parse_close_date_iso(ipo.get("~Srt_Close", ""))
        
        if not close_date or close_date < today:
            continue

        if category == "SME" and gmp >= 60:
            filtered.append(ipo)
        elif category == "IPO" and gmp >= 20:
            filtered.append(ipo)

    return filtered

def format_as_html_table(ipos):
    ipo_rows = ""
    sme_rows = ""

    for ipo in ipos:
        category = ipo.get("~IPO_Category", "")
        name_link = f"https://www.investorgain.com{ipo.get('~urlrewrite_folder_name', '#')}"
        name = unescape(re.sub(r"<.*?>", "", ipo.get("Name", "")))
        gmp = ipo.get("GMP", "")
        open_dt = ipo.get("Open", "")
        close_dt = ipo.get("Close", "")
        price = ipo.get("Price", "") 
        size = ipo.get("IPO Size", "")
        pe = ipo.get("~P/E", "")
        sub = ipo.get("Sub", "")

        row = f"""
        <tr>
            <td><a href="{name_link}" target="_blank">{name}</a></td>
            <td>{gmp}</td>
            <td>{open_dt}</td>
            <td>{close_dt}</td>
            <td>{price}</td>
            <td>{sub}</td>
            <td>{size}</td>
            <td>{pe}</td>
        </tr>
        """

        if category == "IPO":
            ipo_rows += row
        elif category == "SME":
            sme_rows += row

    def build_table(title, rows):
        if not rows:
            return f"<p><b>{title}:</b> No entries found.</p>"
        return f"""
        <h3>{title}</h3>
        <table border="1" cellpadding="6" cellspacing="0" style="border-collapse: collapse; font-family: Arial, sans-serif; font-size: 14px;">
            <thead style="background-color: #f2f2f2;">
                <tr>
                    <th>Name</th>
                    <th>GMP</th>
                    <th>Open</th>
                    <th>Close</th>
                    <th>Price</th>
                    <th>Sub</th>
                    <th>IPO Size</th>
                    <th>P/E</th>
                </tr>
            </thead>
            <tbody>{rows}</tbody>
        </table><br/>
        """

    html = f"""
    <html>
    <body>
        <h2>🚀 IPOs with High GMP</h2>
        <p>Filtered on {datetime.today().strftime('%d-%b-%Y')}</p>
        {build_table("IPO", ipo_rows)}
        {build_table("SME", sme_rows)}
    </body>
    </html>
    """

    return html

def main():
    ipos = fetch_gmp_data()
    filtered_ipos = filter_ipos(ipos)

    if not filtered_ipos:
        print("No IPOs matched your criteria today.")
        return
    
    # Pass full filtered IPOs (with complete data) to HTML formatter
    html_body = format_as_html_table(filtered_ipos)

    recipients = os.environ.get("NOTIFY_EMAILS", "")
    if recipients:
        to_emails = [email.strip() for email in recipients.split(",")]
        send_email(
            subject="🚨 GMP IPO Alert - " + datetime.today().strftime('%d-%b-%Y'),
            body=html_body,
            to_emails=to_emails,
            is_html=True
        )
    else:
        print("NOTIFY_EMAILS environment variable not set; skipping email.")

if __name__ == "__main__":
    main()
