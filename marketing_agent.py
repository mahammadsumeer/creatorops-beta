import os
import re
import json
import imaplib
import email
import urllib.request
import urllib.parse
from datetime import datetime, timezone
from email.header import decode_header
from github import Github, Auth
from agents_core import get_secret, call_llm, send_gmail, load_trials, save_trials

OUTREACH_NICHES = [
    "cloud computing architecture tutorial",
    "AI engineering deep dive podcast",
    "personal finance investing masterclass",
    "cybersecurity ethical hacking full course",
    "startup founder interview podcast"
]

def load_outreach_log():
    try:
        repo_name = get_secret("TRIALS_REPO", "mahammadsumeer/creatorops-beta")
        repo = Github(auth=Auth.Token(get_secret("GITHUB_TOKEN"))).get_repo(repo_name)
        raw = repo.get_contents("outreach_log.json").decoded_content.decode("utf-8")
        return json.loads(raw)
    except Exception:
        return []

def save_outreach_log(log):
    repo_name = get_secret("TRIALS_REPO", "mahammadsumeer/creatorops-beta")
    repo = Github(auth=Auth.Token(get_secret("GITHUB_TOKEN"))).get_repo(repo_name)
    content = json.dumps(log, indent=2)
    try:
        c = repo.get_contents("outreach_log.json")
        repo.update_file(c.path, "Update YouTube creator outreach log", content, c.sha)
    except Exception:
        repo.create_file("outreach_log.json", "Create YouTube creator outreach log", content)

def discover_and_invite_youtubers(max_invites=5):
    yt_key = get_secret("YOUTUBE_API_KEY")
    if not yt_key:
        print("[INFO] YOUTUBE_API_KEY not set; skipping YouTube channel discovery.")
        return

    log = load_outreach_log()
    contacted_emails = {entry.get("email", "").lower() for entry in log}
    contacted_channels = {entry.get("channel_id", "") for entry in log}
    existing_trials = {t.get("email", "").lower() for t in load_trials()}

    niche = OUTREACH_NICHES[datetime.now(timezone.utc).timetuple().tm_yday % len(OUTREACH_NICHES)]
    yt_host = "www." + "googleapis" + ".com"
    search_url = (
        f"https://{yt_host}/youtube/v3/search?part=snippet&type=video&videoDuration=long"
        f"&maxResults=50&order=relevance&q={urllib.parse.quote(niche)}&key={yt_key}"
    )

    try:
        with urllib.request.urlopen(search_url, timeout=20) as resp:
            items = json.loads(resp.read().decode("utf-8")).get("items", [])
    except Exception as e:
        print(f"[WARN] YouTube search failed: {e}")
        return

    video_ids = [it.get("id", {}).get("videoId") for it in items if it.get("id", {}).get("videoId")]
    full_video_descs = {}
    if video_ids:
        vids_url = f"https://{yt_host}/youtube/v3/videos?part=snippet&id={','.join(video_ids[:50])}&key={yt_key}"
        try:
            with urllib.request.urlopen(vids_url, timeout=20) as vresp:
                for vitem in json.loads(vresp.read().decode("utf-8")).get("items", []):
                    full_video_descs[vitem.get("id", "")] = vitem.get("snippet", {}).get("description", "")
        except Exception as e:
            print(f"[WARN] Videos full description lookup failed: {e}")

    channel_videos = {}
    for item in items:
        snip = item.get("snippet", {})
        cid = snip.get("channelId")
        vid_id = item.get("id", {}).get("videoId", "")
        if cid and cid not in contacted_channels and cid not in channel_videos:
            channel_videos[cid] = {
                "channel_title": snip.get("channelTitle", ""),
                "video_title": snip.get("title", ""),
                "video_desc": full_video_descs.get(vid_id, snip.get("description", ""))
            }

    if not channel_videos:
        print("[INFO] No new channels found in this batch.")
        save_outreach_log(log)
        return

    cids_param = ",".join(list(channel_videos.keys())[:50])
    channels_url = f"https://{yt_host}/youtube/v3/channels?part=snippet,statistics&id={cids_param}&key={yt_key}"
    try:
        with urllib.request.urlopen(channels_url, timeout=20) as resp:
            ch_items = json.loads(resp.read().decode("utf-8")).get("items", [])
    except Exception as e:
        print(f"[WARN] YouTube channels lookup failed: {e}")
        return

    sent_count = 0
    for ch in ch_items:
        if sent_count >= max_invites:
            break
        cid = ch.get("id", "")
        snip = ch.get("snippet", {})
        desc = snip.get("description", "")
        subs = int(ch.get("statistics", {}).get("subscriberCount", 0))

        if subs < 1000 or subs > 2000000:
            continue

        combined_text = desc + "\n" + channel_videos[cid].get("video_desc", "")
        emails_found = re.findall(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", combined_text)
        valid_emails = [
            e.lower() for e in emails_found
            if not e.lower().endswith((".png", ".jpg", "example.com", "sentry.io"))
        ]
        if not valid_emails:
            continue

        target_email = next(iter(valid_emails))
        if target_email in contacted_emails or target_email in existing_trials:
            continue

        ch_title = channel_videos[cid]["channel_title"]
        vid_title = channel_videos[cid]["video_title"]
        pitch = call_llm([
            {
                "role": "system",
                "content": (
                    "You are the Founder of CreatorOps AI (https://streamlit.app). "
                    "Write a short, respectful, non-spammy 85-word cold outreach email to a YouTube creator who makes 30+ minute videos. "
                    "Reference their recent long-form video title naturally, explain how CreatorOps AI turns 1 long video into "
                    "3 timestamped Shorts clips, 15 LinkedIn/X/newsletter posts, and a Sponsor Rate Card in 30 seconds, "
                    "and invite them to claim a free 3-day full-access trial at https://streamlit.app."
                )
            },
            {
                "role": "user",
                "content": f"Channel: {ch_title} ({subs:,} subscribers) | Recent Long Video: {vid_title}"
            }
        ], temperature=0.4)

        try:
            send_gmail(target_email, f"Quick idea for {ch_title}'s long-form videos", pitch)
            log.append({
                "channel_id": cid,
                "channel_title": ch_title,
                "email": target_email,
                "subscribers": subs,
                "video_title": vid_title,
                "sent_at": datetime.now(timezone.utc).isoformat()
            })
            contacted_emails.add(target_email)
            contacted_channels.add(cid)
            sent_count += 1
            print(f"[SENT] Cold trial invite sent to {ch_title} ({target_email})")
        except Exception as e:
            print(f"[WARN] Failed sending invite to {target_email}: {e}")

    save_outreach_log(log)
    print(f"[OK] YouTube discovery finished. Invites sent: {sent_count}")

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
    discover_and_invite_youtubers(max_invites=5)
    print("[OK] Marketing & Lifecycle Agent finished.")

if __name__ == "__main__":
    run_lifecycle_agent()
