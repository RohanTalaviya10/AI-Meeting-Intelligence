import os
import json
import socket
import threading
import time
from pathlib import Path
import requests
import streamlit as st
import uvicorn

st.set_page_config(
    page_title="AI Meeting Intelligence",
    layout="wide",
    initial_sidebar_state="expanded"
)


def is_backend_running(host: str = "127.0.0.1", port: int = 8000) -> bool:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.5)
            return s.connect_ex((host, port)) == 0
    except Exception:
        return False


def start_backend():
    from backend.main import app as fastapi_app
    uvicorn.run(fastapi_app, host="127.0.0.1", port=8000, log_level="warning")


if not is_backend_running():
    server_thread = threading.Thread(target=start_backend, daemon=True)
    server_thread.start()
    for _ in range(30):
        if is_backend_running():
            break
        time.sleep(0.1)

BACKEND_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8000")


def check_backend_health():
    try:
        resp = requests.get(f"{BACKEND_URL}/api/health", timeout=10)
        return resp.status_code == 200, resp.json()
    except Exception:
        return False, {}


def get_meetings_list():
    try:
        resp = requests.get(f"{BACKEND_URL}/api/meetings", timeout=30)
        if resp.status_code == 200:
            return resp.json()
    except Exception:
        pass
    return []


def get_meeting_details(meeting_id):
    try:
        resp = requests.get(f"{BACKEND_URL}/api/meetings/{meeting_id}", timeout=30)
        if resp.status_code == 200:
            return resp.json()
    except Exception as e:
        st.error(f"Error fetching meeting: {e}")
    return None


def delete_meeting(meeting_id):
    try:
        resp = requests.delete(f"{BACKEND_URL}/api/meetings/{meeting_id}", timeout=30)
        return resp.status_code == 200
    except Exception:
        return False


with st.sidebar:
    st.title("Meeting Agent")
    st.caption("Meeting Intelligence and Action Tracker")

    is_alive, health_data = check_backend_health()
    if is_alive:
        st.success(f"Backend Connected ({health_data.get('model', 'gemini-3.1-flash-lite')})")
    else:
        st.error("Backend Disconnected (Port 8000)")

    st.markdown("---")
    st.subheader("Configuration")
    
    user_api_key = st.text_input(
        "Gemini API Key",
        value=os.getenv("GEMINI_API_KEY", ""),
        type="password"
    )

    st.markdown("---")
    st.subheader("Meeting History")
    
    meetings = get_meetings_list()
    selected_meeting_id = None

    if meetings:
        meeting_options = {f"ID {m['id']} - {m['filename']} ({m['created_at'][:16]})": m['id'] for m in meetings}
        chosen_label = st.selectbox("Select Meeting", list(meeting_options.keys()))
        selected_meeting_id = meeting_options[chosen_label]
        
        col_view, col_del = st.columns([2, 1])
        with col_view:
            if st.button("Refresh List", use_container_width=True):
                st.rerun()
        with col_del:
            if st.button("Delete", use_container_width=True):
                if delete_meeting(selected_meeting_id):
                    st.success("Deleted.")
                    st.rerun()
                else:
                    st.error("Delete failed.")
    else:
        st.info("No meetings recorded yet.")


st.title("AI Meeting Intelligence and Action Tracker")
st.caption("Transcribe meeting recordings, extract decisions, action items, risks, and query conversations with Gemini 3.1 Flash-Lite.")

tab_process, tab_intelligence, tab_query = st.tabs([
    "1. Upload and Process",
    "2. Intelligence Dashboard",
    "3. Questions and Answers"
])

