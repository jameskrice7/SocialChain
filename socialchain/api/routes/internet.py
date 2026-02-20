import re
import urllib.parse

from flask import Blueprint, jsonify, request

try:
    import requests as _requests
    _REQUESTS_AVAILABLE = True
except ImportError:
    _REQUESTS_AVAILABLE = False

internet_bp = Blueprint("internet", __name__)

_DDGAPI = "https://api.duckduckgo.com/"
_HEADERS = {
    "User-Agent": (
        "SocialChain/1.0 (Decentralized Network Search; "
        "+https://github.com/jameskrice7/SocialChain)"
    )
}


def _ddg_search(query: str, max_results: int = 8) -> dict:
    """Query the DuckDuckGo Instant Answer API and return structured results."""
    params = {
        "q": query,
        "format": "json",
        "no_html": "1",
        "skip_disambig": "1",
        "no_redirect": "1",
    }
    try:
        resp = _requests.get(
            _DDGAPI,
            params=params,
            headers=_HEADERS,
            timeout=8,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        return {"error": str(exc), "results": [], "abstract": "", "query": query}

    results = []

    # Instant answer
    if data.get("AbstractText"):
        results.append(
            {
                "title": data.get("Heading", query),
                "snippet": data["AbstractText"],
                "url": data.get("AbstractURL", ""),
                "source": data.get("AbstractSource", ""),
                "type": "abstract",
            }
        )

    # Direct answer
    if data.get("Answer"):
        results.append(
            {
                "title": "Direct Answer",
                "snippet": data["Answer"],
                "url": "",
                "source": data.get("AnswerType", "instant"),
                "type": "answer",
            }
        )

    # Related topics
    for topic in (data.get("RelatedTopics") or [])[:max_results]:
        if isinstance(topic, dict) and topic.get("Text"):
            url = topic.get("FirstURL", "")
            results.append(
                {
                    "title": _extract_title(topic.get("Text", "")),
                    "snippet": topic["Text"],
                    "url": url,
                    "source": "DuckDuckGo",
                    "type": "related",
                }
            )
        elif isinstance(topic, dict) and topic.get("Topics"):
            for sub in topic["Topics"][:2]:
                if sub.get("Text"):
                    results.append(
                        {
                            "title": _extract_title(sub.get("Text", "")),
                            "snippet": sub["Text"],
                            "url": sub.get("FirstURL", ""),
                            "source": "DuckDuckGo",
                            "type": "related",
                        }
                    )

    return {
        "query": query,
        "abstract": data.get("AbstractText", ""),
        "abstract_url": data.get("AbstractURL", ""),
        "results": results[:max_results],
        "result_count": len(results),
    }


def _extract_title(text: str) -> str:
    """Extract a short title from DuckDuckGo text (up to first ' - ' or 60 chars)."""
    text = text.strip()
    sep_idx = text.find(" - ")
    if sep_idx > 0:
        return text[:min(sep_idx, 80)]
    return text[:60]


@internet_bp.route("/api/search", methods=["GET"])
def search():
    """Web search proxy using DuckDuckGo Instant Answer API."""
    query = request.args.get("q", "").strip()
    if not query:
        return jsonify({"error": "Missing query parameter 'q'"}), 400
    if len(query) > 256:
        return jsonify({"error": "Query too long (max 256 chars)"}), 400

    if not _REQUESTS_AVAILABLE:
        return jsonify({"error": "requests library not available", "results": []}), 503

    max_results = min(int(request.args.get("limit", 8)), 20)
    result = _ddg_search(query, max_results=max_results)
    return jsonify(result), 200


@internet_bp.route("/api/internet/topology", methods=["GET"])
def internet_topology():
    """Return a synthesized internet topology snapshot for visualization."""
    # Generate a static but meaningful topology of internet-scale nodes
    # grouped by tier (ISP tiers, CDN, cloud, edge, etc.)
    topology = {
        "tiers": [
            {
                "name": "Tier 1 ISPs",
                "color": "#dc3545",
                "nodes": [
                    {"id": "att", "label": "AT&T", "region": "US"},
                    {"id": "ntt", "label": "NTT", "region": "JP"},
                    {"id": "lumen", "label": "Lumen/CenturyLink", "region": "US"},
                    {"id": "telia", "label": "Telia", "region": "SE"},
                    {"id": "cogent", "label": "Cogent", "region": "US"},
                    {"id": "telecom_italia", "label": "Telecom Italia", "region": "IT"},
                    {"id": "verizon", "label": "Verizon", "region": "US"},
                ],
            },
            {
                "name": "Cloud / Hyperscalers",
                "color": "#0dcaf0",
                "nodes": [
                    {"id": "aws", "label": "AWS", "region": "Global"},
                    {"id": "azure", "label": "Azure", "region": "Global"},
                    {"id": "gcp", "label": "Google Cloud", "region": "Global"},
                    {"id": "cloudflare", "label": "Cloudflare", "region": "Global"},
                    {"id": "fastly", "label": "Fastly CDN", "region": "Global"},
                    {"id": "akamai", "label": "Akamai", "region": "Global"},
                ],
            },
            {
                "name": "Internet Exchange Points",
                "color": "#ffc107",
                "nodes": [
                    {"id": "ams_ix", "label": "AMS-IX", "region": "NL"},
                    {"id": "de_cix", "label": "DE-CIX", "region": "DE"},
                    {"id": "linx", "label": "LINX", "region": "GB"},
                    {"id": "nap_americas", "label": "NAP Americas", "region": "US"},
                    {"id": "equinix", "label": "Equinix IX", "region": "Global"},
                ],
            },
            {
                "name": "SocialChain Nodes",
                "color": "#198754",
                "nodes": [
                    {"id": "sc_main", "label": "SC Mainnet", "region": "Decentralized"},
                    {"id": "sc_peer_eu", "label": "SC EU Peer", "region": "EU"},
                    {"id": "sc_peer_us", "label": "SC US Peer", "region": "US"},
                    {"id": "sc_peer_ap", "label": "SC AP Peer", "region": "AP"},
                ],
            },
        ],
        "links": [
            {"source": "att", "target": "ntt"},
            {"source": "att", "target": "lumen"},
            {"source": "ntt", "target": "telia"},
            {"source": "cogent", "target": "att"},
            {"source": "cogent", "target": "telia"},
            {"source": "verizon", "target": "att"},
            {"source": "verizon", "target": "lumen"},
            {"source": "aws", "target": "att"},
            {"source": "aws", "target": "cogent"},
            {"source": "azure", "target": "verizon"},
            {"source": "azure", "target": "ntt"},
            {"source": "gcp", "target": "att"},
            {"source": "gcp", "target": "telia"},
            {"source": "cloudflare", "target": "aws"},
            {"source": "cloudflare", "target": "ams_ix"},
            {"source": "cloudflare", "target": "de_cix"},
            {"source": "akamai", "target": "linx"},
            {"source": "akamai", "target": "ams_ix"},
            {"source": "fastly", "target": "de_cix"},
            {"source": "ams_ix", "target": "de_cix"},
            {"source": "ams_ix", "target": "linx"},
            {"source": "de_cix", "target": "equinix"},
            {"source": "linx", "target": "equinix"},
            {"source": "nap_americas", "target": "equinix"},
            {"source": "sc_main", "target": "cloudflare"},
            {"source": "sc_main", "target": "aws"},
            {"source": "sc_peer_eu", "target": "ams_ix"},
            {"source": "sc_peer_eu", "target": "de_cix"},
            {"source": "sc_peer_us", "target": "nap_americas"},
            {"source": "sc_peer_us", "target": "aws"},
            {"source": "sc_peer_ap", "target": "ntt"},
            {"source": "sc_peer_ap", "target": "gcp"},
            {"source": "sc_main", "target": "sc_peer_eu"},
            {"source": "sc_main", "target": "sc_peer_us"},
            {"source": "sc_main", "target": "sc_peer_ap"},
        ],
    }

    # Integrate user-specific social network nodes when a DID is provided
    did = request.args.get("did", "").strip()
    if did:
        try:
            from flask import current_app
            state = current_app.app_state
            profile = state.network_map.get_profile(did)
            if profile and profile.metadata:
                user_social_links = profile.metadata.get("social_links", {})
                _PLATFORM_META = {
                    "facebook":  {"label": "Facebook",   "region": "Global"},
                    "linkedin":  {"label": "LinkedIn",   "region": "Global"},
                    "instagram": {"label": "Instagram",  "region": "Global"},
                    "youtube":   {"label": "YouTube",    "region": "Global"},
                    "twitter":   {"label": "Twitter / X", "region": "Global"},
                }
                social_nodes = []
                for platform, meta in _PLATFORM_META.items():
                    if user_social_links.get(platform):
                        social_nodes.append({
                            "id": f"social_{platform}",
                            "label": meta["label"],
                            "region": meta["region"],
                            "url": user_social_links[platform],
                        })
                        topology["links"].append({"source": "sc_main", "target": f"social_{platform}"})
                if social_nodes:
                    topology["tiers"].append({
                        "name": "Your Social Networks",
                        "color": "#6f42c1",
                        "nodes": social_nodes,
                    })
        except Exception:
            pass  # Do not fail topology if profile lookup fails

    return jsonify(topology), 200
