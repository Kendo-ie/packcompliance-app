import streamlit as st
import anthropic
import json
import re

st.set_page_config(
    page_title="PackCoPilot.app – Packaging Compliance Triage",
    page_icon="📦",
    layout="wide",
)

# ── Styling ───────────────────────────────────────────────────────────────────
st.markdown("""
<style>
  [data-testid="stAppViewContainer"] { background: #f4f7f4; }
  .hero { background: linear-gradient(135deg, #1a3a2a 0%, #2d6a4f 100%);
          color: white; padding: 1.1rem 1.75rem; border-radius: 10px;
          margin-bottom: 1.25rem; display:flex; align-items:center; gap:1rem; }
  .hero h1 { font-size: 1.4rem; font-weight: 700; margin: 0 0 0.15rem; }
  .hero p  { font-size: 0.82rem; opacity: 0.82; margin: 0; }
  .card    { background: white; border-radius: 10px; padding: 1.25rem 1.5rem;
             margin-bottom: 1rem; box-shadow: 0 1px 4px rgba(0,0,0,0.08); }
  .card h3 { margin: 0 0 0.75rem; font-size: 1rem; color: #1a3a2a; }
  .sample-card { background: white; border: 1.5px solid #e5e7eb; border-radius: 10px;
                 padding: 1rem 1.1rem 0.85rem; height: 130px;
                 box-shadow: 0 1px 3px rgba(0,0,0,0.06); display:flex;
                 flex-direction:column; justify-content:space-between; }
  .sample-card-inner { display:flex; align-items:flex-start; gap:0.75rem; }
  .sample-card h4 { margin: 0 0 0.2rem; color: #1a3a2a; font-size: 0.84rem;
                    font-weight: 600; line-height:1.3; }
  .sample-card p  { margin: 0; color: #6b7280; font-size: 0.76rem; }
  .badge-green  { background:#d1fae5; color:#065f46; padding:3px 10px;
                  border-radius:999px; font-size:0.82rem; font-weight:600; }
  .badge-amber  { background:#fef3c7; color:#92400e; padding:3px 10px;
                  border-radius:999px; font-size:0.82rem; font-weight:600; }
  .badge-red    { background:#fee2e2; color:#991b1b; padding:3px 10px;
                  border-radius:999px; font-size:0.82rem; font-weight:600; }
  .score-box    { text-align:center; padding:1.5rem; border-radius:10px; }
  .score-green  { background:#d1fae5; border: 2px solid #34d399; }
  .score-amber  { background:#fef3c7; border: 2px solid #fbbf24; }
  .score-red    { background:#fee2e2; border: 2px solid #f87171; }
  .score-num    { font-size:3rem; font-weight:800; line-height:1; }
  .score-label  { font-size:0.85rem; font-weight:600; margin-top:0.3rem; }
  .tag { display:inline-block; background:#dcfce7; color:#166534;
         border-radius:6px; padding:2px 8px; font-size:0.8rem;
         margin:2px; font-weight:500; }
  footer { visibility: hidden; }
</style>
""", unsafe_allow_html=True)

