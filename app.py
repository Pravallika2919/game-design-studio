import os
import re
import time
from datetime import datetime

import streamlit as st
from dotenv import load_dotenv

import db
from exporters import build_docx, build_markdown, build_pdf
from groq_client import GroqAuthError, call_groq, list_chat_models

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
html,body,[data-testid="stAppViewContainer"]{background:var(--bg)!important;color:var(--text);font-family:'Rajdhani',sans-serif;}
h1,h2,h3{font-family:'Orbitron',monospace;}
[data-testid="stSidebar"]{background:var(--surface)!important;border-right:1px solid var(--border);}
.stTextArea textarea{background:var(--surface)!important;color:var(--text)!important;border:1px solid var(--border)!important;border-radius:8px;font-family:'Rajdhani',sans-serif;font-size:1rem;}
.stButton>button,.stDownloadButton>button{background:var(--accent)!important;color:white!important;border:none!important;border-radius:6px;font-family:'Orbitron',monospace;font-size:0.75rem;letter-spacing:0.1em;padding:0.6rem 1.5rem;}
.stButton>button:hover,.stDownloadButton>button:hover{opacity:0.85;}
.agent-card{background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:1rem 1.25rem;margin-bottom:0.75rem;}
.agent-card.success{border-left:3px solid var(--accent2);}
.agent-card.error{border-left:3px solid #ef4444;}
.agent-card.running{border-left:3px solid var(--accent);}
.agent-title{font-family:'Orbitron',monospace;font-size:0.7rem;letter-spacing:0.15em;color:var(--muted);margin-bottom:0.5rem;}
.agent-content{font-size:0.95rem;line-height:1.7;white-space:pre-wrap;}
.model-tag{font-size:0.6rem;color:#475569;margin-bottom:4px;}
.status-badge{display:inline-block;font-size:0.65rem;font-family:'Orbitron',monospace;padding:2px 8px;border-radius:4px;letter-spacing:0.1em;margin-bottom:0.5rem;}
.badge-ok{background:#064e3b;color:#6ee7b7;}
.badge-err{background:#450a0a;color:#fca5a5;}
.badge-run{background:#2e1065;color:#c4b5fd;}
.export-box{background:var(--surface);border:1px solid var(--accent);border-radius:10px;padding:1rem 1.25rem;margin:1rem 0;}
[data-testid="stVerticalBlockBorderWrapper"]{background:var(--surface);border-color:var(--border)!important;border-radius:10px;}
[data-testid="stVerticalBlockBorderWrapper"] h1{font-size:1.25rem!important;margin:.6rem 0 .3rem!important;}
[data-testid="stVerticalBlockBorderWrapper"] h2{font-size:1.1rem!important;margin:.6rem 0 .3rem!important;}
[data-testid="stVerticalBlockBorderWrapper"] h3,[data-testid="stVerticalBlockBorderWrapper"] h4{font-size:1rem!important;margin:.5rem 0 .2rem!important;}
[data-testid="stVerticalBlockBorderWrapper"] p{margin-bottom:.4rem;}
[data-testid="stSidebar"] .stButton>button{background:#1a1a2a!important;border:1px solid var(--border)!important;font-family:'Rajdhani',sans-serif;letter-spacing:0;text-transform:none;font-size:.92rem;padding:.35rem .6rem;text-align:left;justify-content:flex-start;}
[data-testid="stSidebar"] .stButton>button:hover{border-color:var(--accent)!important;}
[data-baseweb="select"]>div{background:var(--surface)!important;border-color:var(--border)!important;color:var(--text)!important;}
[data-testid="stExpander"]{background:var(--surface);border:1px solid var(--border)!important;border-radius:10px;}
hr{border-color:var(--border);}
#MainMenu,footer{visibility:hidden;}
header[data-testid="stHeader"]{background:transparent;}
[data-testid="stSidebarCollapsedControl"] button,[data-testid="stExpandSidebarButton"],[data-testid="stSidebarCollapseButton"] button{color:#e2e8f0!important;}
[data-testid="stSidebarCollapsedControl"],[data-testid="stExpandSidebarButton"]{background:#12121a;border:1px solid #7c3aed;border-radius:8px;}
</style>
""", unsafe_allow_html=True)

# ── Config ─────────────────────────────────────────────────────────────────────
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
        "- A sharp elevator pitch (2-3 sentences)\n- Genre & sub-genre\n"
        "- Core themes\n- Target audience\n- 3 unique selling points\n"
        "Be concise, creative, and inspiring."
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

# ── Customization dropdowns ───────────────────────────────────────────────────
AUTO = "Let AI decide"
OPTION_FIELDS = {          # key: (label, choices)
    "genre": ("Genre", [AUTO, "Action", "Adventure", "RPG", "Strategy", "Puzzle", "Platformer",
                        "Shooter", "Survival / Horror", "Simulation", "Card & Board", "Racing", "Sports"]),
    "platform": ("Platform", [AUTO, "Mobile", "PC", "Console", "Web browser", "VR"]),
    "audience": ("Audience", [AUTO, "Kids (under 12)", "Teens", "Adults", "All ages", "Casual players", "Hardcore players"]),
    "art_style": ("Art style", [AUTO, "Pixel art", "Low-poly 3D", "Cel-shaded", "Realistic", "Hand-drawn", "Minimalist"]),
    "tone": ("Tone", [AUTO, "Dark & gritty", "Cheerful & colourful", "Epic & heroic", "Funny", "Mysterious", "Relaxing"]),
    "team": ("Team size", [AUTO, "Solo developer", "Small team (2-5)", "Medium team (6-15)", "Large team (16+)"]),
}


def chosen_options() -> dict:
    """Only the dropdowns the user actually changed: {key: value}."""
    out = {}
    for k in OPTION_FIELDS:
        v = st.session_state.get(f"opt_{k}", AUTO)
        if v != AUTO:
            out[k] = v
    return out


def labeled(options: dict) -> dict:
    return {OPTION_FIELDS[k][0]: v for k, v in (options or {}).items() if k in OPTION_FIELDS}


def build_brief(idea: str, options: dict) -> str:
    text = f"Game Idea: {idea}\n"
    if options:
        text += "\nDesign constraints (every agent must follow these):\n"
        text += "\n".join(f"- {OPTION_FIELDS[k][0]}: {v}" for k, v in options.items()) + "\n"
    return text + "\n"


# ── Token budget (free tier has a per-minute token cap) ───────────────────────
LENGTH_RULE = {"GDD COMPILER": "Keep the whole document under 600 words."}
DEFAULT_RULE = "Keep your answer under 250 words. Use short bullet points; avoid tables."
MAX_TOKENS = {"GDD COMPILER": 1800}
CONTEXT_CHARS = 1800        # each earlier agent is trimmed to this when passed on


def trim(text: str, n: int = CONTEXT_CHARS) -> str:
    return text if len(text) <= n else text[:n].rsplit(" ", 1)[0] + " …"


db.init_db()


# ── Session state (keeps results alive after a download click) ────────────────
if "results" not in st.session_state:
    st.session_state.results = {}      # {agent: {"output": str, "model": str}}
    st.session_state.idea = ""
    st.session_state.models = []
    st.session_state.current_id = None
    st.session_state.options = {}


# ── Backend ────────────────────────────────────────────────────────────────────
def validate_key():
    key = os.getenv("GROQ_API_KEY", "").strip()
    if not key:
        return False, "GROQ_API_KEY not set in .env"
    if not key.startswith("gsk_"):
        return False, "Key should start with 'gsk_' — check your .env"
    return True, key


# ── UI helpers ─────────────────────────────────────────────────────────────────
def render_card(icon, title, subtitle, state, content="", model_used=""):
    badge = {
        "idle": "",
        "running": '<span class="status-badge badge-run">● RUNNING</span>',
        "done": '<span class="status-badge badge-ok">✔ COMPLETE</span>',
        "error": '<span class="status-badge badge-err">✖ ERROR</span>',
    }[state]
    meta = f'<div class="model-tag">model: {model_used}</div>' if model_used else ""
    with st.container(border=True):
        st.markdown(
            f'<div class="agent-title">{icon} {title} · {subtitle}</div>{badge}{meta}',
            unsafe_allow_html=True,
        )
        if content:
            st.markdown(content.replace("$", "\\$"))   # render markdown natively; $ is not LaTeX


def show_downloads():
    """Download section — appears once at least one agent has produced output."""
    results, idea = st.session_state.results, st.session_state.idea
    brief = labeled(st.session_state.options)
    if not results:
        return

    st.markdown("---")
    st.markdown("### 📥 Download your Game Design Document")
    slug = re.sub(r"[^a-z0-9]+", "_", idea.lower()).strip("_")[:30] or "game"

    c1, c2, c3 = st.columns(3)
    with c1:
        st.download_button("📄 PDF", data=build_pdf(idea, results, brief),
                           file_name=f"GDD_{slug}.pdf", mime="application/pdf",
                           use_container_width=True)
    with c2:
        st.download_button(
            "📝 WORD", data=build_docx(idea, results, brief), file_name=f"GDD_{slug}.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            use_container_width=True)
    with c3:
        st.download_button("🗒️ MARKDOWN", data=build_markdown(idea, results, brief),
                           file_name=f"GDD_{slug}.md", mime="text/markdown",
                           use_container_width=True)


# ── History (database) ────────────────────────────────────────────────────────
def _load_entry(gdd_id):
    row = db.load_gdd(gdd_id)
    if row:
        st.session_state.results = row["results"]
        st.session_state.idea = row["idea"]
        st.session_state.game_idea = row["idea"]       # fills the text box
        st.session_state.current_id = gdd_id
        st.session_state.options = row["options"]
        for k, (_, choices) in OPTION_FIELDS.items():  # restore the dropdowns
            v = row["options"].get(k, AUTO)
            st.session_state[f"opt_{k}"] = v if v in choices else AUTO


def _delete_entry(gdd_id):
    db.delete_gdd(gdd_id)
    if st.session_state.current_id == gdd_id:
        st.session_state.results, st.session_state.current_id = {}, None


def _new_entry():
    st.session_state.results, st.session_state.idea = {}, ""
    st.session_state.game_idea, st.session_state.current_id = "", None
    st.session_state.options = {}
    for k in OPTION_FIELDS:
        st.session_state[f"opt_{k}"] = AUTO


def render_history():
    entries = db.list_gdds()
    st.markdown(f"### 📚 History ({len(entries)})")
    st.button("➕ New GDD", key="new_gdd", on_click=_new_entry, use_container_width=True)
    if not entries:
        st.caption("Nothing saved yet. Every GDD you generate is saved here automatically.")
        return
    for e in entries:
        when = datetime.fromisoformat(e["created_at"]).strftime("%d %b, %I:%M %p")
        label = ("▶ " if e["id"] == st.session_state.current_id else "") + e["idea"][:26]
        c1, c2 = st.columns([5, 1])
        with c1:
            st.button(label, key=f"load_{e['id']}", on_click=_load_entry, args=(e["id"],),
                      help=f"{e['idea']}\n{when} · {e['agents_done']}/6 agents",
                      use_container_width=True)
        with c2:
            st.button("🗑", key=f"del_{e['id']}", on_click=_delete_entry, args=(e["id"],),
                      help="Delete this GDD")
        st.caption(f"{when} · {e['agents_done']}/6 agents")


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
**Get a FREE Groq key:**
1. [console.groq.com](https://console.groq.com)
2. API Keys → Create API Key
3. Add to `.env`:
```
GROQ_API_KEY=gsk_your_key_here
```
        """)
    st.markdown("---")
    st.markdown("**Models**")
    st.caption("Detected live from Groq on every run, so retired models never break the app.")
    if st.session_state.get("models"):
        for m in st.session_state.models[:5]:
            st.markdown(f"• `{m}`")
    st.markdown("---")
    history_box = st.container()

# ── Main ───────────────────────────────────────────────────────────────────────
st.markdown("## Describe your game idea")
game_idea = st.text_area(
    label="Game idea", label_visibility="collapsed", height=120, key="game_idea",
    placeholder="e.g. space adventure, zombie survival RPG, cozy farming sim...",
)

with st.expander("🎛️ Customize your game (optional)", expanded=True):
    st.caption("Leave as 'Let AI decide' for a surprise, or pick options to steer all 6 agents.")
    keys = list(OPTION_FIELDS)
    for row in (keys[:3], keys[3:]):
        for col, k in zip(st.columns(3), row):
            label, choices = OPTION_FIELDS[k]
            col.selectbox(label, choices, key=f"opt_{k}")

c1, _ = st.columns([1, 4])
with c1:
    run = st.button("▶ RUN AGENTS", use_container_width=True)

st.markdown("---")

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

# ── Pipeline ───────────────────────────────────────────────────────────────────
if run:
    if not game_idea.strip():
        st.warning("Please describe your game idea first.")
        st.stop()

    ok, key = validate_key()
    if not ok:
        st.error(f"❌ {key}")
        st.stop()

    st.session_state.results = {}
    st.session_state.idea = game_idea.strip()

    try:
        models = list_chat_models(key)
        st.session_state.models = models
    except GroqAuthError as e:
        st.error(f"🔑 {e}")
        st.stop()
    except Exception as e:
        st.error(f"🌐 {e}")
        st.stop()
    st.info(f"⚡ Using `{models[0]}` (+{len(models) - 1} backups)")

    progress = st.progress(0, text="Starting agents...")
    st.session_state.options = chosen_options()
    accumulated = build_brief(game_idea.strip(), st.session_state.options)

    for i, (icon, title, subtitle) in enumerate(AGENTS):
        progress.progress(i / len(AGENTS), text=f"Agent {i + 1} of {len(AGENTS)}: {title.title()}...")
        slot = st.empty()
        with slot:
            render_card(icon, title, subtitle, "running")

        prompt = (
            accumulated + f"\nYour role: {title}\n"
            f"Based on the game idea and all previous agent outputs above, "
            f"provide your expert {title.lower()} contribution now."
        )
        try:
            def wait_msg(msg, _i=icon, _t=title, _s=subtitle):
                with slot:
                    render_card(_i, _t, _s, "running", msg)

            system = AGENT_PROMPTS[title] + "\n\n" + LENGTH_RULE.get(title, DEFAULT_RULE)
            output, model_used = call_groq(key, system, prompt, models,
                                           max_tokens=MAX_TOKENS.get(title, 1200),
                                           status_cb=wait_msg)
            accumulated += f"\n\n=== {title} ===\n{trim(output)}"
            st.session_state.results[title] = {"output": output, "model": model_used}
            with slot:
                render_card(icon, title, subtitle, "done", output, model_used)
        except Exception as e:
            with slot:
                render_card(icon, title, subtitle, "error", str(e)[:600])
            if isinstance(e, GroqAuthError):
                st.stop()
        time.sleep(1)

    done = len(st.session_state.results)
    if done:
        st.session_state.current_id = db.save_gdd(st.session_state.idea, st.session_state.results, st.session_state.options)
    if done == len(AGENTS):
        progress.progress(1.0, text="✅ All agents complete!")
        st.success("🎮 Your Game Design Document is ready — download it below!")
        st.balloons()
    else:
        progress.progress(done / len(AGENTS), text=f"⚠️ {done} of {len(AGENTS)} agents finished")
        st.error(f"Only {done} of {len(AGENTS)} agents succeeded. See the error on the red card(s) above.")

elif st.session_state.results:
    # Page re-ran (e.g. after a download click) — redraw saved results
    for icon, title, subtitle in AGENTS:
        if title in st.session_state.results:
            r = st.session_state.results[title]
            render_card(icon, title, subtitle, "done", r["output"], r["model"])
        else:
            render_card(icon, title, subtitle, "idle")
else:
    for icon, title, subtitle in AGENTS:
        render_card(icon, title, subtitle, "idle")

show_downloads()

with history_box:
    render_history()