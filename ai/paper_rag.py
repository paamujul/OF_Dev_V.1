"""
rag-based paper ingestion engine.
reads all pdfs from the papers/ directory, chunks them,
builds a faiss vector store, and extracts a master findings
dictionary using gemini as the llm backbone.
"""

import os
import json
import time
import hashlib
from PyPDF2 import PdfReader
from google import genai

from config.settings import gemini_api_key, gemini_model_name
from google.genai import types


papers_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "papers")
cache_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ai", "cache")
findings_cache_path = os.path.join(cache_dir, "master_findings.json")
improvement_log_path = os.path.join(cache_dir, "improvement_log.json")


def extract_text_from_pdf(pdf_path):
    """extracts raw text from a single pdf file."""
    try:
        reader = PdfReader(pdf_path)
    except Exception as e:
        print(f"  warning: could not open {os.path.basename(pdf_path)}: {e}")
        return ""
    text = ""
    for i, page in enumerate(reader.pages):
        try:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
        except Exception:
            pass
    return text


def chunk_text(text, chunk_size=2000, overlap=300):
    """splits text into overlapping chunks for embedding."""
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]
        if chunk.strip():
            chunks.append(chunk.strip())
        start += chunk_size - overlap
    return chunks


def ingest_all_papers():
    """reads every pdf in papers/ and returns a list of dicts with filename, text, and chunks."""
    papers = []
    if not os.path.exists(papers_dir):
        return papers

    for fname in sorted(os.listdir(papers_dir)):
        if not fname.lower().endswith(".pdf"):
            continue
        fpath = os.path.join(papers_dir, fname)
        try:
            text = extract_text_from_pdf(fpath)
            if not text.strip():
                print(f"  skipping {fname} (no extractable text)")
                continue
            chunks = chunk_text(text)
            papers.append({
                "filename": fname,
                "full_text": text,
                "chunks": chunks,
                "chunk_count": len(chunks),
            })
        except Exception as e:
            print(f"  warning: failed to ingest {fname}: {e}")
    return papers


def compute_papers_hash(papers):
    """creates a deterministic hash of all paper filenames + sizes for cache invalidation."""
    sig = ""
    for p in papers:
        sig += p["filename"] + str(len(p["full_text"]))
    return hashlib.md5(sig.encode()).hexdigest()


def build_master_findings(papers, api_key=None):
    """
    uses gemini to perform a map-reduce extraction of findings.
    map: summarize each paper into structured findings.
    reduce: merge all findings into a single master dictionary.
    """
    key = api_key or gemini_api_key
    client = genai.Client(api_key=key)

    map_prompt = """you are a sports science researcher. read the following research paper excerpt and extract ALL actionable findings relevant to elite athlete performance, recovery, and readiness.

for each finding, return a json object with these exact keys:
- "finding_id": a short unique slug (e.g., "iron_supplementation_ferritin")
- "category": one of ["sleep", "nutrition", "supplementation", "thermoregulation", "circadian", "recovery", "hydration", "biomechanics", "cardiovascular", "hormonal", "inflammation", "neural"]
- "finding": the core scientific finding in one sentence
- "actionable_recommendation": a precise, dosage-specific recommendation (e.g., "take 325mg ferrous sulfate with 200mg vitamin c on empty stomach")
- "magnitude_of_effect": qualitative assessment: "high", "moderate", or "low"
- "evidence_level": "strong", "moderate", or "preliminary"
- "relevant_biomarkers": list of biomarker names this finding relates to
- "source_paper": the paper filename

return ONLY a valid json array of finding objects. no markdown, no explanation."""

    all_paper_findings = []

    for paper in papers:
        combined_text = "\n".join(paper["chunks"][:10])
        if len(combined_text) > 15000:
            combined_text = combined_text[:15000]

        for attempt in range(3):
            try:
                response = client.models.generate_content(
                    model=gemini_model_name,
                    contents=f"paper filename: {paper['filename']}\n\n{combined_text}",
                    config=types.GenerateContentConfig(
                        system_instruction=map_prompt,
                        temperature=0.2,
                        max_output_tokens=8192,
                    ),
                )
                raw = response.text.strip()
                if raw.startswith("```"):
                    raw = raw.split("\n", 1)[1]
                    if raw.endswith("```"):
                        raw = raw[:-3]
                findings = json.loads(raw)
                for f in findings:
                    f["source_paper"] = paper["filename"]
                all_paper_findings.extend(findings)
                break
            except Exception as e:
                if attempt < 2 and ("429" in str(e) or "503" in str(e) or "RESOURCE_EXHAUSTED" in str(e)):
                    wait = 30 * (attempt + 1)
                    print(f"  rate limited on {paper['filename']}, waiting {wait}s...")
                    time.sleep(wait)
                else:
                    print(f"  warning: failed to extract from {paper['filename']}: {e}")
                    break

    reduce_prompt = """you are a sports science researcher. you have extracted findings from multiple research papers. your job is to deduplicate, merge, and organize them into a single master findings dictionary.

rules:
1. merge duplicate or near-duplicate findings into one entry, keeping the strongest evidence level and combining source papers
2. ensure every recommendation is PRECISE: dosages in mg/iu/ml, durations in hours/minutes, temperatures in celsius/fahrenheit
3. if two papers contradict each other, note the conflict in the finding
4. group findings by category
5. assign each finding a "priority_rank" from 1 (most impactful) to n (least impactful)

return a json object with this structure:
{
  "total_findings": <int>,
  "categories": {
    "<category_name>": [
      {
        "finding_id": "...",
        "finding": "...",
        "actionable_recommendation": "...",
        "magnitude_of_effect": "high|moderate|low",
        "evidence_level": "strong|moderate|preliminary",
        "relevant_biomarkers": [...],
        "source_papers": [...],
        "priority_rank": <int>
      }
    ]
  }
}

return ONLY valid json. no markdown, no explanation."""

    try:
        response = client.models.generate_content(
            model=gemini_model_name,
            contents=f"here are all extracted findings from {len(papers)} papers:\n\n{json.dumps(all_paper_findings, indent=2)}",
            config=types.GenerateContentConfig(
                system_instruction=reduce_prompt,
                temperature=0.1,
                max_output_tokens=16384,
            ),
        )
        raw = response.text.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1]
            if raw.endswith("```"):
                raw = raw[:-3]
        master = json.loads(raw)
    except Exception as e:
        print(f"  warning: reduce step failed: {e}")
        master = {
            "total_findings": len(all_paper_findings),
            "categories": {"uncategorized": all_paper_findings},
        }

    return master


