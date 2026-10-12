import os
import shutil
from pathlib import Path
from typing import List, Optional
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, status, Header
from fastapi.middleware.cors import CORSMiddleware

from backend.config import UPLOAD_DIR, GEMINI_MODEL
from backend.database import init_db, save_meeting, list_meetings, get_meeting, delete_meeting, save_query_record
from backend.schemas import MeetingResponse, MeetingListItem, QueryRequest, QueryResponse
from backend.services import transcribe_audio_file, analyze_transcript, query_meeting
from backend.vector_store import index_transcript, search_similar_chunks

app = FastAPI(
    title="Meeting Intelligence API",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    init_db()


@app.get("/api/health")
def health_check():
    return {
        "status": "healthy",
        "model": GEMINI_MODEL,
        "upload_dir_exists": UPLOAD_DIR.exists()
    }


@app.post("/api/meetings/upload", response_model=MeetingResponse, status_code=status.HTTP_201_CREATED)
def upload_meeting(
    file: Optional[UploadFile] = File(None),
    transcript_text: Optional[str] = Form(None),
    x_gemini_api_key: Optional[str] = Header(None)
):
    if not file and not transcript_text:
        raise HTTPException(
            status_code=400,
            detail="Either an audio file or transcript_text must be provided."
        )

    file_path_str = ""
    file_size = 0
    filename = "transcript_input.txt"

    if file:
        filename = file.filename or "audio_file.wav"
        allowed_extensions = {".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac", ".webm", ".mp4", ".mov", ".mkv", ".avi"}
        ext = Path(filename).suffix.lower()
        if ext not in allowed_extensions:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported format {ext}."
            )

        saved_path = UPLOAD_DIR / filename
        with open(saved_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        file_path_str = str(saved_path)
        file_size = saved_path.stat().st_size

    try:
        if transcript_text and transcript_text.strip():
            transcript = transcript_text.strip()
        else:
            transcript = transcribe_audio_file(file_path_str, api_key=x_gemini_api_key)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    if not transcript or not transcript.strip():
        raise HTTPException(status_code=422, detail="Transcript is empty.")

    try:
        analysis = analyze_transcript(transcript, api_key=x_gemini_api_key)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    meeting_id = save_meeting(
        filename=filename,
        file_path=file_path_str,
        file_size=file_size,
        transcript=transcript,
        analysis=analysis.model_dump()
    )

    try:
        index_transcript(meeting_id, transcript, api_key=x_gemini_api_key)
    except Exception:
        pass

    saved_data = get_meeting(meeting_id)
    if not saved_data:
        raise HTTPException(status_code=500, detail="Failed to retrieve saved meeting.")

    return saved_data


@app.get("/api/meetings", response_model=List[MeetingListItem])
def get_meetings():
    return list_meetings()


@app.get("/api/meetings/{meeting_id}", response_model=MeetingResponse)
def get_meeting_by_id(meeting_id: int):
    meeting = get_meeting(meeting_id)
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found.")
    return meeting


@app.post("/api/meetings/{meeting_id}/query", response_model=QueryResponse)
def query_meeting_by_id(
    meeting_id: int,
    payload: QueryRequest,
    x_gemini_api_key: Optional[str] = Header(None)
):
    meeting = get_meeting(meeting_id)
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found.")

    if not payload.query or not payload.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty.")

    retrieved_chunks = []
    retrieved_text = ""
    try:
        retrieved_chunks = search_similar_chunks(
            meeting_id,
            payload.query.strip(),
            top_k=3,
            api_key=x_gemini_api_key
        )
        if retrieved_chunks:
            retrieved_text = "\n---\n".join([f"[{c['speaker']}] {c['text']}" for c in retrieved_chunks])
    except Exception:
        pass

    try:
        answer = query_meeting(
            transcript=meeting["transcript"],
            analysis_data=meeting["analysis"],
            query=payload.query.strip(),
            api_key=x_gemini_api_key,
            retrieved_context=retrieved_text
        )
        save_query_record(meeting_id, payload.query.strip(), answer)
        return QueryResponse(
            meeting_id=meeting_id,
            query=payload.query.strip(),
            answer=answer,
            retrieved_chunks=retrieved_chunks
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



@app.delete("/api/meetings/{meeting_id}")
def delete_meeting_by_id(meeting_id: int):
    meeting = get_meeting(meeting_id)
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found.")

    if meeting.get("file_path") and os.path.exists(meeting["file_path"]):
        try:
            os.remove(meeting["file_path"])
        except Exception:
            pass

    success = delete_meeting(meeting_id)
    return {"success": success}
