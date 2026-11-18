import os
import json
import streamlit as st
from agents_core import call_llm, read_github_file, push_to_github, extract_youtube_transcript

st.set_page_config(page_title="CreatorOps AI & Agent Command Center", page_icon="🚀", layout="wide")

# --- 1. ROLE-BASED AUTHENTICATION (ADMIN VS. CUSTOMER BETA) ---
if "role" not in st.session_state:
    st.session_state.role = None

if not st.session_state.role:
    col_l, col_m, col_r = st.columns([1, 1.4, 1])
    with col_m:
        st.title("🚀 CreatorOps AI")
        st.subheader("Turn 1 Video Into 15 Platform-Native Assets & Brand Deals in 30 Seconds")
        st.markdown("Sign in with your **Beta Access Code** or **Admin Password** to continue.")
        access_key = st.text_input("Access Code / Password", type="password")
        if st.button("Enter Workspace", type="primary", use_container_width=True):
            admin_pwd = os.getenv("ADMIN_PASSWORD") or os.getenv("DASHBOARD_PASSWORD", "admin123")
            beta_code = os.getenv("BETA_ACCESS_CODE", "CREATORBETA2026")
            if access_key == admin_pwd:
                st.session_state.role = "admin"
                st.rerun()
            elif access_key == beta_code:
                st.session_state.role = "customer"
                st.rerun()
            else:
                st.error("Invalid Access Code or Password.")
    st.stop()

is_admin = st.session_state.role == "admin"

# --- 2. SHARED CREATOR WORKSPACE FUNCTIONS (AGENTS 1, 2 & 5) ---
def render_creator_studio():
    st.header("🎬 1 Video → 15 Social Assets + Viral Clip Timestamps")
    col_in, col_voice = st.columns([1.2, 1])
    with col_in:
        yt_url = st.text_input("Paste YouTube Video URL", placeholder="https://www.youtube.com/watch?v=...")
        cta_link = st.text_input("Your Call-to-Action Link (Optional)", placeholder="https://yournewsletter.com or channel URL")
        raw_script = st.text_area("Or Paste Raw Video Script / Transcript Directly", height=110)
    with col_voice:
        voice_samples = st.text_area(
            "Brand Voice Samples (Paste 2–3 past posts to clone your tone)",
            value="Direct, tactical, zero fluff. Short punchy sentences, real numbers, actionable steps.",
            height=225
        )

    if st.button("⚡ Generate 15 Assets & Find Viral Clips", type="primary"):
        source_text = raw_script.strip()
        if not source_text and yt_url.strip():
            with st.spinner("🎙️ Agent 1: Extracting timestamped YouTube transcript..."):
                try:
                    source_text = extract_youtube_transcript(yt_url.strip())
                except Exception as e:
                    st.error(f"Transcript extraction failed: {e}")
                    st.stop()

        if not source_text:
            st.warning("Please enter a YouTube URL or paste a transcript first.")
            st.stop()

        with st.spinner("🎙️ Agent 1: Analyzing Brand Voice & Finding Top 3 Viral Clip Timestamps..."):
            brief = call_llm([
                {
                    "role": "system",
                    "content": (
                        "You are Agent 1: Transcript, Viral Clip & Brand Voice Analyst. Analyze the timestamped transcript "
                        "and Brand Voice samples. Output two crisp sections:\n"
                        "### 1. Brand Voice DNA & Core Thesis\n"
                        "Summarize tone, pacing, core thesis, top 5 actionable insights, and key stats.\n"
                        "### 2. Top 3 Viral Short-Form Clip Timestamps (For CapCut / Premiere Editing)\n"
                        "Identify the 3 highest-retention 30-to-60 second segments using the [MM:SS] timestamps in the transcript. "
                        "For each clip, list: Exact Start -> End Timestamp, Viral 3-Second Hook, and Why It Will Perform."
                    )
                },
                {"role": "user", "content": f"BRAND VOICE SAMPLES:\n{voice_samples}\n\nTIMESTAMPED TRANSCRIPT:\n{source_text[:11000]}"}
            ], temperature=0.2)
            st.session_state.creator_brief = brief

        link_rule = f"Use this exact CTA link where appropriate: {cta_link.strip()}" if cta_link.strip() else "Do NOT include any URLs or [link] placeholders anywhere."

        with st.spinner("🚀 Agent 2: Multiplying into 15 platform-native assets..."):
            assets = call_llm([
                {
                    "role": "system",
                    "content": (
                        "You are Agent 2: Omni-Channel Content Multiplier. Generate ALL 15 assets matching the Brand Voice DNA:\n"
                        "### Short-Form Video Scripts (Assets 1-3: Shorts, Reels, TikTok scripts tied to the top timestamps)\n"
                        "### LinkedIn Authority Suite (Assets 4-6: Storytelling post, Tactical checklist post, 7-Slide Carousel)\n"
                        "### X / Twitter Growth Pack (Assets 7-9: 8-Tweet Thread [strictly <280 chars/tweet], 2 Standalone Tweets)\n"
                        "### Instagram Pack (Assets 10-12: Carousel copy, Caption + Hashtags, 3-Frame Story Poll)\n"
                        "### Owned Audience & Search (Assets 13-15: Substack Newsletter, 800-Word SEO Blog, 3 YouTube Title Hooks)\n\n"
                        f"STRICT GUARDRAIL: Never output bracketed placeholders like [link], [insert link], or [URL]. {link_rule}"
                    )
                },
                {"role": "user", "content": brief}
            ], temperature=0.4)
            st.session_state.creator_assets = assets

    if "creator_assets" in st.session_state:
        st.subheader("✂️ Agent 1: Viral Clip Timestamps & Voice Brief")
        st.markdown(st.session_state.creator_brief)
        st.divider()

        col_dl, col_fix = st.columns(2)
        full_export = f"# CreatorOps Export\n\n## Viral Clip Timestamps & Brief\n{st.session_state.creator_brief}\n\n---\n\n## 15 Ready-to-Publish Assets\n{st.session_state.creator_assets}"
        with col_dl:
            st.download_button(
                label="📥 Download Clips + All 15 Assets (.md)",
                data=full_export,
                file_name="creatorops_complete_pack.md",
                mime="text/markdown"
            )
        with col_fix:
            if st.button("🔧 Auto-Audit & Polish (Remove Placeholders & Check Limits)"):
                with st.spinner("QA Agent auditing & polishing all 15 assets..."):
                    fixed = call_llm([
                        {
                            "role": "system",
                            "content": (
                                "Inspect all 15 assets below. Remove any bracketed placeholders like [link], "
                                "ensure every tweet in the X thread is strictly under 280 characters, and output the clean 15 assets."
                            )
                        },
                        {"role": "user", "content": st.session_state.creator_assets}
                    ], temperature=0.2)
                    st.session_state.creator_assets = fixed
                    st.rerun()

        st.subheader("🚀 Agent 2: 15 Ready-to-Publish Assets")
        st.markdown(st.session_state.creator_assets)

