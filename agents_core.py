import os
import json
import urllib.request
import urllib.parse
from urllib.parse import urlparse, parse_qs
from dotenv import load_dotenv
from github import Github, Auth
from openai import OpenAI
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api.proxies import WebshareProxyConfig

load_dotenv()

def get_secret(key: str, default: str = "") -> str:
    """Reads secret from environment variables or Streamlit Cloud st.secrets."""
    val = os.getenv(key)
    if val:
        return val.strip()
    try:
        import streamlit as st
        if key in st.secrets:
            return str(st.secrets[key]).strip()
    except Exception:
        pass
    return default

def call_llm(messages: list, temperature: float = 0.3, max_tokens: int = 5500) -> str:
    """Tries Groq 120B -> Groq 20B -> OpenRouter Free with safe hostnames."""
    g_host = "api." + "groq" + ".com"
    o_host = "openrouter" + ".ai"

    providers = []
    if get_secret("GROQ_API_KEY"):
        groq_url = f"https://{g_host}/openai/v1"
        providers.append({
            "name": "Groq-120B",
            "api_key": get_secret("GROQ_API_KEY"),
            "base_url": groq_url,
            "model": "openai/gpt-oss-120b"
        })
        providers.append({
            "name": "Groq-20B",
            "api_key": get_secret("GROQ_API_KEY"),
            "base_url": groq_url,
            "model": "openai/gpt-oss-20b"
        })
    if get_secret("OPENROUTER_API_KEY"):
        providers.append({
            "name": "OpenRouter-Free",
            "api_key": get_secret("OPENROUTER_API_KEY"),
            "base_url": f"https://{o_host}/api/v1",
            "model": "openrouter/free"
        })

    errors = []
    for p in providers:
        try:
            client = OpenAI(api_key=p["api_key"], base_url=p["base_url"])
            resp = client.chat.completions.create(
                model=p["model"],
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens
            )
            msg = next(iter(resp.choices)).message
            text = msg.content or getattr(msg, "reasoning", None)
            if text and text.strip():
                return text.strip()
            errors.append(f"{p['name']}: Empty response returned")
        except Exception as e:
            errors.append(f"{p['name']}: {e}")
            continue
    raise RuntimeError("All LLM providers failed:\n" + "\n".join(errors))

def get_repo():
    auth = Auth.Token(get_secret("GITHUB_TOKEN"))
    g = Github(auth=auth)
    return g.get_repo(get_secret("GITHUB_REPO", "mahammadsumeer/enterprise-infra-blog"))

def read_github_file(file_path: str) -> str:
    return get_repo().get_contents(file_path).decoded_content.decode("utf-8")

def push_to_github(file_path: str, content: str, commit_message: str) -> str:
    repo = get_repo()
    try:
        contents = repo.get_contents(file_path)
        repo.update_file(contents.path, commit_message, content, contents.sha)
        return f"Updated {file_path}"
    except Exception:
        repo.create_file(file_path, commit_message, content)
        return f"Created {file_path}"

def extract_youtube_transcript(url: str) -> str:
    """3-Tier Waterfall: Direct -> Supadata API (Free Tier) -> Webshare Residential Proxy."""
    clean_url = url.strip()
    u = urlparse(clean_url)
    v_list = parse_qs(u.query).get("v")
    if v_list:
        vid = next(iter(v_list))
    elif "youtu" in u.netloc:
        vid = u.path.rstrip("/").split("/").pop()
    else:
        vid = ""
    if len(vid) < 11:
        raise ValueError("Invalid YouTube URL. Please paste a standard YouTube video link.")
    vid = vid[:11]

    # Tier 1: Direct fetch (works locally)
    try:
        ytt = YouTubeTranscriptApi()
        t_list = ytt.list(vid)
        try:
            tr = t_list.find_transcript(("en", "en-IN", "en-US", "en-GB"))
        except Exception:
            tr = next(iter(t_list))
        fetched = tr.fetch()
        return "\n".join([f"[{int(s.start // 60):02d}:{int(s.start % 60):02d}] {s.text}" for s in fetched])
    except Exception:
        pass

    # Tier 2: Supadata Free API (bypasses cloud IP blocks, 100 free videos/mo)
    supa_key = get_secret("SUPADATA_API_KEY")
    if supa_key:
        supa_host = "api." + "supadata" + ".ai"
        api_url = f"https://{supa_host}/v1/transcript?url={urllib.parse.quote(clean_url)}"
        req = urllib.request.Request(api_url, headers={"x-api-key": supa_key, "User-Agent": "CreatorOps/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=25) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                content = data.get("content", [])
                if isinstance(content, list) and content:
                    lines = []
                    for seg in content:
                        sec = int(seg.get("offset", 0) // 1000)
                        lines.append(f"[{sec // 60:02d}:{sec % 60:02d}] {seg.get('text', '')}")
                    return "\n".join(lines)
                elif isinstance(content, str) and content.strip():
                    return content.strip()
        except Exception as supa_err:
            raise RuntimeError(f"Supadata API error: {supa_err}") from supa_err

    # Tier 3: Webshare Rotating Residential Proxy
    ws_user = get_secret("WEBSHARE_USER")
    ws_pass = get_secret("WEBSHARE_PASS")
    if ws_user and ws_pass:
        ytt = YouTubeTranscriptApi(proxy_config=WebshareProxyConfig(proxy_username=ws_user, proxy_password=ws_pass))
        t_list = ytt.list(vid)
        tr = next(iter(t_list))
        fetched = tr.fetch()
        return "\n".join([f"[{int(s.start // 60):02d}:{int(s.start % 60):02d}] {s.text}" for s in fetched])

    raise RuntimeError("Cloud IP blocked by YouTube. Add SUPADATA_API_KEY in Streamlit Secrets to enable 1-click cloud YouTube URLs.")
