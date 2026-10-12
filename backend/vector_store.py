import re
import numpy as np
from typing import List, Dict, Any, Optional
from backend.config import GEMINI_API_KEY, EMBEDDING_MODEL
from backend.database import save_meeting_chunks, get_meeting_chunks, get_meeting


def chunk_transcript(transcript: str, target_words: int = 100) -> List[Dict[str, Any]]:
    lines = [line.strip() for line in transcript.split("\n") if line.strip()]
    chunks = []
    current_lines = []
    current_speaker = "General"
    current_word_count = 0

    for line in lines:
        speaker_match = re.match(r"^([A-Za-z0-9_\s]{1,30}):\s*(.*)", line)
        if speaker_match:
            speaker = speaker_match.group(1).strip()
            content = speaker_match.group(2).strip()
            if not current_lines:
                current_speaker = speaker
        else:
            speaker = current_speaker
            content = line

        words = len(content.split())
        if current_lines and (current_word_count + words > target_words):
            chunk_text = "\n".join(current_lines)
            chunks.append({
                "chunk_index": len(chunks) + 1,
                "speaker": current_speaker,
                "text": chunk_text
            })
            current_lines = [line]
            current_speaker = speaker
            current_word_count = words
        else:
            current_lines.append(line)
            current_word_count += words

    if current_lines:
        chunk_text = "\n".join(current_lines)
        chunks.append({
            "chunk_index": len(chunks) + 1,
            "speaker": current_speaker,
            "text": chunk_text
        })

    return chunks


def compute_fallback_embedding(text: str, dim: int = 256) -> List[float]:
    vec = np.zeros(dim, dtype=np.float32)
    words = re.findall(r"\w+", text.lower())
    for w in words:
        h = abs(hash(w)) % dim
        vec[h] += 1.0
    norm = np.linalg.norm(vec)
    if norm > 0:
        vec = vec / norm
    return vec.tolist()


def generate_embeddings(texts: List[str], api_key: Optional[str] = None) -> List[List[float]]:
    key = api_key or GEMINI_API_KEY
    if not key or key == "DEMO_KEY":
        return [compute_fallback_embedding(t) for t in texts]

    try:
        from google import genai
        client = genai.Client(api_key=key)
        embeddings = []
        for text in texts:
            resp = client.models.embed_content(model=EMBEDDING_MODEL, contents=text)
            if resp and resp.embeddings:
                embeddings.append(list(resp.embeddings[0].values))
            else:
                embeddings.append(compute_fallback_embedding(text))
        return embeddings
    except Exception:
        pass

    try:
        import google.generativeai as legacy_genai
        legacy_genai.configure(api_key=key)
        embeddings = []
        for text in texts:
            res = legacy_genai.embed_content(
                model=f"models/{EMBEDDING_MODEL}",
                content=text,
                task_type="retrieval_document"
            )
            embeddings.append(res["embedding"])
        return embeddings
    except Exception:
        pass

    return [compute_fallback_embedding(t) for t in texts]


def index_transcript(meeting_id: int, transcript: str, api_key: Optional[str] = None) -> int:
    chunks = chunk_transcript(transcript)
    if not chunks:
        return 0

    texts = [c["text"] for c in chunks]
    embeddings = generate_embeddings(texts, api_key=api_key)

    for i, c in enumerate(chunks):
        c["embedding"] = embeddings[i]

    save_meeting_chunks(meeting_id, chunks)
    return len(chunks)


def search_similar_chunks(
    meeting_id: int,
    query: str,
    top_k: int = 3,
    api_key: Optional[str] = None
) -> List[Dict[str, Any]]:
    chunks = get_meeting_chunks(meeting_id)
    if not chunks:
        meeting = get_meeting(meeting_id)
        if meeting and meeting.get("transcript"):
            index_transcript(meeting_id, meeting["transcript"], api_key=api_key)
            chunks = get_meeting_chunks(meeting_id)

    if not chunks:
        return []

    valid_chunks = [c for c in chunks if c.get("embedding")]
    if not valid_chunks:
        return []

    dim = len(valid_chunks[0]["embedding"])
    query_emb = generate_embeddings([query], api_key=api_key)[0]

    if len(query_emb) != dim:
        query_emb = compute_fallback_embedding(query, dim=dim)

    matrix = np.array([c["embedding"] for c in valid_chunks], dtype=np.float32)
    q_vec = np.array(query_emb, dtype=np.float32)

    norms_m = np.linalg.norm(matrix, axis=1)
    norm_q = np.linalg.norm(q_vec)

    denom = norms_m * norm_q
    denom[denom == 0] = 1e-9
    scores = np.dot(matrix, q_vec) / denom

    scored_chunks = []
    for idx, c in enumerate(valid_chunks):
        scored_chunks.append({
            "chunk_index": c["chunk_index"],
            "speaker": c.get("speaker", "General"),
            "text": c["text"],
            "similarity": round(float(scores[idx]), 4)
        })

    scored_chunks.sort(key=lambda x: x["similarity"], reverse=True)
    return scored_chunks[:top_k]
