import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from starlette.testclient import TestClient
from backend.main import app

client = TestClient(app)

res = client.get("/api/health")
assert res.status_code == 200

sample_transcript = """Manager: We need to finalize the beta launch by 15 September.
Rahul: I can complete the payment API integration by 10 September."""

res = client.post("/api/meetings/upload", data={"transcript_text": sample_transcript})
assert res.status_code == 201
meeting_id = res.json()["id"]

res = client.get("/api/meetings")
assert res.status_code == 200

res = client.get(f"/api/meetings/{meeting_id}")
assert res.status_code == 200

res = client.post(
    f"/api/meetings/{meeting_id}/query",
    json={"query": "What tasks were assigned to Rahul?"}
)
assert res.status_code == 200
assert "retrieved_chunks" in res.json()


res = client.delete(f"/api/meetings/{meeting_id}")
assert res.status_code == 200

print("API tests passed.")
