from __future__ import annotations
import os

def _supabase():
    url = os.getenv("SUPABASE_URL", "")
    key = os.getenv("SUPABASE_KEY", "")
    if not url or url == "your_supabase_url_here":
        return None
    from supabase import create_client
    return create_client(url, key)

def get_clinical_guidelines_for_wound(wound_type: str) -> str:
    """
    RAG Retrieval: Queries the pgvector clinical_knowledge_base in Supabase
    to retrieve only the necessary guidelines for the specific wound type.
    This saves massive amounts of tokens by avoiding sending the entire library.
    """
    sb = _supabase()
    if not sb:
        # Fallback to a hardcoded generic string if Supabase is unavailable
        return "GENERAL GUIDELINE: Ensure moisture balance. Debride slough if >50%. Monitor for STONES/NERDS infection criteria."

    try:
        # In a full production system, we would:
        # 1. Use Gemini Text embedding API to embed the `wound_type` (e.g. "Diabetic Foot Ulcer")
        # 2. Call an RPC function `match_guidelines(query_embedding)` in Supabase
        
        # For this hackathon/MVP implementation, we can just do a standard relational text match
        # on the `wound_type_tag` since we have a fixed number of major wound types.
        
        resp = sb.table("clinical_knowledge_base").select("content, guideline_source").ilike("wound_type_tag", f"%{wound_type}%").execute()
        
        if resp.data:
            chunks = []
            for row in resp.data:
                chunks.append(f"[{row['guideline_source']}]: {row['content']}")
            return "\n\n".join(chunks)
        else:
            return "GENERAL GUIDELINE: Ensure moisture balance. Debride slough if >50%. Monitor for STONES/NERDS infection criteria."
            
    except Exception as e:
        print(f"[RAG] Vector retrieval failed: {e}")
        return "GENERAL GUIDELINE: Ensure moisture balance. Debride slough if >50%. Monitor for STONES/NERDS infection criteria."
