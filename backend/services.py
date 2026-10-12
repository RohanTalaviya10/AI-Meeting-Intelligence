import os
import json
import mimetypes
from datetime import date
from pathlib import Path
from typing import Optional, Dict, Any, List
from backend.config import GEMINI_MODEL, GEMINI_API_KEY, FALLBACK_MODELS
from backend.schemas import MeetingAnalysis, ActionItem


def get_api_key(provided_key: Optional[str] = None, allow_demo: bool = True) -> str:
    key = provided_key or GEMINI_API_KEY or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or ""
    if not key:
        if allow_demo:
            return "DEMO_KEY"
        raise ValueError("Gemini API key is required.")
    return key.strip()


def get_mime_type(file_path: str) -> str:
    mime, _ = mimetypes.guess_type(file_path)
    if mime:
        return mime
    ext = Path(file_path).suffix.lower()
    mapping = {
        ".mp3": "audio/mp3",
        ".wav": "audio/wav",
        ".m4a": "audio/m4a",
        ".aac": "audio/m4a",
        ".ogg": "audio/ogg",
        ".flac": "audio/flac",
        ".mp4": "video/mp4",
        ".mov": "video/quicktime",
        ".webm": "video/webm",
        ".mkv": "video/x-matroska",
        ".avi": "video/x-msvideo"
    }
    return mapping.get(ext, "audio/wav")


def clean_json_text(text: str) -> str:
    text = text.strip()
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    return text.strip()


def deduplicate_action_items(items: List[ActionItem]) -> List[ActionItem]:
    seen = set()
    unique = []
    for it in items:
        clean_key = it.task.lower().strip()
        if clean_key not in seen:
            seen.add(clean_key)
            unique.append(it)
    return unique


def check_overdue_deadlines(items: List[ActionItem]) -> List[ActionItem]:
    today_str = date.today().isoformat()
    for it in items:
        if it.normalized_deadline:
            try:
                it.is_overdue = it.normalized_deadline < today_str
            except Exception:
                pass
    return items


def transcribe_audio_file(file_path: str, api_key: Optional[str] = None, model_name: Optional[str] = None) -> str:
    key = get_api_key(api_key)
    if key == "DEMO_KEY":
        sample_txt = Path(__file__).resolve().parent.parent / "sample_data" / "sample_transcript.txt"
        if sample_txt.exists():
            return sample_txt.read_text(encoding="utf-8").strip()
        return "Manager: We need to finalize the beta launch by 15 September.\nRahul: I can complete the payment API integration by 10 September."

    models = [model_name] if model_name else [GEMINI_MODEL] + FALLBACK_MODELS
    last_error = None

    for model in models:
        if not model:
            continue
        try:
            try:
                from google import genai
                client = genai.Client(api_key=key)
                uploaded = client.files.upload(file=file_path)
                prompt = (
                    "Transcribe this recording verbatim with speaker identification. "
                    "Label speakers like 'Manager:', 'Rahul:', 'Priya:'. "
                    "Return only the transcript."
                )
                response = client.models.generate_content(model=model, contents=[uploaded, prompt])
                if response and response.text:
                    return response.text.strip()
            except ImportError:
                pass

            import google.generativeai as legacy_genai
            legacy_genai.configure(api_key=key)
            uploaded_file = legacy_genai.upload_file(path=file_path)
            gen_model = legacy_genai.GenerativeModel(model)
            prompt = (
                "Transcribe this recording verbatim with speaker identification. "
                "Label speakers like 'Manager:', 'Rahul:', 'Priya:'. "
                "Return only the transcript."
            )
            response = gen_model.generate_content([uploaded_file, prompt])
            if response and response.text:
                return response.text.strip()

        except Exception as e:
            last_error = e
            continue

    raise RuntimeError(f"Transcription failed: {last_error}")