# ── Sample Concepts ───────────────────────────────────────────────────────────
SAMPLE_CONCEPTS = [
    {
        "name": "Plastic Shampoo Bottle – Retail UK",
        "category": "Rigid Plastic · Personal Care",
        "full_text": """Product: Shampoo
Packaging format: Rigid plastic bottle with flip-top cap
Material: PET (polyethylene terephthalate)
Recycled content: 0% recycled content currently
Market: UK retail (supermarket and pharmacy)
Volume: 300ml
Label: Paper wrap-around label with adhesive
Cap material: Polypropylene (PP)
Current recyclability claim: 'This bottle is recyclable'
EPR registered: No
Notes: Launching Q4 2026. Brand team wants to make recyclability claims on pack.""",
    },
    {
        "name": "Flexible Snack Pouch – EU Grocery",
        "category": "Flexible Plastic · Food",
        "full_text": """Product: Protein snack bar multipacks
Packaging format: Flexible plastic pouch (stand-up)
Material: Multi-layer laminate (PET/aluminium/PE)
Recycled content: 0%
Market: EU grocery (France, Germany, Netherlands)
Volume: 200g multipack
Label: Print directly on pouch
Closure: Resealable zip
EPR registered: France only
Notes: PPWR compliance review needed ahead of August 2026 deadline.
Sustainability team has flagged the multi-layer laminate as a potential issue.""",
    },
    {
        "name": "Glass Jar – Premium Food UK/EU",
        "category": "Glass · Food",
        "full_text": """Product: Premium pasta sauce
Packaging format: Glass jar with metal twist-off lid
Material: Soda-lime glass, 420g jar
Recycled content: 30% recycled glass (cullet)
Market: UK and EU (launching simultaneously)
Label: Paper label, water-based adhesive
Lid material: Steel with plastisol lining
EPR registered: UK (registered), EU (not yet registered)
Recyclability claim: 'Widely recycled' (UK)
Notes: Brand considers glass a sustainability positive and wants to highlight
recycled content on pack. Legal team unsure if 30% cullet qualifies under PPWR
recycled content thresholds.""",
    },
]

# ── SVG Illustrations ─────────────────────────────────────────────────────────
SVG_BOTTLE = """<svg width="38" height="72" viewBox="0 0 38 72" xmlns="http://www.w3.org/2000/svg">
  <rect x="13" y="4" width="12" height="8" rx="2" fill="#2d6a4f"/>
  <rect x="10" y="10" width="18" height="4" rx="1" fill="#1a3a2a"/>
  <rect x="6" y="14" width="26" height="50" rx="6" fill="#2d6a4f"/>
  <rect x="9" y="18" width="8" height="18" rx="2" fill="#ffffff" opacity="0.18"/>
  <rect x="8" y="42" width="22" height="12" rx="2" fill="#ffffff" opacity="0.1"/>
  <text x="19" y="51" text-anchor="middle" font-size="4.5" fill="white" font-family="Arial" font-weight="bold">SHAMPOO</text>
  <rect x="6" y="58" width="26" height="3" rx="1" fill="#52b788" opacity="0.5"/>
</svg>"""

SVG_POUCH = """<svg width="52" height="68" viewBox="0 0 52 68" xmlns="http://www.w3.org/2000/svg">
  <rect x="6" y="10" width="40" height="52" rx="4" fill="#2d6a4f"/>
  <rect x="6" y="8" width="40" height="6" rx="2" fill="#1a3a2a"/>
  <rect x="14" y="8" width="24" height="4" rx="1" fill="#52b788" opacity="0.6"/>
  <rect x="9" y="16" width="34" height="28" rx="2" fill="#ffffff" opacity="0.12"/>
  <text x="26" y="27" text-anchor="middle" font-size="5" fill="white" font-family="Arial" font-weight="bold">PROTEIN</text>
  <text x="26" y="34" text-anchor="middle" font-size="4" fill="white" font-family="Arial">SNACK BAR</text>
  <rect x="9" y="50" width="34" height="3" rx="1" fill="#52b788" opacity="0.4"/>
  <rect x="9" y="55" width="20" height="3" rx="1" fill="#52b788" opacity="0.3"/>
  <rect x="6" y="60" width="40" height="5" rx="2" fill="#1a3a2a" opacity="0.7"/>
</svg>"""

