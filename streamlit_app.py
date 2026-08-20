from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path
from urllib.parse import urlparse

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import httpx
import numpy as np
import pandas as pd
import streamlit as st

from app.config import settings
from app.db.repository import Repository
from app.models.schemas import AnalyzeRequest
from app.services.crawl_service import crawl_article
from app.services.gemini_service import GeminiService
from app.services.opportunity_service import OpportunityService
from app.services.sitemap_service import chunked, get_sitemap_urls


def normalize_domain(url_or_domain: str) -> str:
    """Extracts clean lowercase domain from URL/domain without 'www.', port, or protocol."""
    if not url_or_domain:
        return ""
    raw = str(url_or_domain).strip().lower()
    if not raw.startswith(("http://", "https://", "//")):
        raw = "https://" + raw
    try:
        parsed = urlparse(raw)
        netloc = parsed.netloc or parsed.path
        if "/" in netloc:
            netloc = netloc.split("/")[0]
        if ":" in netloc:
            host, port = netloc.split(":", 1)
            netloc = host if port in ("80", "443", "") else f"{host}:{port}"
        if netloc.startswith("www."):
            netloc = netloc[4:]
        return netloc.rstrip(".")
    except Exception:
        return ""


def classify_link_type(source_url: str, target_url: str) -> str:
    """Classifies link as INTERNAL (same domain) or EXTERNAL."""
    s = normalize_domain(source_url)
    t = normalize_domain(target_url)
    return "INTERNAL" if (s and t and s == t) else "EXTERNAL"


