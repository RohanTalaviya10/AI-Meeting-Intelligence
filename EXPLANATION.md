# Engineering Notes: Design and Technical Decisions

This note explains why I picked specific tools, how I handled prompts and validation, and where the current system has limits.

---

## 1. Speech-to-Text Choice

For converting speech to text, I went with Gemini's native multimodal audio ingestion instead of setting up a local Whisper model or an external STT service.

Here is why:
- Running Whisper locally sounds good in theory, but in practice it forces anyone testing the code to download large model weights (1 to 3 GB), install FFmpeg, and often run into CUDA or C++ compiler headaches on Windows.
- Services like AssemblyAI or Deepgram work well, but they require setting up extra accounts, credentials, and billing.
- Gemini Flash takes audio formats (.wav, .mp3, .m4a) directly through the API.
- The biggest win was speaker diarization. By letting Gemini transcribe the audio natively, it tags speaker turns (like "Manager:", "Rahul:", "Priya:") directly in the transcript without needing a heavy second pipeline like pyannote.audio.

---

## 2. AI and Model Choice

I picked `gemini-3.1-flash-lite` (with `gemini-2.5-flash` as fallback).

Why Flash instead of a larger model like Pro:
- Speed and latency: Meeting audio files can be long. Flash generates responses significantly faster, which keeps the UI responsive.
- Cost: Flash is much cheaper per token while still being reliable enough for structured JSON extraction.
- Context window: Flash has a 1 million token context window. Even a two-hour meeting transcript takes less than 30,000 words, so the whole conversation easily fits into context without needing aggressive truncation.

For semantic search and vector retrieval, I used Gemini's `text-embedding-004` to convert text chunks into 768-dimensional vectors, and calculated cosine similarity using standard NumPy. This avoided having to install heavy vector database servers.

---

## 3. Prompt Strategy

Instead of throwing the audio at the model and asking for everything in one massive prompt, I split the work into clear stages. Doing transcription, speaker identification, summary, and action item extraction in a single prompt usually leads to missed deadlines or made-up details.

Here is how I structured the prompts:

1. Stage 1 (Transcription):
A single-purpose prompt that tells the model to transcribe the audio verbatim and label speakers cleanly with their names or titles.

2. Stage 2 (Structured Extraction):
I gave the model strict definitions for each category:
- Decisions: Only count things where people actually agreed on a final outcome. General discussion or ideas thrown around are explicitly ignored.
- Action items: Extract concrete tasks along with the person responsible, the stated deadline, and a priority level.
- Risks and blockers: Focus on technical dependencies or missing access that actively stops someone from getting work done (for example, waiting on credentials).
- Unresolved items: Flag topics that were explicitly pushed to the next meeting or left open (like pricing).

3. Stage 3 (Q&A with RAG):
When a user asks a question in the UI, the system first finds the top 3 most relevant transcript chunks using vector similarity. Then it feeds those chunks along with the summary into the prompt. This forces the model to answer directly from the transcript context rather than guessing or making things up.

---

## 4. Validation and Edge Cases

Language models can return messy formatting or hallucinated values if you do not guard against them. Here is how I handled validation:

- Schema validation with Pydantic:
The API uses Pydantic models (like `MeetingAnalysis` and `ActionItem`). If the model output is missing a field or returns unexpected JSON structure, the code parses and sanitizes it before saving to the database.

- Action item deduplication:
In meetings, people often repeat the same task multiple times across different sentences. To avoid cluttering the dashboard with duplicate cards, the backend has a deduplication step that groups identical tasks.

- Deadline normalization:
People in meetings say dates like "tomorrow", "today", or "by 10 September". The code converts these into standard ISO dates (YYYY-MM-DD) and checks whether the deadline has already passed, marking it as overdue if needed.

- Offline and fallback mode:
If someone tests the project without an API key, the backend does not crash. It falls back to deterministic vector calculations and sample meeting data so they can click through the UI and see how the pipeline behaves.

---

## 5. Current Limitations and Trade-offs

To keep the project clean, honest, and easy to run on any machine, I made a few trade-offs:

- Diarization without voice profiles:
Gemini guesses speaker labels based on voice pitch and conversational flow. In a 2-person or 3-person call, it works well. But in a crowded meeting where 5 people talk over each other, speaker attribution can occasionally get mixed up.

- Processing time for large files:
Uploading a 30-minute audio file over a home internet connection can take 15 to 30 seconds just to transfer, and Gemini takes another 20 to 30 seconds to parse the audio. I increased the client timeouts to handle this, but for true production use, a background job queue with websockets or progress bars would be better.

- SQLite concurrency:
I used SQLite because it requires zero installation or database setup on another PC. I enabled WAL mode to prevent locking during reads, but SQLite is still a single-file database. A production multi-tenant SaaS with hundreds of teams uploading at the same time would need PostgreSQL and Celery or Redis.

- Relative dates:
If an audio recording has no metadata saying when it was recorded, a phrase like "tomorrow" is calculated relative to the day the file was processed.