SVG_JAR = """<svg width="52" height="68" viewBox="0 0 52 68" xmlns="http://www.w3.org/2000/svg">
  <rect x="8" y="4" width="36" height="10" rx="4" fill="#374151"/>
  <rect x="6" y="14" width="40" height="46" rx="6" fill="#d1fae5" opacity="0.9"/>
  <rect x="6" y="14" width="40" height="46" rx="6" fill="none" stroke="#2d6a4f" stroke-width="2"/>
  <rect x="10" y="20" width="14" height="30" rx="2" fill="#ffffff" opacity="0.4"/>
  <rect x="12" y="24" width="28" height="20" rx="2" fill="#2d6a4f" opacity="0.15"/>
  <text x="26" y="33" text-anchor="middle" font-size="5" fill="#1a3a2a" font-family="Arial" font-weight="bold">PASTA</text>
  <text x="26" y="40" text-anchor="middle" font-size="4.5" fill="#1a3a2a" font-family="Arial">SAUCE</text>
  <rect x="10" y="48" width="32" height="3" rx="1" fill="#2d6a4f" opacity="0.3"/>
  <rect x="8" y="58" width="36" height="4" rx="2" fill="#374151" opacity="0.2"/>
</svg>"""

SAMPLE_SVGS = [SVG_BOTTLE, SVG_POUCH, SVG_JAR]

# ── Prompts ───────────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """You are PackCoPilot.app, an expert UK and EU packaging compliance AI assistant.
You assess plastic packaging against the EU Packaging and Packaging Waste Regulation (PPWR, Regulation 2025/40,
in force February 2025, applying from August 2026), UK Plastic Packaging Tax (PPT), UK EPR for packaging,
and on-pack recyclability labelling rules (OPRL in UK, Triman in France).

Focus on: recyclability requirements, recycled content thresholds, minimisation obligations,
EPR registration requirements, and substantiation of on-pack claims.

Always respond with valid JSON only — no markdown, no prose outside the JSON structure."""

ANALYSIS_PROMPT = """Analyse this packaging concept for UK/EU regulatory compliance. Return ONLY a JSON object:

{
  "product_name": "string",
  "packaging_format": "string",
  "market": "string",
  "overall_score": number (0-100, where 100 = fully compliant),
  "overall_rag": "GREEN" | "AMBER" | "RED",
  "summary": "2-3 sentence plain-English summary of the compliance picture",
  "ppwr_checks": [
    {
      "requirement": "short name of PPWR requirement",
      "detail": "what the regulation requires",
      "current_status": "what the concept currently does",
      "rag": "GREEN" | "AMBER" | "RED",
      "action_required": "what the brand team must do, or 'None'"
    }
  ],
  "claims_checks": [
    {
      "claim_text": "exact claim from the concept",
      "rag": "GREEN" | "AMBER" | "RED",
      "issue": "compliance issue or 'No issues identified'",
      "action_required": "what must be done, or 'None'"
    }
  ],
  "epr_status": {
    "uk_registered": true | false | "unknown",
    "eu_registered": true | false | "unknown",
    "rag": "GREEN" | "AMBER" | "RED",
    "note": "brief note on EPR obligations"
  },
  "evidence_checklist": [
    {
      "document": "name of document or evidence required",
      "reason": "why it is needed",
      "priority": "High" | "Medium" | "Low"
    }
  ],
  "key_risks": ["string array of top 3-4 risks in plain English"],
  "next_steps": ["string array of 4-5 prioritised actions for the packaging team"]
}

Be accurate about PPWR requirements. Flag multi-layer laminates as RED — they are not recyclable under PPWR.
Flag missing EPR registration as RED for EU markets. Flag unsubstantiated recyclability claims as AMBER.
Keep all string values concise — max 1-2 sentences. Do not pad responses.

