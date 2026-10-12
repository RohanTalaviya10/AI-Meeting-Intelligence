import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.database import init_db, save_meeting, get_meeting
from backend.services import analyze_transcript, query_meeting

init_db()

sample_transcript = """
Manager: We need to finalize the beta launch by 15 September.
Rahul: I can complete the payment API integration by 10 September.
Priya: I will prepare the QA test cases by 12 September.
Manager: Rahul, please also investigate the timeout issue reported by the mobile team.
Rahul: I will check the timeout issue tomorrow.
Priya: The product pricing is still not finalized.
Manager: Let's discuss pricing in the next meeting. For now, the beta launch date remains 15 September.
Rahul: I also need access to the payment gateway test account.
Manager: I will provide that access today.
"""

analysis = analyze_transcript(sample_transcript)
meeting_id = save_meeting(
    filename="sample_meeting.wav",
    file_path="",
    file_size=320044,
    transcript=sample_transcript.strip(),
    analysis=analysis.model_dump()
)

saved_item = get_meeting(meeting_id)
assert saved_item is not None
assert len(saved_item["analysis"]["action_items"]) == 4

from backend.vector_store import index_transcript, search_similar_chunks

indexed_count = index_transcript(meeting_id, saved_item["transcript"])
assert indexed_count > 0

search_res = search_similar_chunks(meeting_id, "payment API integration", top_k=2)
assert len(search_res) > 0
assert any("payment" in r["text"].lower() for r in search_res)

ans1 = query_meeting(saved_item["transcript"], saved_item["analysis"], "What tasks were assigned to Rahul?")
assert "Rahul" in ans1

ans2 = query_meeting(saved_item["transcript"], saved_item["analysis"], "What are the deadlines?")
assert "10 September" in ans2

print("Pipeline tests passed.")

