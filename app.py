import streamlit as st
import requests
from dotenv import load_dotenv
import os
import time

load_dotenv()

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Game Design Studio",
    page_icon="🎮",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── CSS ────────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@500;700&family=Rajdhani:wght@400;600&display=swap');
:root {
    --bg:#0a0a0f; --surface:#12121a; --border:#2a2a3a;
    --accent:#7c3aed; --accent2:#10b981; --text:#e2e8f0; --muted:#64748b;
}
html,body,[data-testid="stAppViewContainer"]{
    background:var(--bg)!important;color:var(--text);font-family:'Rajdhani',sans-serif;
}
h1,h2,h3{font-family:'Orbitron',monospace;}
[data-testid="stSidebar"]{background:var(--surface)!important;border-right:1px solid var(--border);}
.stTextArea textarea{
    background:var(--surface)!important;color:var(--text)!important;
    border:1px solid var(--border)!important;border-radius:8px;
    font-family:'Rajdhani',sans-serif;font-size:1rem;
}
.stButton>button{
    background:var(--accent)!important;color:white!important;border:none!important;
    border-radius:6px;font-family:'Orbitron',monospace;font-size:0.75rem;
    letter-spacing:0.1em;padding:0.6rem 1.5rem;
}
.stButton>button:hover{opacity:0.85;}
.agent-card{
    background:var(--surface);border:1px solid var(--border);
    border-radius:10px;padding:1rem 1.25rem;margin-bottom:0.75rem;
}
.agent-card.success{border-left:3px solid var(--accent2);}
.agent-card.error  {border-left:3px solid #ef4444;}
.agent-card.running{border-left:3px solid var(--accent);}
.agent-card.warning{border-left:3px solid #f59e0b;}
.agent-title{
    font-family:'Orbitron',monospace;font-size:0.7rem;
    letter-spacing:0.15em;color:var(--muted);margin-bottom:0.5rem;
}
.agent-content{font-size:0.95rem;line-height:1.7;white-space:pre-wrap;}
.model-tag{font-size:0.6rem;color:#475569;margin-bottom:4px;}
.status-badge{
    display:inline-block;font-size:0.65rem;font-family:'Orbitron',monospace;
    padding:2px 8px;border-radius:4px;letter-spacing:0.1em;margin-bottom:0.5rem;
}
.badge-ok {background:#064e3b;color:#6ee7b7;}
.badge-err{background:#450a0a;color:#fca5a5;}
.badge-run{background:#2e1065;color:#c4b5fd;}
.badge-warn{background:#451a03;color:#fcd34d;}
hr{border-color:var(--border);}
#MainMenu,footer,header{visibility:hidden;}
</style>
""", unsafe_allow_html=True)

# ── Groq models (fallback order) ──────────────────────────────────────────────
# All FREE on Groq — fast inference, high rate limits
GROQ_MODELS = [
    "llama-3.3-70b-versatile",      # Best quality, free
    "llama-3.1-8b-instant",         # Fast, free
    "llama3-70b-8192",              # Reliable, free
    "llama3-8b-8192",               # Lightweight, free
    "mixtral-8x7b-32768",           # Good quality, free
    "gemma2-9b-it",                 # Google Gemma, free
    "gemma-7b-it",                  # Smaller Gemma, free
]

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

# ── Agent definitions ──────────────────────────────────────────────────────────
AGENTS = [
    ("💡", "CONCEPT DESIGNER",   "Core concept, genre, theme & elevator pitch"),
    ("⚙️", "MECHANICS DESIGNER", "Gameplay loops, systems & mechanics"),
    ("📖", "NARRATIVE DESIGNER", "Story, world, characters & lore"),
    ("🎨", "ART DIRECTOR",       "Visual style, aesthetics & art direction"),
    ("🔍", "GAME CRITIC",        "Critical review, risks & improvements"),
    ("📋", "GDD COMPILER",       "Formal Game Design Document"),
]

AGENT_PROMPTS = {
    "CONCEPT DESIGNER": (
        "You are a veteran game concept designer. Given a game idea, produce:\n"
        "- A sharp elevator pitch (2-3 sentences)\n"
        "- Genre & sub-genre\n- Core themes\n- Target audience\n"
        "- 3 unique selling points\nBe concise, creative, and inspiring."
    ),
    "MECHANICS DESIGNER": (
        "You are a gameplay systems designer. Design:\n"
        "- Core gameplay loop (step by step)\n- 4-5 key mechanics\n"
        "- Progression system\n- Win/fail conditions\n- Player motivation hooks\n"
        "Use bullet points. Be specific and practical."
    ),
    "NARRATIVE DESIGNER": (
        "You are a narrative designer. Create:\n"
        "- Story premise (2-3 sentences)\n- World-building overview\n"
        "- 3 main characters with brief descriptions\n- 5 key story beats\n"
        "- Tone and atmosphere\nMake it compelling and game-ready."
    ),
    "ART DIRECTOR": (
        "You are a game art director. Define:\n"
        "- Visual style (e.g. pixel art, cel-shaded, realistic)\n"
        "- Color palette (4-5 key colors with hex codes)\n"
        "- UI/UX aesthetic direction\n- 3 art inspiration references\n"
        "- Key visual motifs\nBe specific and visual."
    ),
    "GAME CRITIC": (
        "You are a seasoned game critic. Evaluate:\n"
        "- Top 3 design strengths\n- Top 3 potential risks\n"
        "- Market positioning\n- 3 concrete improvement suggestions\n"
        "- Viability score (1-10) with justification\nBe honest and constructive."
    ),
    "GDD COMPILER": (
        "You are a GDD writer. Using ALL previous outputs, compile a complete GDD:\n"
        "1. GAME OVERVIEW\n2. CORE MECHANICS\n3. NARRATIVE & WORLD\n"
        "4. ART DIRECTION\n5. RISKS & MITIGATIONS\n6. DEVELOPMENT ROADMAP\n"
        "Format professionally. This is the final deliverable."
    ),
}

# ── API helpers ────────────────────────────────────────────────────────────────
def validate_key() -> tuple[bool, str]:
    key = os.getenv("GROQ_API_KEY", "").strip()
    if not key:
        return False, "GROQ_API_KEY not set in .env"
    if not key.startswith("gsk_"):
        return False, "Key should start with 'gsk_' — check your .env"
    return True, key


def call_groq(api_key: str, agent_name: str, context: str) -> tuple[str, str]:
    """
    Call Groq API with automatic model fallback.
    Returns (response_text, model_used).
    """
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    for model in GROQ_MODELS:
        for attempt in range(3):
            payload = {
                "model": model,
                "messages": [
                    {"role": "system", "content": AGENT_PROMPTS[agent_name]},
                    {"role": "user",   "content": context},
                ],
                "max_tokens": 1500,
                "temperature": 0.8,
            }

            try:
                resp = requests.post(GROQ_URL, headers=headers,
                                     json=payload, timeout=60)
                data = resp.json()

                # ✅ Success
                if resp.status_code == 200:
                    text = data["choices"][0]["message"]["content"]
                    return text.strip(), model

                # 🔑 Auth error — stop immediately
                if resp.status_code in (401, 403):
                    raise Exception(
                        "Invalid Groq API key. Check GROQ_API_KEY in your .env file."
                    )

                # ⏳ Rate limit on this model — wait briefly then try next model
                if resp.status_code == 429:
                    wait = int(resp.headers.get("Retry-After", "10"))
                    wait = min(wait, 15)  # cap at 15s
                    time.sleep(wait)
                    break  # try next model

                # ❌ Model not found — next model
                if resp.status_code in (400, 404):
                    err_msg = data.get("error", {}).get("message", "")
                    if "model" in err_msg.lower() or resp.status_code == 404:
                        break
                    # Other 400 — retry
                    time.sleep(2)
                    continue

                # Server error — retry with backoff
                if resp.status_code >= 500:
                    time.sleep(3 * (attempt + 1))
                    continue

            except requests.exceptions.Timeout:
                time.sleep(5)
                continue
            except Exception as e:
                if "Invalid Groq API key" in str(e):
                    raise
                time.sleep(2)
                continue

    raise Exception(
        "All Groq models failed. Check your internet connection or "
        "visit console.groq.com to verify your key."
    )


# ── UI ─────────────────────────────────────────────────────────────────────────
def render_card(icon, title, subtitle, state, content="", model_used=""):
    badges = {
        "idle":    "",
        "running": '<span class="status-badge badge-run">● RUNNING</span>',
        "done":    '<span class="status-badge badge-ok">✔ COMPLETE</span>',
        "error":   '<span class="status-badge badge-err">✖ ERROR</span>',
        "warning": '<span class="status-badge badge-warn">⚠ WARNING</span>',
    }
    css_map = {
        "idle":"","running":"running","done":"success","error":"error","warning":"warning"
    }
    sub  = f" · {subtitle}" if subtitle else ""
    meta = f'<div class="model-tag">model: {model_used}</div>' if model_used else ""
    body = f'<div class="agent-content">{content}</div>' if content else ""
    st.markdown(f"""
    <div class="agent-card {css_map.get(state,'')}">
        <div class="agent-title">{icon} {title}{sub}</div>
        {badges.get(state,'')}{meta}{body}
    </div>""", unsafe_allow_html=True)


# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🎮 Game Design Studio")
    st.markdown("---")

    ok, msg = validate_key()
    if ok:
        st.success("✅ Groq API key loaded")
    else:
        st.error(f"❌ {msg}")
        st.markdown("""
**Get your FREE Groq key:**
1. Go to **[console.groq.com](https://console.groq.com)**
2. Sign up (free, no credit card)
3. Click **API Keys → Create API Key**
4. Add to `.env`:
```
GROQ_API_KEY=gsk_your_key_here
```
5. Restart: `streamlit run app.py`
        """)

    st.markdown("---")
    st.markdown(f"""
**Why Groq?**
- ⚡ Fastest inference available
- ✅ Completely free
- ✅ {len(GROQ_MODELS)} model fallbacks
- ✅ Much higher rate limits
- ✅ No quota surprises

**Free Models**
""")
    for m in GROQ_MODELS:
        st.markdown(f"• `{m}`")

    st.markdown("""
---
**Agents**
💡 Concept Designer
⚙️ Mechanics Designer
📖 Narrative Designer
🎨 Art Director
🔍 Game Critic
📋 GDD Compiler
    """)

# ── Main ───────────────────────────────────────────────────────────────────────
st.markdown("## Describe your game idea")

game_idea = st.text_area(
    label="",
    placeholder="e.g. space adventure, zombie survival RPG, cozy farming sim...",
    height=120,
)

c1, _ = st.columns([1, 4])
with c1:
    run = st.button("▶ RUN AGENTS", use_container_width=True)

st.markdown("---")

# Icons row
cols = st.columns(len(AGENTS))
for col, (icon, title, _) in zip(cols, AGENTS):
    with col:
        st.markdown(
            f"<div style='text-align:center;font-size:2rem'>{icon}</div>"
            f"<div style='text-align:center;font-size:0.55rem;font-family:Orbitron,monospace;"
            f"letter-spacing:0.08em;color:#64748b;margin-top:4px'>{title}</div>",
            unsafe_allow_html=True,
        )

st.markdown("---")

# ── Run pipeline ───────────────────────────────────────────────────────────────
if run:
    if not game_idea.strip():
        st.warning("Please describe your game idea first.")
        st.stop()

    ok, key_or_msg = validate_key()
    if not ok:
        st.error(f"❌ {key_or_msg}")
        st.info("👆 See sidebar for FREE Groq key setup")
        st.stop()

    st.info(f"⚡ Groq engine ready | {len(GROQ_MODELS)} models on standby")
    accumulated = f"Game Idea: {game_idea.strip()}\n\n"

    for icon, title, subtitle in AGENTS:
        slot = st.empty()
        with slot:
            render_card(icon, title, subtitle, "running")

        prompt = (
            accumulated +
            f"\nYour role: {title}\n"
            f"Based on the game idea and all previous agent outputs above, "
            f"provide your expert {title.lower()} contribution now."
        )

        try:
            output, model_used = call_groq(key_or_msg, title, prompt)
            accumulated += f"\n\n=== {title} ===\n{output}"
            with slot:
                render_card(icon, title, subtitle, "done", output, model_used)

        except Exception as e:
            err = str(e)
            with slot:
                render_card(icon, title, subtitle, "error", err[:300])
            if "Invalid Groq API key" in err:
                st.stop()

        time.sleep(1)   # Small delay — Groq is fast so 1s is enough

    st.success("🎮 All agents complete! Your Game Design Document is ready above.")
    st.balloons()

else:
    for icon, title, subtitle in AGENTS:
        render_card(icon, title, subtitle, "idle")