Packaging concept to analyse:
"""


# ── Helpers ───────────────────────────────────────────────────────────────────
def badge(rag: str) -> str:
    cls = {"GREEN": "badge-green", "AMBER": "badge-amber", "RED": "badge-red"}.get(rag, "badge-amber")
    icon = {"GREEN": "✅", "AMBER": "⚠️", "RED": "🚫"}.get(rag, "⚠️")
    return f'<span class="{cls}">{icon} {rag}</span>'


def score_box(score: int, rag: str) -> str:
    cls = {"GREEN": "score-green", "AMBER": "score-amber", "RED": "score-red"}.get(rag, "score-amber")
    label = {"GREEN": "LOW RISK", "AMBER": "REVIEW REQUIRED", "RED": "HIGH RISK"}.get(rag, "REVIEW REQUIRED")
    colour = {"GREEN": "#065f46", "AMBER": "#92400e", "RED": "#991b1b"}.get(rag, "#92400e")
    return f"""
    <div class="score-box {cls}">
      <div class="score-num" style="color:{colour}">{score}</div>
      <div class="score-label" style="color:{colour}">{label}</div>
      <div style="font-size:0.75rem;color:#6b7280;margin-top:0.2rem;">Compliance Score / 100</div>
    </div>"""


def run_analysis(api_key: str, concept: str) -> dict:
    client = anthropic.Anthropic(api_key=api_key)
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=8096,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": ANALYSIS_PROMPT + concept}],
    )
    raw = message.content[0].text.strip()
    raw = re.sub(r"^```json\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    return json.loads(raw)


def render_results(result: dict):
    r_col1, r_col2, r_col3 = st.columns([2, 1, 1])

    with r_col1:
        st.markdown(f"""
        <div class="card">
          <h3>📦 {result.get('product_name', 'Product')} &nbsp;
              <span class="tag">{result.get('packaging_format', '')}</span>
              <span class="tag">{result.get('market', '')}</span></h3>
          <p style="color:#374151;margin:0">{result.get('summary', '')}</p>
        </div>
        """, unsafe_allow_html=True)

    with r_col2:
        st.markdown(score_box(result.get("overall_score", 0), result.get("overall_rag", "AMBER")),
                    unsafe_allow_html=True)

    with r_col3:
        risks = result.get("key_risks", [])
        risk_html = "".join(f"<li style='margin-bottom:0.3rem;font-size:0.85rem'>{r}</li>" for r in risks)
        st.markdown(f"""
        <div class="card" style="height:100%;box-sizing:border-box">
          <h3>⚡ Key Risks</h3>
          <ul style="padding-left:1.2rem;margin:0">{risk_html}</ul>
        </div>""", unsafe_allow_html=True)

    st.markdown("---")

    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📋 PPWR Requirements",
        "🏷️ Claims",
        "🏛️ EPR Status",
        "📄 Evidence Checklist",
        "✅ Next Steps"
    ])

    with tab1:
        checks = result.get("ppwr_checks", [])
        if checks:
            for check in checks:
                rag = check.get("rag", "AMBER")
                icon = {"GREEN": "✅", "AMBER": "⚠️", "RED": "🚫"}.get(rag, "⚠️")
                with st.expander(f"{icon} {check.get('requirement', '')}", expanded=(rag != "GREEN")):
                    c1, c2 = st.columns([1, 2])
                    with c1:
                        st.markdown(badge(rag), unsafe_allow_html=True)
                        st.markdown(f"**Regulation requires:** {check.get('detail', '')}")
                    with c2:
                        st.markdown(f"**Current status:** {check.get('current_status', '')}")
                        action = check.get("action_required", "None")
                        if action and action != "None":
                            st.info(f"**Action required:** {action}")
        else:
            st.info("No PPWR checks available.")

    with tab2:
        claims = result.get("claims_checks", [])
        if claims:
            for claim in claims:
                rag = claim.get("rag", "AMBER")
                icon = {"GREEN": "✅", "AMBER": "⚠️", "RED": "🚫"}.get(rag, "⚠️")
                with st.expander(f"{icon} \"{claim.get('claim_text', '')}\"", expanded=(rag != "GREEN")):
                    st.markdown(badge(rag), unsafe_allow_html=True)
                    st.markdown(f"**Issue:** {claim.get('issue', '')}")
                    action = claim.get("action_required", "None")
                    if action and action != "None":
                        st.info(f"**Action required:** {action}")
        else:
            st.info("No on-pack claims identified.")

    with tab3:
        epr = result.get("epr_status", {})
        epr_rag = epr.get("rag", "AMBER")
        st.markdown(badge(epr_rag), unsafe_allow_html=True)
        e1, e2 = st.columns(2)
        with e1:
            uk = epr.get("uk_registered")
            uk_label = "✅ Registered" if uk is True else ("🚫 Not registered" if uk is False else "❓ Unknown")
            st.markdown(f"**UK EPR:** {uk_label}")
        with e2:
            eu = epr.get("eu_registered")
            eu_label = "✅ Registered" if eu is True else ("🚫 Not registered" if eu is False else "❓ Unknown")
            st.markdown(f"**EU EPR:** {eu_label}")
        st.markdown(f"**Note:** {epr.get('note', '')}")

    with tab4:
        checklist = result.get("evidence_checklist", [])
        if checklist:
            high = [i for i in checklist if i.get("priority") == "High"]
            med  = [i for i in checklist if i.get("priority") == "Medium"]
            low  = [i for i in checklist if i.get("priority") == "Low"]
            for priority_group, label, colour in [
                (high, "High Priority", "#fee2e2"),
                (med,  "Medium Priority", "#fef3c7"),
                (low,  "Low Priority", "#f3f4f6"),
            ]:
                if priority_group:
                    st.markdown(f"**{label}**")
                    for item in priority_group:
                        st.markdown(f"""
                        <div style="background:{colour};border-radius:6px;
                                    padding:0.6rem 0.9rem;margin-bottom:0.4rem">
                          <strong>{item.get('document', '')}</strong><br>
                          <span style="font-size:0.83rem;color:#374151">{item.get('reason', '')}</span>
                        </div>""", unsafe_allow_html=True)
        else:
            st.info("No evidence requirements identified.")

    with tab5:
        steps = result.get("next_steps", [])
        if steps:
            for i, step in enumerate(steps, 1):
                st.markdown(f"**{i}.** {step}")
        else:
            st.info("No next steps identified.")

    st.markdown("---")
    st.caption(
        "⚠️ PackCoPilot.app is an AI-powered screening tool and does not constitute legal or regulatory advice. "
        "Always verify outputs with a qualified packaging regulatory consultant."
    )


# ── Header ────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="hero">
  <div style="font-size:1.6rem;line-height:1">📦</div>
  <div>
    <h1>PackCoPilot.app</h1>
    <p>AI-powered packaging compliance triage for CPG brands launching into UK &amp; EU markets</p>
  </div>
</div>
""", unsafe_allow_html=True)

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### ⚙️ Configuration")
    api_key = st.text_input(
        "Anthropic API Key",
        type="password",
        placeholder="sk-ant-...",
        help="Get your key at console.anthropic.com",
    )
    st.markdown("---")
    st.markdown("### ℹ️ About")
    st.markdown(
        "PackCoPilot.app screens packaging concepts against UK and EU regulations "
        "before artwork, supplier quotes, and production are committed — saving brands "
        "from costly last-minute compliance issues."
    )
    st.markdown("---")
    st.caption("Proof of Concept · PackCoPilot.app · 2025")
    st.caption("⚠️ For demonstration only. Always verify with a qualified regulatory consultant.")

