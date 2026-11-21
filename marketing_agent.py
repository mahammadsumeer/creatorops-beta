import os
import imaplib
import email
from datetime import datetime, timezone
from email.header import decode_header
from agents_core import get_secret, call_llm, send_gmail, load_trials, save_trials

def check_inbox_and_reply(trials):
    user = get_secret("GMAIL_USER")
    pwd = get_secret("GMAIL_APP_PASSWORD")
    if not user or not pwd:
        return trials
    imap_host = "imap." + "gmail" + ".com"
    tmap = {t["email"].lower(): t for t in trials}
    try:
        mail = imaplib.IMAP4_SSL(imap_host)
        mail.login(user, pwd)
        mail.select("INBOX")
        _, msgs = mail.search(None, "UNSEEN")
        for num in msgs.split():
            _, data = mail.fetch(num, "(RFC822)")
            msg = email.message_from_bytes(data)
            sender = email.utils.parseaddr(msg.get("From", "")).lower()
            subj = str(decode_header(msg.get("Subject", "")))
            body = ""
            if msg.is_multipart():
                for part in msg.walk():
                    if part.get_content_type() == "text/plain":
                        body = part.get_payload(decode=True).decode("utf-8", errors="ignore")
                        break
            else:
                body = msg.get_payload(decode=True).decode("utf-8", errors="ignore")
            if sender in tmap:
                tmap[sender].setdefault("feedback_log", []).append({
                    "time": datetime.now(timezone.utc).isoformat(),
                    "text": body[:500]
                })
                reply = call_llm([
                    {"role": "system", "content": "You are the CreatorOps AI Success Agent. Reply warmly and helpfully in under 90 words."},
                    {"role": "user", "content": f"Creator wrote: {body[:1000]}"}
                ])
                send_gmail(sender, f"Re: {subj or 'CreatorOps AI'}", reply)
        mail.logout()
    except Exception as e:
        print(f"[WARN] IMAP scan error: {e}")
    return trials

def run_lifecycle_agent():
    trials = check_inbox_and_reply(load_trials())
    now = datetime.now(timezone.utc)
    changed = False
    for t in trials:
        created = datetime.fromisoformat(t["created_at"])
        expires = datetime.fromisoformat(t["expires_at"])
        hrs = (now - created).total_seconds() / 3600
        if hrs >= 48 and not t.get("day2_sent") and now < expires:
            msg = call_llm([
                {"role": "system", "content": "Write a friendly 60-word Day-2 check-in email asking which of the 15 assets or Viral Clip Timestamps saved them the most time."},
                {"role": "user", "content": f"Creator: {t['email']} - Channel: {t.get('channel_url', 'N/A')}"}
            ])
            send_gmail(t["email"], "Quick question on your CreatorOps AI trial", msg)
            t["day2_sent"] = True
            changed = True
        if now >= expires and not t.get("day3_sales_sent"):
            fb = "; ".join([f["text"] for f in t.get("feedback_log", [])])
            pitch = call_llm([
                {"role": "system", "content": "Write a persuasive post-trial sales email: their 3-day trial ended, recap how turning 1 30-min video into 15 assets + Brand Deal Rate Cards saves 5+ hrs/week, and invite them to reply UPGRADE for the Founder Early-Bird Plan ($19/mo or Rs 1,499/mo)."},
                {"role": "user", "content": f"Creator: {t['email']} - Feedback: {fb or 'None yet'}"}
            ])
            send_gmail(t["email"], "Your 3-day CreatorOps AI trial ended - Founder Offer inside", pitch)
            t["day3_sales_sent"] = True
            changed = True
    if changed or any(t.get("feedback_log") for t in trials):
        save_trials(trials)
    print("[OK] Marketing & Lifecycle Agent finished.")

if __name__ == "__main__":
    run_lifecycle_agent()
