import streamlit as st
import requests
from dotenv import load_dotenv
import os
import time
import re
import markdown as md


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
    --bg:      #0d0b1a;   /* deep indigo-black background */
    --surface: #16132b;   /* card background - dark violet */
    --border:  #3d2f6b;   /* soft purple border */
    --accent:  #d4af37;   /* antique gold - headings/highlights */
    --text:    #e8e6f0;   /* soft off-white for readability */
}
html,body,[data-testid="stAppViewContainer"]{
    body { background-color: var(--bg); color: var(--text); }font-family:'Rajdhani',sans-serif;
}
h1,h2,h3{font-family:'Orbitron',monospace;}
[data-testid="stSidebar"]{background:var(--surface)!important;border-right:1px solid var(--border);}
.stTextArea textarea{
    background:var(--surface)!important;color:var(--text)!important;
    border:1px solid var(--border)!important;border-radius:8px;
    font-family:'Rajdhani',sans-serif;font-size:1rem;
}
.stButton>button{
    background:#7c3aed!important;color:white!important;border:none!important;
    border-radius:6px;font-family:'Orbitron',monospace;font-size:0.75rem;
    letter-spacing:0.1em;padding:0.6rem 1.5rem;
}
.stButton>button:hover{opacity:0.85;background:#6d28d9!important;}
.agent-card {
    background: var(--surface);
    border-left: 4px solid var(--accent);   /* gold left border like before, but warmer */
    border-radius: 8px;
    padding: 20px;
    margin-bottom: 16px;
}
.agent-card.success {
    border: 2px solid #22c55e !important;
    border-radius: 10px;
    box-shadow: 0 0 8px rgba(34,197,94,0.3);
}
.agent-card.error {
    border: 2px solid #ef4444 !important;
    border-radius: 10px;
    box-shadow: 0 0 8px rgba(239,68,68,0.3);
}
.agent-card.running {
    border: 2px solid #3b82f6 !important;
    border-radius: 10px;
}
.agent-card.warning{border-left:3px solid #f59e0b;}
.agent-title{
    font-family:'Orbitron',monospace;font-size:0.7rem;
    letter-spacing:0.15em;color:var(--muted);margin-bottom:0.5rem;
}
.agent-content h1, .agent-content h2, .agent-content h3,
.agent-content strong {
    color: var(--accent);
}

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
    "openai/gpt-oss-20b",              # Fast, free
    "openai/gpt-oss-120b",             # Reliable, free
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

    last_error = "No response received"

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
                response = requests.post(GROQ_URL, headers=headers,
                                          json=payload, timeout=60)
                data = response.json()

                # Success
                if response.status_code == 200:
                    text = data["choices"][0]["message"]["content"]
                    return text.strip(), model

                # Auth error - stop immediately
                if response.status_code in (401, 403):
                    raise Exception(
                        "Invalid Groq API key. Check GROQ_API_KEY in your .env file."
                    )

                # Rate limit on this model - wait briefly then try next model
                if response.status_code == 429:
                    wait = int(response.headers.get("Retry-After", "10"))
                    wait = min(wait, 30)  # cap at 15s
                    last_error = f"Rate limited on {model}"
                    time.sleep(wait)
                    break  # try next model

                # Model not found - next model
                if response.status_code in (400, 404):
                    err_msg = data.get("error", {}).get("message", "")
                    last_error = f"{model}: {response.status_code} - {err_msg}"
                    if "model" in err_msg.lower() or response.status_code == 404:
                        break
                    time.sleep(2)
                    continue

                # Server error - retry with backoff
                if response.status_code >= 500:
                    last_error = f"{model}: server error {response.status_code}"
                    time.sleep(3 * (attempt + 1))
                    continue

            except requests.exceptions.Timeout:
                last_error = f"{model}: timeout"
                time.sleep(5)
                continue
            except Exception as e:
                if "Invalid Groq API key" in str(e):
                    raise
                last_error = f"{model}: {str(e)}"
                time.sleep(2)
                continue

    raise Exception(f"All Groq models failed. Last error: {last_error}")

# ── UI ─────────────────────────────────────────────────────────────────────────
def render_card(icon, title, subtitle, state, content="", model_used=""):
    badges = {
        "idle":    "",
        "running": '<span class="status-badge badge-run">● RUNNING</span>',
        "done":    '<span class="status-badge badge-ok">✓ COMPLETE</span>',
        "error":   '<span class="status-badge badge-err">✕ ERROR</span>',
        "warning": '<span class="status-badge badge-warn">⚠ WARNING</span>',
    }
    css_map = {"idle":"","running":"running","done":"success","error":"error","warning":"warning"}
    sub  = f" · {subtitle}" if subtitle else ""
    meta = f'<div class="model-tag">model: {model_used}</div>' if model_used else ""
    content_html = md.markdown(content, extensions=["extra"]) if content else ""
    body = f'<div class="agent-content">{content_html}</div>' if content else ""

    st.markdown(f"""
    <div class="agent-card {css_map.get(state,'')}">
        <div class="agent-title">{icon} {title}{sub}</div>
        {badges.get(state,'')}{meta}{body}
    </div>
    """, unsafe_allow_html=True)


    

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
icon_slots = []
cols = st.columns(len(AGENTS))
for col, (icon, title, subtitle) in zip(cols, AGENTS):
    with col:
        slot = st.empty()
        slot.markdown(
            f"<div style='text-align:center;font-size:2rem;padding:8px;border-radius:8px;"
            f"border:2px solid transparent'>{icon}</div>"
            f"<div style='text-align:center;font-size:0.55rem;font-family:Orbitron,monospace;"
            f"letter-spacing:0.08em;color:#64748b;margin-top:4px'>{title}</div>",
            unsafe_allow_html=True,
        )
        icon_slots.append((slot, icon, title))

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

            # NEW — turn the icon green
            for icon_slot, icon_char, icon_title in icon_slots:
                if icon_title == title:
                    icon_slot.markdown(
                    f"<div style='text-align:center;font-size:2rem;padding:8px;border-radius:8px;"
                    f"border:2px solid #22c55e'>{icon_char}</div>"
                    f"<div style='text-align:center;font-size:0.55rem;font-family:Orbitron,monospace;"
                    f"letter-spacing:0.08em;color:#22c55e;margin-top:4px'>{icon_title}</div>",
                    unsafe_allow_html=True,
                )

        except Exception as e:
            err = str(e)
            with slot:
                render_card(icon, title, subtitle, "error", err[:300])
            if "Invalid Groq API key" in err:
                st.stop()

        time.sleep(15)   # Small delay — Groq is fast so 1s is enough

    st.success("🎮 All agents complete! Your Game Design Document is ready above.")
    st.balloons()

else:
    for icon, title, subtitle in AGENTS:
        render_card(icon, title, subtitle, "idle")