# ── Explainer ─────────────────────────────────────────────────────────────────
st.markdown("""
<div style="background:white;border-left:4px solid #2d6a4f;border-radius:6px;
            padding:0.85rem 1.1rem;margin-bottom:1.25rem;
            box-shadow:0 1px 3px rgba(0,0,0,0.06)">
  <p style="margin:0 0 0.6rem;font-size:0.95rem;color:#1a3a2a;font-weight:500">
    PackCoPilot.app helps CPG brands assess packaging feasibility before committing
    to artwork, supplier quotes, or production — surfacing regulatory constraints,
    documentation requirements, and on-pack claim risks early in the launch process.
    Each concept is scored and assigned a traffic light rating:
    <span style="color:#065f46;font-weight:700">● Green</span> (proceed),
    <span style="color:#92400e;font-weight:700">● Amber</span> (rework required), or
    <span style="color:#991b1b;font-weight:700">● Red</span> (stop — compliance issue identified).
  </p>
  <ul style="margin:0.75rem 0 0;padding-left:1.1rem;font-size:0.88rem;color:#1a3a2a">
    <li style="margin-bottom:0.4rem">
      <strong>PPWR – EU Packaging and Packaging Waste Regulation (2025/40)</strong> — in force
      February 2025, applying from August 2026. Sets mandatory recyclability, recycled content,
      minimisation, and reuse requirements for all packaging sold in the EU.
    </li>
    <li style="margin-bottom:0.4rem">
      <strong>UK EPR for Packaging</strong> — Extended Producer Responsibility scheme requiring
      UK producers and importers to register, report packaging data, and pay fees based on
      packaging placed on the UK market.
    </li>
    <li>
      <strong>On-pack Claims (OPRL / Triman)</strong> — UK and EU rules governing recyclability
      and sustainability claims on packaging, requiring substantiation and approved labelling
      formats to avoid greenwashing enforcement.
    </li>
  </ul>
</div>
""", unsafe_allow_html=True)