def load_or_build_findings(api_key=None):
    """loads cached findings if papers haven't changed, otherwise rebuilds."""
    os.makedirs(cache_dir, exist_ok=True)

    papers = ingest_all_papers()
    if not papers:
        return {"total_findings": 0, "categories": {}}

    current_hash = compute_papers_hash(papers)

    if os.path.exists(findings_cache_path):
        with open(findings_cache_path, "r") as f:
            cached = json.load(f)
        if cached.get("_papers_hash") == current_hash:
            print("  using cached master findings (papers unchanged)")
            return cached

    print(f"  ingesting {len(papers)} papers ({sum(p['chunk_count'] for p in papers)} chunks)...")
    master = build_master_findings(papers, api_key)
    master["_papers_hash"] = current_hash

    with open(findings_cache_path, "w") as f:
        json.dump(master, f, indent=2)
    print(f"  master findings cached to {findings_cache_path}")

    return master


def load_improvement_log():
    """loads the improvement tracking dictionary."""
    if os.path.exists(improvement_log_path):
        with open(improvement_log_path, "r") as f:
            return json.load(f)
    return {"tracked_suggestions": [], "improvement_history": []}


def save_improvement_log(log):
    """persists the improvement tracking dictionary."""
    os.makedirs(cache_dir, exist_ok=True)
    with open(improvement_log_path, "w") as f:
        json.dump(log, f, indent=2)


def query_findings_for_context(master_findings, athlete_state, api_key=None):
    """
    rag retrieval step: given the athlete's current state and the master
    findings, uses gemini to select the most relevant findings and rank
    them by urgency for this specific athlete on this specific day.
    """
    key = api_key or gemini_api_key
    client = genai.Client(api_key=key)

    prompt = """you are the obeo fit research advisor. you have access to a master dictionary of scientific findings extracted from peer-reviewed sports science literature, and the current athlete telemetry state.

your job:
1. analyze the athlete's current biometric state (bloodwork, wearables, travel, readiness scores)
2. cross-reference against the master findings dictionary
3. identify which findings are MOST relevant to this athlete RIGHT NOW
4. return the top findings ranked by urgency and impact

return a json array of the top 10 most relevant findings, each with:
- "finding_id": from the master dictionary
- "relevance_score": 0.0 to 1.0 (how relevant to this athlete today)
- "urgency": "immediate", "within_24h", "within_week"
- "athlete_data_trigger": which specific data point triggered this finding
- "personalized_recommendation": the finding's recommendation, customized with the athlete's actual values

return ONLY valid json. no markdown."""

    try:
        response = client.models.generate_content(
            model=gemini_model_name,
            contents=(
                f"master findings dictionary:\n{json.dumps(master_findings, indent=2)}\n\n"
                f"current athlete state:\n{json.dumps(athlete_state, indent=2)}"
            ),
            config=types.GenerateContentConfig(
                system_instruction=prompt,
                temperature=0.2,
                max_output_tokens=8192,
            ),
        )
        raw = response.text.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1]
            if raw.endswith("```"):
                raw = raw[:-3]
        return json.loads(raw)
    except Exception as e:
        print(f"  warning: rag query failed: {e}")
        return []