# Page setup
st.set_page_config(
    page_title="Internal Linking Opportunity Finder",
    page_icon="🔗",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for rich aesthetics and clean typography
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }
    
    .metric-card {
        background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
        border: 1px solid #334155;
        border-radius: 12px;
        padding: 16px 20px;
        color: #f8fafc;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
    }
    
    .metric-label {
        font-size: 0.85rem;
        color: #94a3b8;
        font-weight: 500;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    
    .metric-value {
        font-size: 1.8rem;
        font-weight: 700;
        color: #38bdf8;
        margin-top: 4px;
    }
    
    .score-breakdown-box {
        background: #0f172a;
        border: 1px solid #334155;
        border-radius: 8px;
        padding: 10px 14px;
        font-size: 0.85rem;
        margin-bottom: 12px;
        display: flex;
        flex-wrap: wrap;
        gap: 12px;
    }
    
    .score-item {
        color: #cbd5e1;
    }
    
    .score-item strong {
        color: #38bdf8;
    }
    
    .badge-exact {
        background: #059669;
        color: white;
        padding: 4px 10px;
        border-radius: 6px;
        font-size: 0.8rem;
        font-weight: 600;
    }
    
    .badge-semantic {
        background: #0284c7;
        color: white;
        padding: 4px 10px;
        border-radius: 6px;
        font-size: 0.8rem;
        font-weight: 600;
    }
    
    .badge-edit {
        background: #d97706;
        color: white;
        padding: 4px 10px;
        border-radius: 6px;
        font-size: 0.8rem;
        font-weight: 600;
    }
</style>
""", unsafe_allow_html=True)

# Initialize database and services
def get_services():
    repo = Repository(settings.database_path)
    schema_path = PROJECT_ROOT / "app" / "db" / "schema.sql"
    repo.init_schema(schema_path.read_text(encoding="utf-8"))
    api_key = os.environ.get("GEMINI_API_KEY", settings.gemini_api_key)
    gemini = GeminiService(api_key=api_key, model=settings.gemini_model)
    service = OpportunityService(repo=repo, gemini=gemini)
    return repo, gemini, service

repo, gemini, opportunity_service = get_services()

st.title("🔗 AI-Powered Internal Linking Opportunity Finder")
st.markdown("**Deterministic Link Exclusion + Google Gemini Semantic Placement** | *Code handles facts. AI handles meaning.*")

# Fetch domain summaries from database
domain_summaries = repo.fetch_domains_summary()
total_indexed_count = sum(d["count"] for d in domain_summaries)
domain_map = {d["domain"]: d for d in domain_summaries}
distinct_domains = list(domain_map.keys())
prod_domains = [d for d in distinct_domains if not domain_map[d]["is_demo"]]
demo_domains = [d for d in distinct_domains if domain_map[d]["is_demo"]]

# Target URL session state initialization
if "target_url_input" not in st.session_state:
    if prod_domains:
        first_prod = prod_domains[0]
        st.session_state["target_url_input"] = f"https://www.{first_prod}/topics/shoes-and-boots/best-running-shoes" if "outdoorgear" in first_prod else f"https://www.{first_prod}/best-running-shoes"
    elif demo_domains:
        st.session_state["target_url_input"] = "https://example.com/best-running-shoes"
    else:
        st.session_state["target_url_input"] = "https://www.outdoorgearlab.com/topics/shoes-and-boots/best-running-shoes"

with st.sidebar:
    st.header("⚙️ 1. Google AI Studio Key")
    
    user_gemini_key = st.text_input(
        "Gemini API Key (Optional)",
        value=gemini.api_key or "",
        type="password",
        help="Paste your free API key from Google AI Studio (aistudio.google.com). If empty, runs in offline semantic mode."
    )
    if user_gemini_key != gemini.api_key:
        gemini.set_api_key(user_gemini_key)
        
    if gemini.is_api_configured():
        st.success("🟢 **Gemini AI Active** (Gemini 2.5 Flash)")
    else:
        st.info("🟡 **Offline Conservative NLP Mode** (Add API key for full AI generation)")
        
    st.divider()
    st.subheader("🌐 2. Active Website Partition")
    
    if distinct_domains:
        # Auto-infer active domain from target URL if present in indexed domains
        current_target_url = st.session_state.get("target_url_input", "")
        inferred_dom = normalize_domain(current_target_url)
        
        default_domain_idx = 0
        if inferred_dom in distinct_domains:
            default_domain_idx = distinct_domains.index(inferred_dom)
        elif prod_domains and prod_domains[0] in distinct_domains:
            default_domain_idx = distinct_domains.index(prod_domains[0])
            
        active_domain = st.selectbox(
            "Select Website Scope:",
            options=distinct_domains,
            index=default_domain_idx,
            format_func=lambda d: f"{d} — {domain_map[d]['count']} articles ({'Demo' if domain_map[d]['is_demo'] else 'Production'})",
            help="Ensures internal links strictly come from this website partition."
        )
        active_articles_count = domain_map[active_domain]["count"]
        is_active_demo = domain_map[active_domain]["is_demo"]
        st.caption(f"📊 Active Scope: **{active_domain}** ({active_articles_count} articles, {'Demo' if is_active_demo else 'Production'})")
    else:
        active_domain = ""
        active_articles_count = 0
        is_active_demo = False
        st.warning("⚠️ No website partitions indexed yet.")
        st.caption("Click **'🌱 Load Demo & Sample Data'** below or index a sitemap in the **'📥 Index Your Blog Sitemap'** tab.")

    st.divider()
    st.subheader("🎯 3. Target Page")
    
    destination_url = st.text_input(
        "Target Page URL",
        value=st.session_state.get("target_url_input", ""),
        help="The URL of the destination page you want to build internal links to."
    )
    st.session_state["target_url_input"] = destination_url
    
    target_domain = normalize_domain(destination_url)
    link_type = classify_link_type(active_domain or "", target_domain)
    
    # Real-time Domain & Link Type Validation Badge
    if active_domain and target_domain:
        if link_type == "INTERNAL":
            st.success(f"🟢 **Internal Link**: `{target_domain}` matches active partition `{active_domain}`")
        else:
            st.error(f"🔴 **External Target**: Target `{target_domain}` does not match active partition `{active_domain}`")
    elif not active_domain:
        st.info("ℹ️ Index a website or load sample data to establish an active partition.")
            
    anchor_text = st.text_input(
        "Target Anchor Text",
        value="best running shoes",
        help="The desired anchor text phrase to weave into relevant blog posts."
    )
    
    max_results = st.slider("Max Opportunities to Return", min_value=5, max_value=50, value=20, step=5)
    allow_external = st.checkbox("Allow External / Cross-Domain Links", value=False, help="When checked, generates external outbound linking opportunities instead of internal links.")

    st.divider()
    st.subheader("💾 Database Management")
    st.write(f"**Total Indexed Articles:** `{total_indexed_count}`")
    if active_domain:
        st.write(f"**Active Partition Articles:** `{active_articles_count}` (`{active_domain}`)")
    
    col_db1, col_db2 = st.columns(2)
    with col_db1:
        if st.button("🌱 Load Demo & Sample Data", use_container_width=True):
            from scripts.seed_demo_data import seed
            seed()
            st.success("Loaded demo & production sample data!")
            st.rerun()
    with col_db2:
        if st.button("🗑️ Clear All DB", use_container_width=True):
            repo.clear_all_articles()
            st.warning("Database wiped!")
            st.rerun()

    if "example.com" in distinct_domains and len(distinct_domains) > 1:
        if st.button("🧹 Remove Demo Data (example.com)", use_container_width=True):
            repo.delete_domain("example.com")
            st.success("Removed demo data!")
            st.rerun()

tab_analyze, tab_audit, tab_index, tab_about = st.tabs([
    "🚀 Find Linking Opportunities",
    "🚫 Excluded Articles & Audit Log",
    "📥 Index Your Blog Sitemap",
    "ℹ️ How It Works"
])

with tab_index:
    st.subheader("📥 Index Your Website's Blog Articles / Sitemap")
    st.markdown("""
    Crawl and index your live blog articles with automatic retry backoff, canonical URL resolution, and failure diagnostics.
    """)
    
    idx_mode = st.radio("Choose Indexing Mode:", ["🌐 Live Sitemap XML / Auto-Discovery", "📋 Direct List of Article URLs"], horizontal=True)
    
    if idx_mode == "🌐 Live Sitemap XML / Auto-Discovery":
        real_sitemap_input = st.text_input(
            "Sitemap XML, Domain, or Any Article URL",
            placeholder="https://www.outdoorgearlab.com/sitemap.xml",
            help="Enter an XML Sitemap URL (e.g. sitemap.xml) OR any article URL/domain to auto-discover the sitemap from robots.txt!"
        )
    else:
        direct_urls_text = st.text_area(
            "Paste Blog Article URLs (one per line):",
            placeholder="https://www.outdoorgearlab.com/topics/shoes-and-boots/best-running-shoes\nhttps://www.outdoorgearlab.com/topics/shoes-and-boots/best-trail-running-shoes",
            help="Enter one full URL per line to index specific articles directly."
        )

    max_crawl_limit = st.slider("Max Articles to Crawl & Index", min_value=5, max_value=250, value=25, step=5)
    
    col_idx1, col_idx2 = st.columns([2, 1])
    with col_idx1:
        if st.button("🚀 Start Indexing", type="primary", use_container_width=True):
            urls_to_crawl = []
            
            if idx_mode == "📋 Direct List of Article URLs":
                raw_lines = [line.strip() for line in direct_urls_text.splitlines() if line.strip()]
                urls_to_crawl = [u for u in raw_lines if u.startswith("http")]
                if not urls_to_crawl:
                    st.error("Please paste at least one valid HTTP/HTTPS article URL.")
            else:
                if not real_sitemap_input or not real_sitemap_input.strip():
                    st.error("Please enter a sitemap URL, domain, or article URL.")
            
            if (idx_mode == "📋 Direct List of Article URLs" and urls_to_crawl) or (idx_mode != "📋 Direct List of Article URLs" and real_sitemap_input):
                progress_bar = st.progress(0.0)
                status_text = st.empty()
                
                async def run_indexing():
                    discovered = 0
                    attempted = 0
                    saved = 0
                    failed = 0
                    diagnostics = []
                    
                    headers = {"User-Agent": settings.user_agent}
                    async with httpx.AsyncClient(headers=headers, timeout=settings.request_timeout_seconds, follow_redirects=True) as client:
                        if idx_mode == "🌐 Live Sitemap XML / Auto-Discovery":
                            status_text.write("Fetching and parsing sitemap XML (or auto-discovering from robots.txt)...")
                            try:
                                urls = await get_sitemap_urls(real_sitemap_input.strip(), client, max_urls=max_crawl_limit)
                            except Exception as e:
                                st.error(f"Failed to fetch sitemap: {e}")
                                return None
                        else:
                            urls = urls_to_crawl[:max_crawl_limit]
                            
                        discovered = len(urls)
                        if discovered == 0:
                            st.warning("No valid HTML article URLs found to crawl.")
                            return None
                            
                        status_text.write(f"Discovered {discovered} articles. Crawling clean content and outbound links...")
                        
                        batch_size = 4
                        for i, batch in enumerate(chunked(urls, batch_size)):
                            tasks = [crawl_article(u, client) for u in batch]
                            results = await asyncio.gather(*tasks)
                            for payload in results:
                                attempted += 1
                                if payload["crawl_status"] != "SAVED":
                                    failed += 1
                                    diagnostics.append({
                                        "url": payload["url_raw"],
                                        "status": payload.get("crawl_status", "FAILED"),
                                        "http_status": payload.get("http_status", 0),
                                        "reason": payload.get("crawl_error") or "Failed to fetch content after 3 attempts.",
                                        "action": "Check if server blocks bots (403) or rate limits requests (429)."
                                    })
                                    continue
                                
                                # Tag as production (is_demo = 0)
                                payload["is_demo"] = 0
                                art_id = repo.upsert_article(payload)
                                if gemini.is_api_configured():
                                    emb = await gemini.get_embedding(f"{payload.get('title', '')}: {payload.get('content_text', '')[:2000]}")
                                    if emb:
                                        repo.save_embedding(art_id, emb)
                                saved += 1
                            progress_bar.progress(min(1.0, attempted / discovered))
                            status_text.write(f"Crawled {attempted}/{discovered} articles ({saved} saved in SQLite)...")
                            
                    return {
                        "discovered_urls": discovered,
                        "attempted_urls": attempted,
                        "successful_fetches": saved,
                        "saved_articles": saved,
                        "failed_urls": failed,
                        "diagnostics": diagnostics[:50]
                    }

                res = asyncio.run(run_indexing())
                if res:
                    st.session_state["index_result"] = res
                    st.success(f"✅ Indexing complete: {res['saved_articles']} articles saved to database!")
                    st.rerun()

    if "index_result" in st.session_state:
        ir = st.session_state["index_result"]
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Discovered", ir["discovered_urls"])
        c2.metric("Attempted", ir["attempted_urls"])
        c3.metric("Fetched & Saved", ir["saved_articles"])
        c4.metric("Failed / Skipped", ir["failed_urls"])
        c5.metric("Success Rate", f"{(ir['saved_articles'] / max(1, ir['attempted_urls'])) * 100:.0f}%")
        
        if ir.get("diagnostics"):
            with st.expander(f"⚠️ View Failure Diagnostics ({len(ir['diagnostics'])} skipped URLs)"):
                for diag in ir["diagnostics"]:
                    st.markdown(f"**URL:** `{diag['url']}`")
                    st.caption(f"Status: `{diag['status']}` (HTTP {diag['http_status']}) | Attempts: `3/3`")
                    st.warning(f"**Reason:** {diag['reason']}")
                    st.info(f"**Action:** {diag['action']}")
                    st.markdown("---")

with tab_analyze:
    st.subheader("Discover Contextual Internal Linking Opportunities")
    
    if not active_domain or total_indexed_count == 0:
        st.warning("⚠️ **Database is empty**: Please go to the **'📥 Index Your Blog Sitemap'** tab above to crawl your website (or click **'🌱 Load Demo & Sample Data'** in the sidebar).")
    else:
        is_demo_tag = " (Demo)" if is_active_demo else " (Production)"
        st.info(f"🌐 **Active Scope:** Scoped strictly to domain `{active_domain}`{is_demo_tag} ({active_articles_count} posts indexed)")
    
    # Target URL Pre-Validation Warning
    if not allow_external and link_type == "EXTERNAL" and active_domain:
        st.warning(f"⚠️ **Target Validation Warning**: Target URL (`{target_domain}`) does not belong to active partition `{active_domain}`. In strict internal mode, zero cross-domain opportunities will be generated. Either select `{target_domain}` as the active partition or check 'Allow External / Cross-Domain Links'.")

    if st.button("✨ Analyze & Rank Opportunities", type="primary", use_container_width=True):
        if not destination_url or not anchor_text:
            st.error("Please provide both the Target Page URL and Target Anchor Text in the sidebar.")
        elif total_indexed_count == 0 or not active_domain:
            st.error("No indexed articles in active partition. Please index your sitemap or load sample data first.")
        else:
            with st.spinner("Running 4-stage retrieval: Domain filtering ➔ Vector search ➔ Deterministic link exclusion ➔ Gemini AI placement..."):
                try:
                    req = AnalyzeRequest(
                        destination_url=destination_url.strip(),
                        anchor_text=anchor_text.strip(),
                        max_results=max_results,
                        active_domain_override=active_domain,
                        allow_external_links=allow_external,
                        is_demo=is_active_demo,
                    )
                    result_obj = asyncio.run(opportunity_service.analyze(
                        req,
                        active_domain_override=active_domain,
                        allow_external_links=allow_external,
                        is_demo_mode=is_active_demo,
                    ))
                    st.session_state["analysis_result"] = result_obj.model_dump(mode="json")
                    st.success("✅ Analysis complete!")
                except Exception as e:
                    st.error(f"Analysis failed: {str(e)}")

    if "analysis_result" in st.session_state:
        data = st.session_state["analysis_result"]
        t_val = data.get("target_validation", {})
        
        # Display Target Validation Status
        if not t_val.get("is_eligible_for_internal", True) and not allow_external:
            st.error(f"🔴 **Target Validation Error**: {t_val.get('validation_message')}")
        
        st.markdown("---")
        # Metric Overview Cards
        m1, m2, m3, m4 = st.columns(4)
        with m1:
            st.markdown(f'<div class="metric-card"><div class="metric-label">Indexed Posts (Partition)</div><div class="metric-value">{data["discovered_urls"]}</div></div>', unsafe_allow_html=True)
        with m2:
            st.markdown(f'<div class="metric-card"><div class="metric-label">Already Linked (Excluded)</div><div class="metric-value">{data["excluded_already_linking"]}</div></div>', unsafe_allow_html=True)
        with m3:
            st.markdown(f'<div class="metric-card"><div class="metric-label">Weak / Irrelevant (Excluded)</div><div class="metric-value">{data["excluded_irrelevant"]}</div></div>', unsafe_allow_html=True)
        with m4:
            st.markdown(f'<div class="metric-card"><div class="metric-label">Recommended Opportunities</div><div class="metric-value">{data["total_opportunities"]}</div></div>', unsafe_allow_html=True)
            
        st.markdown("<br>", unsafe_allow_html=True)
        
        opportunities = data.get("opportunities", [])
        if not opportunities:
            st.info("ℹ️ **Zero Opportunities**: No eligible internal linking opportunities were generated for this target/partition pair. (See the **'🚫 Excluded Articles & Audit Log'** tab to inspect the exact audit log reason).")
        else:
            st.subheader(f"🎯 Top {len(opportunities)} Recommended Linking Opportunities")
            
            # Export bar
            col_exp1, col_exp2 = st.columns([1, 1])
            with col_exp1:
                st.download_button(
                    label="📥 Export Full Results as JSON",
                    data=json.dumps(data, default=str, indent=2),
                    file_name="internal_linking_opportunities.json",
                    mime="application/json",
                    use_container_width=True
                )
            with col_exp2:
                table_rows = []
                for opp in opportunities:
                    source = opp.get("source_article") or {}
                    target = opp.get("target_page") or {}
                    scores = opp.get("scores") or {}
                    placement = opp.get("placement") or {}
                    loc = placement.get("recommended_location") or {}
                    table_rows.append({
                        "Source Title": source.get("title", "Untitled"),
                        "Source URL": source.get("url", ""),
                        "Target URL": target.get("url", ""),
                        "Target Anchor": target.get("target_anchor", ""),
                        "Link Type": opp.get("link_type", "INTERNAL"),
                        "Overall Score": scores.get("overall_score", 0.0),
                        "Semantic Relevance": scores.get("semantic_relevance", 0.0),
                        "Anchor Match Quality": scores.get("anchor_match_quality", 0.0),
                        "Context Quality": scores.get("context_quality", 0.0),
                        "Linkability": scores.get("linkability_score", 0.0),
                        "Content Quality": scores.get("content_quality", 0.0),
                        "Opportunity Value": scores.get("opportunity_value", 0.0),
                        "Anchor Status": opp.get("anchor_status", "EXACT_UNLINKED_ANCHOR"),
                        "Paragraph Index": loc.get("paragraph_index", 0),
                        "Sentence Index": loc.get("sentence_index", 0),
                        "Reason": opp.get("reason", ""),
                        "Ready-to-Paste Markdown": placement.get("ready_to_paste_markdown", ""),
                        "Ready-to-Paste HTML": placement.get("ready_to_paste_html", ""),
                    })
                df = pd.DataFrame(table_rows)
                st.download_button(
                    label="📊 Export Summary as CSV",
                    data=df.to_csv(index=False).encode("utf-8"),
                    file_name="internal_linking_opportunities.csv",
                    mime="text/csv",
                    use_container_width=True
                )

            st.markdown("<br>", unsafe_allow_html=True)

            for idx, opp in enumerate(opportunities, start=1):
                source = opp.get("source_article") or {}
                target = opp.get("target_page") or {}
                scores = opp.get("scores") or {}
                placement = opp.get("placement") or {}
                loc = placement.get("recommended_location") or {}
                
                status = opp.get("anchor_status", "EXACT_UNLINKED_ANCHOR")
                if status == "EXACT_UNLINKED_ANCHOR":
                    badge_type = '<span class="badge-exact">🟢 Exact Unlinked Anchor Found</span>'
                elif status == "SEMANTIC_ANCHOR_CANDIDATE":
                    badge_type = '<span class="badge-semantic">🔵 Semantic Anchor Candidate</span>'
                else:
                    badge_type = '<span class="badge-edit">🟡 Contextual Clause Insertion</span>'

                ov_score = float(scores.get("overall_score", 0.0))
                sem_score = float(scores.get("semantic_relevance", 0.0))
                anchor_score = float(scores.get("anchor_match_quality", 0.0))
                ctx_score = float(scores.get("context_quality", 0.0))
                link_score = float(scores.get("linkability_score", 0.0))
                content_score = float(scores.get("content_quality", 0.0))

                with st.expander(f"**#{idx} — {source.get('title', 'Article')}** (Opportunity Score: `{ov_score:.1f}/100`)", expanded=(idx <= 3)):
                    
                    # Target / Source Header Card
                    col_s1, col_s2 = st.columns(2)
                    with col_s1:
                        st.markdown(f"**📄 Source Article (Where to add link):**\n[{source.get('url', '')}]({source.get('url', '')})")
                    with col_s2:
                        st.markdown(f"**🎯 Target Page (Destination):**\n[{target.get('url', '')}]({target.get('url', '')})")
                        
                    st.markdown("<br>", unsafe_allow_html=True)
                    
                    # 6-Factor Composite Score Breakdown Card
                    st.markdown(f"""
                    <div class="score-breakdown-box">
                        <div class="score-item">Overall: <strong>{ov_score:.1f}</strong></div>
                        <div class="score-item">Semantic (35%): <strong>{sem_score:.1f}</strong></div>
                        <div class="score-item">Anchor Match (20%): <strong>{anchor_score:.1f}</strong></div>
                        <div class="score-item">Context (15%): <strong>{ctx_score:.1f}</strong></div>
                        <div class="score-item">Linkability (10%): <strong>{link_score:.1f}</strong></div>
                        <div class="score-item">Content Quality (10%): <strong>{content_score:.1f}</strong></div>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    col_info1, col_info2 = st.columns([3, 1])
                    with col_info1:
                        st.markdown(f"💡 **Editorial Reason:** {opp.get('reason', '')}")
                    with col_info2:
                        st.markdown(badge_type, unsafe_allow_html=True)

                    st.markdown("---")
                    p_num = int(loc.get("paragraph_index", 0)) + 1
                    s_num = int(loc.get("sentence_index", 0)) + 1
                    s_char_start = loc.get("sentence_char_start", 0)
                    s_char_end = loc.get("sentence_char_end", 0)
                    st.markdown(f"📍 **Precise Location:** `Paragraph #{p_num}` ➔ `Sentence #{s_num}` (Anchor offsets in sentence: chars `{s_char_start}–{s_char_end}`)")
                    
                    diff_col1, diff_col2 = st.columns(2)
                    with diff_col1:
                        st.markdown("**Original Sentence in Source Article:**")
                        st.info(placement.get("original_sentence", ""))
                    with diff_col2:
                        st.markdown("**Suggested Contextual Placement (Preview):**")
                        st.success(placement.get("suggested_sentence_edit", ""))

                    # Ready to paste code tabs
                    code_tab1, code_tab2 = st.tabs(["📝 Ready-to-Paste Markdown", "🌐 Ready-to-Paste HTML"])
                    with code_tab1:
                        st.code(placement.get("ready_to_paste_markdown", ""), language="markdown")
                    with code_tab2:
                        st.code(placement.get("ready_to_paste_html", ""), language="html")

with tab_audit:
    st.subheader("🚫 Excluded Articles & Audit Log")
    st.markdown("Inspect every article evaluated by the engine and the exact reason it was excluded or rejected.")
    
    if "analysis_result" in st.session_state:
        excluded_log = st.session_state["analysis_result"].get("excluded_articles_log", [])
        if not excluded_log:
            st.info("No articles were excluded during this run.")
        else:
            for item in excluded_log:
                code = item.get("reason_code")
                icon = "🔗" if code == "ALREADY_LINKED" else ("🌐" if code == "WRONG_DOMAIN" else ("📉" if "LOW" in code else "⚠️"))
                with st.container():
                    st.markdown(f"**{icon} {item.get('title')}**")
                    st.caption(f"URL: {item.get('url')} | Code: `{code}` | Anchor: `{item.get('candidate_anchor')}`")
                    st.warning(item.get("explanation"))
                    st.markdown("---")
    else:
        st.info("Run an opportunity analysis to view the exclusion audit log.")

with tab_about:
    st.subheader("Architecture & Methodological Highlights")
    st.markdown("""
    ### 🛡️ Core Principle: Code handles facts. AI handles meaning.
    
    1. **Layer 1 — Deterministic Facts:**
       - **Strict Domain Partitioning**: Source and target MUST share the same domain for internal link opportunities.
       - **URL Normalization**: Canonical URLs, trailing slashes, UTM stripping, and default file removal.
       - **Multi-Format Link Detection**: Deterministically excludes pages that already link to the target across HTML, Markdown, and raw URLs.
       - **Exact Anchor & Coordinate Offsets**: Calculates exact character offsets from the verbatim source sentence.
       - **Weak Pattern Detection**: Automatically rejects promotional and self-referential phrases (`already reviewed`, `our dedicated page`).
       
    2. **Layer 2 — Semantic Retrieval & Cost Optimization:**
       - **Hybrid Funnel**: BM25 keyword matching + Vector Cosine Similarity (`text-embedding-004`).
       - **Shortlisting**: Only top 10 candidates are passed to Gemini, minimizing API cost and latency.
       
    3. **Layer 3 — Gemini AI Editorial Judgment:**
       - Evaluates search intent, topical harmony, and clause naturalness.
       
    4. **Layer 4 — Hard Gate Validation:**
       - Validates all 17 checkpoints before rendering results (zero hallucinations, zero missing offsets, zero placeholder text).
       - Builds live Markdown `[anchor](target_url)` and HTML `<a href="target_url">anchor</a>` code snippets.
    """)