with tab_process:
    st.subheader("Process Meeting")
    
    input_mode = st.radio(
        "Input Mode:",
        ["Audio or Video Recording", "Paste Transcript"],
        horizontal=True
    )

    upload_file_obj = None
    transcript_text_val = None

    if input_mode == "Audio or Video Recording":
        uploaded_file = st.file_uploader(
            "Upload audio or video recording:",
            type=["mp3", "wav", "m4a", "ogg", "flac", "mp4", "mov", "webm"]
        )
        if uploaded_file:
            upload_file_obj = uploaded_file
            ext = Path(uploaded_file.name).suffix.lower()
            if ext in [".mp4", ".mov", ".webm"]:
                st.video(uploaded_file)
            else:
                st.audio(uploaded_file)
            st.caption(f"{uploaded_file.name} ({uploaded_file.size / 1024:.1f} KB)")

    else:
        transcript_text_val = st.text_area(
            "Transcript Text:",
            placeholder="Paste conversation transcript here...",
            height=200
        )

    st.markdown("---")
    if st.button("Process Meeting", type="primary", use_container_width=True):
        if not is_alive:
            st.error("Backend server is not running on port 8000.")
        else:
            headers = {}
            if user_api_key:
                headers["x-gemini-api-key"] = user_api_key

            with st.spinner("Processing recording and extracting structured analysis..."):
                try:
                    if input_mode == "Audio or Video Recording":
                        if not upload_file_obj:
                            st.warning("Please upload an audio or video file.")
                            st.stop()
                        files = {"file": (upload_file_obj.name, upload_file_obj.getvalue(), upload_file_obj.type or "application/octet-stream")}
                        response = requests.post(f"{BACKEND_URL}/api/meetings/upload", files=files, headers=headers, timeout=900)

                    else:
                        if not transcript_text_val or not transcript_text_val.strip():
                            st.warning("Please enter transcript text.")
                            st.stop()
                        data = {"transcript_text": transcript_text_val.strip()}
                        response = requests.post(f"{BACKEND_URL}/api/meetings/upload", data=data, headers=headers, timeout=900)

                    if response.status_code in [200, 201]:
                        res_data = response.json()
                        st.session_state["current_meeting"] = res_data
                        st.success(f"Meeting {res_data['id']} processed successfully.")
                    else:
                        detail = response.json().get("detail", response.text)
                        st.error(f"Processing failed: {detail}")

                except Exception as e:
                    st.error(f"Request failed: {str(e)}")

active_meeting = None
if selected_meeting_id:
    active_meeting = get_meeting_details(selected_meeting_id)
elif "current_meeting" in st.session_state:
    active_meeting = st.session_state["current_meeting"]
elif meetings:
    active_meeting = get_meeting_details(meetings[0]["id"])

with tab_intelligence:
    if not active_meeting:
        st.info("No meeting selected. Upload a recording or select one from the sidebar.")
    else:
        analysis = active_meeting.get("analysis", {})
        
        col_m1, col_m2, col_m3, col_m4 = st.columns([3, 1, 1, 1])
        with col_m1:
            st.subheader(f"Meeting {active_meeting['id']}: {active_meeting['filename']}")
        with col_m2:
            st.caption(f"Date: {active_meeting.get('created_at', '')[:16]}")
        with col_m3:
            st.caption(f"Size: {active_meeting.get('file_size_bytes', 0) / 1024:.1f} KB")
        with col_m4:
            st.caption(f"Confidence: {int(analysis.get('confidence_score', 0.95) * 100)}%")

        participants = analysis.get("participants", [])
        if participants:
            st.write("**Participants:** " + ", ".join(participants))

        st.markdown("---")

        st.subheader("Executive Summary")
        summary_text = analysis.get("summary", "No summary.")
        st.info(summary_text)

        st.subheader("Confirmed Decisions")
        decisions = analysis.get("decisions", [])
        if decisions:
            for d in decisions:
                st.success(d)
        else:
            st.write("No confirmed decisions recorded.")

        st.subheader("Action Items Tracker")
        action_items = analysis.get("action_items", [])
        if action_items:
            for i, act in enumerate(action_items, 1):
                with st.container(border=True):
                    col_task, col_meta = st.columns([3, 2])
                    with col_task:
                        st.markdown(f"**{i}. {act.get('task', '')}**")
                    with col_meta:
                        meta_items = [
                            f"Priority: {act.get('priority', 'Medium')}",
                            f"Status: {act.get('status', 'Pending')}",
                            f"Confidence: {int(act.get('confidence', 0.9) * 100)}%"
                        ]
                        if act.get("is_overdue"):
                            meta_items.append("Overdue")
                        st.caption(" | ".join(meta_items))

                    details = [
                        f"Assignee: **{act.get('assignee') or 'Unassigned'}**",
                        f"Deadline: **{act.get('deadline') or 'None'}**"
                    ]
                    if act.get("normalized_deadline"):
                        details.append(f"Standard Date: **{act.get('normalized_deadline')}**")
                    st.write(" · ".join(details))
        else:
            st.write("No action items extracted.")

        col_risk, col_unres = st.columns(2)
        with col_risk:
            st.subheader("Risks and Blockers")
            risks = analysis.get("risks_blockers", [])
            if risks:
                for r in risks:
                    st.error(r)
            else:
                st.write("None identified.")

        with col_unres:
            st.subheader("Unresolved Items")
            unresolved = analysis.get("unresolved_items", [])
            if unresolved:
                for u in unresolved:
                    st.warning(u)
            else:
                st.write("None identified.")

        with st.expander("View Full Verbatim Transcript"):
            st.text_area("Transcript", active_meeting.get("transcript", ""), height=250, disabled=True)

        st.markdown("---")
        col_dl1, col_dl2 = st.columns(2)
        with col_dl1:
            st.download_button(
                label="Download JSON",
                data=json.dumps(analysis, indent=2),
                file_name=f"meeting_{active_meeting['id']}_analysis.json",
                mime="application/json",
                use_container_width=True
            )
        with col_dl2:
            st.download_button(
                label="Download Transcript Text",
                data=active_meeting.get("transcript", ""),
                file_name=f"meeting_{active_meeting['id']}_transcript.txt",
                mime="text/plain",
                use_container_width=True
            )