def render_brand_deals():
    st.header("💰 Brand Deal Rate Card, Sponsor Pitches & Contract Scanner")
    col_m1, col_m2 = st.columns(2)
    with col_m1:
        niche = st.selectbox("Creator Niche", [
            "Tech / Cloud / AI / SaaS (High CPM)",
            "Finance / Investing / Business (High CPM)",
            "Education / Career / Productivity (Medium-High CPM)",
            "Health / Fitness / Lifestyle (Medium CPM)",
            "Gaming / Entertainment / Vlogs (Standard CPM)"
        ])
        platform = st.selectbox("Primary Platform", ["YouTube Long-Form", "Instagram Reels", "LinkedIn", "X (Twitter)", "Newsletter"])
        avg_views = st.number_input("Average Views / Impressions per Post", min_value=500, value=15000, step=500)
    with col_m2:
        audience_geo = st.selectbox("Primary Audience Region", [
            "Tier-1 Global (US, UK, Canada, Australia, EU)",
            "Mixed Global + India / APAC",
            "India / Emerging Markets"
        ])
        target_brand = st.text_input("Target Sponsor Brand Name (Optional)", placeholder="e.g., Notion, Hostinger, NordVPN")
        contract_text = st.text_area("Paste Sponsor Offer / Contract Clauses to Scan for Red Flags (Optional)", height=105)

    if st.button("💸 Generate Rate Card, Pitch Emails & Red-Flag Audit", type="primary"):
        video_context = f"\n\nRECENT VIDEO TOPIC BRIEF:\n{st.session_state.creator_brief[:4000]}" if "creator_brief" in st.session_state else ""
        with st.spinner("💰 Calculating market rates, drafting pitches & auditing contract terms..."):
            deals_prompt = [
                {
                    "role": "system",
                    "content": (
                        "You are a Senior Creator Talent Manager. Provide realistic sponsorship pricing (USD & INR) and scripts:\n"
                        "### 1. Fair Market Sponsorship Rate Card (Table)\n"
                        "Include: 30-sec Mid-Roll, 60-sec Dedicated Segment, Social Cross-Post Bundle, and +30% Paid Usage Rights.\n"
                        "### 2. Sponsor Outreach Pitch & Counter-Offer Emails\n"
                        "### 3. Contract & Offer Red-Flag Audit (with redline fixes)"
                    )
                },
                {
                    "role": "user",
                    "content": (
                        f"Niche: {niche}\nPlatform: {platform}\nAverage Views: {avg_views:,}\n"
                        f"Audience: {audience_geo}\nTarget Brand: {target_brand or 'Relevant Niche Sponsor'}\n"
                        f"Contract Text:\n{contract_text or 'None provided - list top traps to avoid.'}{video_context}"
                    )
                }
            ]
            st.session_state.brand_deal_pack = call_llm(deals_prompt, temperature=0.3)

    if "brand_deal_pack" in st.session_state:
        st.download_button(
            label="📥 Download Rate Card & Pitch Pack (.md)",
            data=st.session_state.brand_deal_pack,
            file_name="creatorops_brand_deals.md",
            mime="text/markdown"
        )
        st.markdown(st.session_state.brand_deal_pack)

