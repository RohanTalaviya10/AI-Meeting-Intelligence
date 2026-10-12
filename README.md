# AI Meeting Intelligence and Action Tracker

A system that accepts meeting audio recordings (MP3/WAV), generates a transcript with speaker identification, extracts structured business information (summary, decisions, action items, assignees, deadlines, risks, and unresolved items), stores the results in SQLite, and provides an API and UI to query the conversation.

Built using FastAPI, Streamlit, and Google Gemini 3.1 Flash-Lite.

---

## Architecture

The application follows a simple pipeline:

1. Ingestion: Accepts an audio file (MP3/WAV) or raw transcript text through the API or UI.
2. Speech-to-Text: The audio is sent to Gemini to produce an accurate verbatim transcript with speaker labels.
3. Analysis: The transcript is passed to Gemini with a strict schema to extract:
   - Summary
   - Confirmed decisions
   - Action items (task, assignee, deadline, priority, status)
   - Risks and blockers
   - Unresolved items
   - Participants
4. Storage: Metadata, transcript, and extracted JSON are stored in SQLite (`meetings.db`).
5. Querying: Users can ask questions about the meeting. The query service answers using the transcript and extracted items as context.

---

## Project Structure

```
AI-Meeting-Intelligence/
├── backend/
│   ├── main.py
│   ├── config.py
│   ├── database.py
│   ├── schemas.py
│   ├── services.py
│   └── vector_store.py
├── frontend/
│   └── app.py
├── sample_data/
│   ├── sample_transcript.txt
│   └── sample_output.json
├── scripts/
│   ├── test_pipeline.py
│   └── test_api.py
├── .env.example
├── requirements.txt
├── run.bat
├── postman_collection.json
├── main.py
└── README.md
```

---

## Setup and Installation

### Prerequisites
- Python 3.10+
- A Gemini API key (from Google AI Studio)

### Installation

1. Create and activate a virtual environment:

```bash
python -m venv .venv
.venv\Scripts\activate
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Set up the environment file:

Copy `.env.example` to `.env`:

```bash
copy .env.example .env
```

Set your Gemini API key in `.env`:

```
GEMINI_API_KEY=your_gemini_api_key
GEMINI_MODEL=gemini-3.1-flash-lite
```

---

## Running the Application

### Option 1: Startup script (Windows)

Run:

```cmd
run.bat
```

### Option 2: Manual start

Terminal 1 (Backend):

```bash
uvicorn main:app --reload --port 8000
```

FastAPI docs are available at `http://localhost:8000/docs`.

Terminal 2 (Frontend):

```bash
streamlit run frontend/app.py
```

Streamlit UI is available at `http://localhost:8501`.

---

## API Endpoints

- `GET /api/health`: Health check and model status
- `POST /api/meetings/upload`: Upload audio file (form-data: `file`) or transcript text (form-data: `transcript_text`)
- `GET /api/meetings`: List all processed meetings
- `GET /api/meetings/{id}`: Get meeting metadata, transcript, and structured analysis
- `POST /api/meetings/{id}/query`: Query a meeting with natural language (body: `{"query": "..."}`)
- `DELETE /api/meetings/{id}`: Delete a meeting and its queries

Example query request:

```bash
curl -X POST "http://localhost:8000/api/meetings/1/query" \
  -H "Content-Type: application/json" \
  -d "{\"query\": \"What tasks were assigned to Rahul?\"}"
```

---

## Speech-to-Text and Model Choice

- Model: `gemini-3.1-flash-lite`
- Gemini processes audio natively, removing the need for external speech-to-text binaries or heavy local models.
- The model performs transcription and speaker attribution in a single request, followed by structured extraction using JSON schema validation.

---

## Bonus Features

1. Video Input Support: Accepts video recordings (MP4, MOV, WEBM) as well as standard audio formats.
2. Speaker Diarization: Verbatim transcription with speaker turns identified.
3. Confidence Scores: Extraction certainty scores generated for action items and overall meeting analysis.
4. Duplicate Detection: Automatic deduplication of identical or overlapping action items.
5. Deadline Normalization: Converts relative/spoken dates into standard YYYY-MM-DD format and flags overdue tasks.
6. Automated Evaluation: One-click evaluation against predefined test questions in the UI and automated test suites.
7. Vector Database and Semantic Retrieval: Transcripts are chunked and embedded via Gemini embeddings with cosine similarity search using NumPy, stored locally in SQLite with zero external database configuration.

---

## Testing

Run pipeline test:

```bash
python scripts/test_pipeline.py
```

Run REST API test:

```bash
python scripts/test_api.py
```