with tab_query:
    if not active_meeting:
        st.info("Please select or process a meeting first.")
    else:
        st.subheader(f"Query Meeting {active_meeting['id']}")
        st.caption("Ask questions about tasks, deadlines, decisions, or open topics.")

        st.write("**Example Questions:**")
        preset_cols = st.columns(3)
        sample_questions = [
            "What tasks were assigned to Rahul?",
            "What are the deadlines?",
            "What decisions were finalized?",
            "What blockers are still open?",
            "Why is pricing still unresolved?",
            "What is the beta launch date?"
        ]

        preset_clicked = None
        for idx, q in enumerate(sample_questions):
            col = preset_cols[idx % 3]
            if col.button(q, key=f"preset_btn_{idx}", use_container_width=True):
                preset_clicked = q

        default_q = preset_clicked if preset_clicked else ""
        query_input = st.text_input("Question:", value=default_q, placeholder="What tasks were assigned to Rahul?")

        if st.button("Submit Question", type="primary") or preset_clicked:
            if not query_input.strip():
                st.warning("Please enter a question.")
            else:
                with st.spinner("Retrieving answer..."):
                    try:
                        headers = {}
                        if user_api_key:
                            headers["x-gemini-api-key"] = user_api_key

                        payload = {"query": query_input.strip()}
                        res = requests.post(
                            f"{BACKEND_URL}/api/meetings/{active_meeting['id']}/query",
                            json=payload,
                            headers=headers,
                            timeout=120
                        )

                        if res.status_code == 200:
                            q_resp = res.json()
                            st.subheader("Answer:")
                            st.info(q_resp.get("answer", ""))

                            retrieved = q_resp.get("retrieved_chunks", [])
                            if retrieved:
                                st.markdown("---")
                                st.subheader("Semantically Retrieved Context Chunks")
                                for rc in retrieved:
                                    with st.container(border=True):
                                        col_c1, col_c2 = st.columns([3, 1])
                                        with col_c1:
                                            st.markdown(f"**Speaker:** {rc.get('speaker', 'General')}")
                                        with col_c2:
                                            sim_val = int(rc.get("similarity", 0.0) * 100)
                                            st.caption(f"Relevance: {sim_val}%")
                                        st.write(rc.get("text", ""))
                        else:
                            st.error(f"Error: {res.text}")
                    except Exception as e:
                        st.error(f"Request failed: {str(e)}")