# --- 3. SIDEBAR & ROLE-BASED ROUTING ---
if is_admin:
    st.sidebar.title("🛡️ Admin Command Center")
    st.sidebar.success("Logged in as: **System Admin**")
    st.sidebar.markdown("**Live Blog:** [enterprise-infra-blog.pages.dev](https://enterprise-infra-blog.pages.dev/)")
    if st.sidebar.button("🚪 Logout"):
        st.session_state.role = None
        st.rerun()

    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "🎬 CreatorOps Studio",
        "💰 Brand Deals (Agent 5)",
        "🧪 Test Agent (Agent 3)",
        "🛡️ Web-Security (Agent 4)",
        "💬 Direct Agent Chat",
        "⚙️ Admin & Blog Queue"
    ])

    with tab1:
        render_creator_studio()
    with tab2:
        render_brand_deals()
    with tab3:
        st.header("🧪 Agent 3: Automated QA & Test Agent")
        test_mode = st.selectbox("Select Test Target", [
            "Audit Generated 15 CreatorOps Assets",
            "Audit Latest Blog Lab Post on GitHub",
            "Generate Pytest Unit Tests for Python Code"
        ])
        custom_code = st.text_area("Paste Python Code (for Pytest mode)", height=150) if "Pytest" in test_mode else ""
        if st.button("▶️ Run Test Agent"):
            with st.spinner("Agent 3: Running QA verification..."):
                if "CreatorOps" in test_mode:
                    if "creator_assets" not in st.session_state:
                        st.warning("Generate CreatorOps assets in Tab 1 first.")
                        st.stop()
                    target = st.session_state.creator_assets
                    instr = "Audit these 15 assets: check X tweets (<280 chars), zero placeholders, and strong hooks. Output Pass/Fail table."
                elif "Blog Lab" in test_mode:
                    curr = json.loads(read_github_file("agent/curriculum.json"))
                    done = [c for c in curr if c.get("done")]
                    latest = done[-1] if done else curr[0]
                    target = read_github_file(f"content/posts/{latest['slug']}.md")
                    instr = f"Audit `{latest['slug']}.md`: check YAML frontmatter, >1500 words, and double-quoted Mermaid labels."
                else:
                    target = custom_code
                    instr = "Write a complete pytest test suite covering edge cases and failure modes."
                st.markdown(call_llm([
                    {"role": "system", "content": "You are Agent 3: Principal QA Automation & SDET Engineer."},
                    {"role": "user", "content": f"{instr}\n\nDATA:\n{target[:20000]}"}
                ]))
    with tab4:
        st.header("🛡️ Agent 4: Web-Security & AppSec Auditor")
        sec_task = st.selectbox("Select Security Scan", [
            "Scan GitHub Blog Repo for Exposed Secrets & Workflow Risks",
            "Audit Code / API for OWASP Top 10 & Prompt Injection",
            "Generate Production Security Headers (CSP, HSTS, CORS)"
        ])
        sec_input = st.text_area("Paste Code, Config, or Domain (Optional)", height=150)
        if st.button("🛡️ Run Web-Security Agent"):
            with st.spinner("Agent 4: Performing AppSec scan..."):
                if "GitHub Blog" in sec_task:
                    payload = (
                        f"WORKFLOW:\n{read_github_file('.github/workflows/daily-lab-publisher.yml')}\n\n"
                        f"PUBLISHER:\n{read_github_file('agent/auto_publisher.py')}\n\n"
                        f"HUGO:\n{read_github_file('hugo.toml')}"
                    )
                    prompt = "Audit these files for hardcoded secrets, GitHub Actions over-privileges, and XSS risks. Rate severity and provide fixes."
                elif "OWASP" in sec_task:
                    payload = sec_input
                    prompt = "Perform an OWASP Top 10 & LLM Prompt-Injection review on this code and provide patched secure code."
                else:
                    payload = sec_input or "Domain: enterprise-infra-blog.pages.dev + CreatorOps SaaS"
                    prompt = "Generate hardened Cloudflare _headers (HSTS, CSP compatible with Mermaid.js & AdSense, X-Frame-Options)."
                st.markdown(call_llm([
                    {"role": "system", "content": "You are Agent 4: Principal Application Security Engineer & Pentester."},
                    {"role": "user", "content": f"{prompt}\n\nTARGET:\n{payload[:20000]}"}
                ]))
    with tab5:
        st.header("💬 Direct Chat With Any of Your 5 Agents")
        agent_choice = st.selectbox("Choose Agent", [
            "Agent 1: Transcript, Viral Clip & Brand Voice Analyst",
            "Agent 2: 1-to-15 Content Multiplier",
            "Agent 3: Automated QA & Test Engineer",
            "Agent 4: Principal Web-Security Architect",
            "Agent 5: Brand Deal & Sponsorship Strategist"
        ])
        if "chat_history" not in st.session_state:
            st.session_state.chat_history = []
        for m in st.session_state.chat_history:
            with st.chat_message(m["role"]):
                st.markdown(m["content"])
        msg = st.chat_input(f"Message {agent_choice}...")
        if msg:
            st.session_state.chat_history.append({"role": "user", "content": f"**[{agent_choice}]** {msg}"})
            with st.chat_message("user"):
                st.markdown(f"**[{agent_choice}]** {msg}")
            ctx = f"\n\nCURRENT ASSETS:\n{st.session_state.creator_assets[:8000]}" if "creator_assets" in st.session_state else ""
            with st.chat_message("assistant"):
                with st.spinner("Thinking..."):
                    reply = call_llm([
                        {"role": "system", "content": f"You are {agent_choice}.{ctx}"},
                        {"role": "user", "content": msg}
                    ])
                    st.markdown(reply)
                    st.session_state.chat_history.append({"role": "assistant", "content": reply})
    with tab6:
        st.header("⚙️ Admin Controls & Enterprise Infra Blog Queue")
        st.info(f"**Customer Beta Access Code:** `{os.getenv('BETA_ACCESS_CODE', 'CREATORBETA2026')}` (Share this code with beta testers)")
        try:
            curr_raw = read_github_file("agent/curriculum.json")
            curr_data = json.loads(curr_raw)
            pending_count = sum(1 for x in curr_data if not x.get("done"))
            st.metric("Pending Automated Blog Labs in Queue", pending_count)
            if st.button("➕ Auto-Generate 10 New Blog Labs & Push to GitHub"):
                with st.spinner("Principal IT Architect generating 10 new Beginner-to-Expert labs..."):
                    new_json = call_llm([
                        {
                            "role": "system",
                            "content": (
                                "Output ONLY valid JSON (no markdown fences). Keep all existing items in the provided "
                                "curriculum.json array and append 10 brand-new Beginner-to-Expert lab topics across Hardware, "
                                "CCNA, Cyber Security, Ethical Hacking, AWS, Azure, GCP, DevOps, and DevSecOps with 'done': false."
                            )
                        },
                        {"role": "user", "content": curr_raw}
                    ], temperature=0.3)
                    parsed = json.loads(new_json)
                    res = push_to_github("agent/curriculum.json", json.dumps(parsed, indent=2), "Admin Dashboard: Append 10 new lab topics")
                    st.success(f"{res} — Total topics now: {len(parsed)}")
            st.dataframe(curr_data, use_container_width=True)
        except Exception as e:
            st.error(f"Could not load blog curriculum: {e}")

else:
    # --- CUSTOMER BETA STOREFRONT VIEW ---
    st.sidebar.title("🚀 CreatorOps Beta")
    st.sidebar.info(
        "**Your Creator Toolkit:**\n"
        "- ✂️ Viral Clip Timestamp Finder\n"
        "- 📱 15 Platform-Native Posts\n"
        "- 💰 Sponsor Rate Card & Pitches"
    )
    if st.sidebar.button("🚪 Logout"):
        st.session_state.role = None
        st.rerun()

    c_tab1, c_tab2 = st.tabs(["🎬 1 Video → 15 Assets & Viral Clips", "💰 Brand Deal Rate Card & Pitches"])
    with c_tab1:
        render_creator_studio()
    with c_tab2:
        render_brand_deals()