def analyze_transcript(transcript: str, api_key: Optional[str] = None, model_name: Optional[str] = None) -> MeetingAnalysis:
    key = get_api_key(api_key)
    if key == "DEMO_KEY":
        sample_json_path = Path(__file__).resolve().parent.parent / "sample_data" / "sample_output.json"
        if sample_json_path.exists():
            data = json.loads(sample_json_path.read_text(encoding="utf-8"))
            analysis = MeetingAnalysis(**data)
            analysis.action_items = check_overdue_deadlines(deduplicate_action_items(analysis.action_items))
            return analysis

    models = [model_name] if model_name else [GEMINI_MODEL] + FALLBACK_MODELS

    prompt = f"""Analyze this meeting transcript and output JSON.

Extract:
- summary: brief executive summary
- decisions: list of finalized decisions
- action_items: list of objects with fields:
    - task: task description
    - assignee: person name or null
    - deadline: deadline as mentioned in dialogue
    - normalized_deadline: deadline converted to standard YYYY-MM-DD format if date/month is known or null
    - priority: High, Medium, or Low
    - status: Pending, In Progress, or Completed
    - confidence: float score between 0.0 and 1.0 indicating extraction certainty
- risks_blockers: list of blockers/dependencies
- unresolved_items: list of open questions/unresolved topics
- participants: list of speaker names
- confidence_score: float score between 0.0 and 1.0 for overall analysis certainty

Format strictly as JSON:
{{
  "summary": "...",
  "decisions": ["..."],
  "action_items": [
    {{
      "task": "...",
      "assignee": "...",
      "deadline": "...",
      "normalized_deadline": "YYYY-MM-DD",
      "priority": "High/Medium/Low",
      "status": "Pending/In Progress/Completed",
      "confidence": 0.95
    }}
  ],
  "risks_blockers": ["..."],
  "unresolved_items": ["..."],
  "participants": ["..."],
  "confidence_score": 0.95
}}

TRANSCRIPT:
{transcript}
"""

    last_error = None
    for model in models:
        if not model:
            continue
        try:
            raw_text = ""
            try:
                from google import genai
                from google.genai import types

                client = genai.Client(api_key=key)
                response = client.models.generate_content(
                    model=model,
                    contents=prompt,
                    config=types.GenerateContentConfig(response_mime_type="application/json")
                )
                if response and response.text:
                    raw_text = response.text
            except ImportError:
                pass

            if not raw_text:
                import google.generativeai as legacy_genai
                legacy_genai.configure(api_key=key)
                gen_model = legacy_genai.GenerativeModel(
                    model,
                    generation_config={"response_mime_type": "application/json"}
                )
                response = gen_model.generate_content(prompt)
                if response and response.text:
                    raw_text = response.text

            cleaned = clean_json_text(raw_text)
            data = json.loads(cleaned)
            analysis = MeetingAnalysis(**data)
            analysis.action_items = check_overdue_deadlines(deduplicate_action_items(analysis.action_items))
            return analysis

        except Exception as e:
            last_error = e
            continue

    raise RuntimeError(f"Analysis extraction failed: {last_error}")


def query_meeting(
    transcript: str,
    analysis_data: Dict[str, Any],
    query: str,
    api_key: Optional[str] = None,
    model_name: Optional[str] = None,
    retrieved_context: Optional[str] = None
) -> str:
    key = get_api_key(api_key)
    if key == "DEMO_KEY":
        q_lower = query.lower()
        if "rahul" in q_lower and ("task" in q_lower or "assigned" in q_lower or "action" in q_lower):
            return "Rahul was assigned two tasks:\n1. Complete payment API integration (Deadline: 10 September)\n2. Investigate mobile timeout issue (Deadline: tomorrow)."
        elif "deadline" in q_lower:
            return "The extracted deadlines are:\n- 10 September: Rahul to complete payment API integration.\n- 12 September: Priya to prepare QA test cases.\n- Tomorrow: Rahul to investigate mobile timeout issue.\n- Today: Manager to provide access to payment gateway test account."
        elif "decision" in q_lower:
            return "The confirmed final decision is that the beta launch date remains 15 September."
        elif "blocker" in q_lower or "open" in q_lower or "dependency" in q_lower:
            return "The active blocker is: Rahul requires access to the payment gateway test account (Manager agreed to provide it today)."
        elif "pricing" in q_lower:
            return "Pricing remains unresolved because it is not yet finalized; the discussion was deferred to the next meeting."
        elif "launch" in q_lower or "beta" in q_lower:
            return "The beta launch date is finalized for 15 September."
        else:
            return f"Based on the meeting: {analysis_data.get('summary', '')}"

    models = [model_name] if model_name else [GEMINI_MODEL] + FALLBACK_MODELS

    context_section = f"Retrieved Relevant Excerpts:\n{retrieved_context}\n\nFull Transcript:\n{transcript}" if retrieved_context else f"Transcript:\n{transcript}"

    prompt = f"""Answer the question concisely based on the transcript and meeting data.

Summary: {analysis_data.get('summary', '')}
Decisions: {json.dumps(analysis_data.get('decisions', []))}
Action Items: {json.dumps(analysis_data.get('action_items', []))}
Blockers: {json.dumps(analysis_data.get('risks_blockers', []))}
Unresolved: {json.dumps(analysis_data.get('unresolved_items', []))}

{context_section}

Question:
{query}
"""

    last_error = None
    for model in models:
        if not model:
            continue
        try:
            try:
                from google import genai
                client = genai.Client(api_key=key)
                resp = client.models.generate_content(model=model, contents=prompt)
                if resp and resp.text:
                    return resp.text.strip()
            except ImportError:
                pass

            import google.generativeai as legacy_genai
            legacy_genai.configure(api_key=key)
            gen_model = legacy_genai.GenerativeModel(model)
            resp = gen_model.generate_content(prompt)
            if resp and resp.text:
                return resp.text.strip()

        except Exception as e:
            last_error = e
            continue

    raise RuntimeError(f"Query answering failed: {last_error}")
