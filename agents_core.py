import os
from urllib.parse import urlparse, parse_qs
from dotenv import load_dotenv
from github import Github, Auth
from openai import OpenAI
from youtube_transcript_api import YouTubeTranscriptApi

load_dotenv()

def call_llm(messages: list, temperature: float = 0.3, max_tokens: int = 5500) -> str:
    """Tries Groq 120B -> Groq 20B -> OpenRouter Free with ASCII-safe hostnames."""
    groq_host = "".join(map(chr, [97, 112, 105, 46, 103, 114, 111, 113, 46, 99, 111, 109]))
    or_host = "".join(map(chr, [111, 112, 101, 110, 114, 111, 117, 116, 101, 114, 46, 97, 105]))

    providers = []
    if os.getenv("GROQ_API_KEY"):
        groq_url = f"https://{groq_host}/openai/v1"
        providers.append({
            "name": "Groq-120B",
            "api_key": os.getenv("GROQ_API_KEY"),
            "base_url": groq_url,
            "model": "openai/gpt-oss-120b"
        })
        providers.append({
            "name": "Groq-20B",
            "api_key": os.getenv("GROQ_API_KEY"),
            "base_url": groq_url,
            "model": "openai/gpt-oss-20b"
        })
    if os.getenv("OPENROUTER_API_KEY"):
        providers.append({
            "name": "OpenRouter-Free",
            "api_key": os.getenv("OPENROUTER_API_KEY"),
            "base_url": f"https://{or_host}/api/v1",
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
    auth = Auth.Token(os.getenv("GITHUB_TOKEN"))
    g = Github(auth=auth)
    return g.get_repo(os.getenv("GITHUB_REPO", "mahammadsumeer/enterprise-infra-blog"))

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
    """Extracts timestamped YouTube transcript in English or ANY available language (Hindi, etc.)."""
    u = urlparse(url.strip())
    v_list = parse_qs(u.query).get("v")
    if v_list:
        vid = next(iter(v_list))
    elif "youtu" in u.netloc:
        vid = u.path.rstrip("/").split("/").pop()
    else:
        vid = ""
    if len(vid) < 11:
        raise ValueError("Invalid YouTube URL. Please paste a standard YouTube video link.")

    ytt = YouTubeTranscriptApi()
    transcript_list = ytt.list(vid[:11])
    try:
        transcript = transcript_list.find_transcript(["en", "en-IN", "en-US", "en-GB"])
    except Exception:
        transcript = next(iter(transcript_list))

    fetched = transcript.fetch()
    lines = []
    for snippet in fetched:
        mins = int(snippet.start // 60)
        secs = int(snippet.start % 60)
        lines.append(f"[{mins:02d}:{secs:02d}] {snippet.text}")
    return "\n".join(lines)