def run_and_render(api_key: str, concept_text: str, concept_name: str):
    if not api_key:
        st.error("Please enter your Anthropic API key in the sidebar.")
        st.stop()
    with st.spinner(f"Analysing '{concept_name}' against UK/EU packaging regulations…"):
        try:
            result = run_analysis(api_key, concept_text)
        except json.JSONDecodeError as e:
            st.error(f"Could not parse the AI response. Please try again. ({e})")
            st.stop()
        except anthropic.AuthenticationError:
            st.error("Invalid API key. Please check your key in the sidebar.")
            st.stop()
        except Exception as e:
            st.error(f"Analysis failed: {e}")
            st.stop()
    st.markdown("---")
    render_results(result)


# ── Sample Concepts ───────────────────────────────────────────────────────────
st.markdown("### 💡 See How It Works")
st.markdown("Select one of our sample packaging concepts and run an instant compliance check.")
st.markdown(" ")

s_cols = st.columns(3)
for i, concept in enumerate(SAMPLE_CONCEPTS):
    with s_cols[i]:
        st.markdown(f"""
        <div class="sample-card">
          <div class="sample-card-inner">
            <div style="flex-shrink:0;display:flex;align-items:center;justify-content:center;
                        width:52px;height:68px">{SAMPLE_SVGS[i]}</div>
            <div>
              <h4>{concept['name']}</h4>
              <p>{concept['category']}</p>
            </div>
          </div>
        </div>
        """, unsafe_allow_html=True)
        if st.button("Try this concept →", key=f"sample_{i}", use_container_width=True):
            st.session_state["queued_concept"] = concept

if "queued_concept" in st.session_state:
    qc = st.session_state["queued_concept"]
    with st.expander(f"📋 {qc['name']}", expanded=True):
        st.text(qc["full_text"])
    if st.button("🔍 Analyse This Concept", type="primary", key="btn_queued"):
        run_and_render(api_key, qc["full_text"], qc["name"])
        del st.session_state["queued_concept"]

st.markdown("---")

# ── Main input ────────────────────────────────────────────────────────────────
st.markdown("### 📦 Analyse Your Own Concept")
st.markdown("Describe your packaging format, materials, markets, and any on-pack claims below.")

manual_text = st.text_area(
    "Packaging concept",
    placeholder="""Product: [product name]
Packaging format: [e.g. rigid plastic bottle, flexible pouch, glass jar]
Material: [e.g. PET, HDPE, multi-layer laminate, glass]
Recycled content: [e.g. 30% rPET, or none]
Market: [e.g. UK retail, EU grocery — France and Germany]
On-pack claims: [e.g. 'recyclable', 'made from recycled materials']
EPR registered: [Yes / No / Unsure]
Notes: [anything else relevant]""",
    height=240,
    label_visibility="collapsed",
)

if st.button("🔍 Analyse Packaging Concept", type="primary", use_container_width=True, key="btn_manual"):
    if not manual_text.strip():
        st.error("Please describe your packaging concept above.")
        st.stop()
    run_and_render(api_key, manual_text, "packaging concept")
