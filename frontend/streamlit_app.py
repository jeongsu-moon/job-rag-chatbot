import os

import requests
import streamlit as st

API_URL = os.getenv("API_URL", "http://localhost:8000")

st.set_page_config(page_title="채용 공고 RAG 챗봇", page_icon="💼", layout="wide")

# ── 사이드바 ──
with st.sidebar:
    st.header("설정")

    # 서버 상태 표시
    try:
        health = requests.get(f"{API_URL}/api/health", timeout=5).json()
        st.success(f"서버 연결됨")
        st.metric("LLM 모드", health["llm_mode"].upper())
        st.metric("총 문서 수", health["total_documents"])
    except Exception:
        st.error("서버에 연결할 수 없습니다. FastAPI 서버를 먼저 실행해주세요.")
        health = None

    st.divider()
    st.subheader("검색 설정")
    top_k = st.slider("검색 결과 수 (top_k)", min_value=1, max_value=10, value=5)
    use_reranker = st.toggle("Reranker 사용", value=True)

    st.divider()
    if st.button("대화 초기화", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

# ── 메인 영역 ──
st.title("💼 채용 공고 RAG 챗봇")
st.caption("채용 공고 데이터를 기반으로 질문에 답변합니다.")

# 세션 상태 초기화
if "messages" not in st.session_state:
    st.session_state.messages = []

# 예시 질문 버튼
if not st.session_state.messages:
    st.markdown("**예시 질문을 선택하거나 직접 입력하세요:**")
    examples = [
        "Python 백엔드 주니어 채용 공고 알려줘",
        "AI 엔지니어에게 요구하는 기술 스택은?",
        "DevOps 엔지니어 채용 조건을 비교해줘",
        "FastAPI 경험을 요구하는 회사는?",
    ]
    cols = st.columns(2)
    for i, example in enumerate(examples):
        if cols[i % 2].button(example, key=f"example_{i}", use_container_width=True):
            st.session_state.messages.append({"role": "user", "content": example})
            st.rerun()

# 대화 기록 표시
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg.get("sources"):
            with st.expander("참조 문서"):
                for s in msg["sources"]:
                    score = s.get("relevance_score")
                    score_text = f" (관련도: {score})" if score else ""
                    st.markdown(f"- **{s['company']}** - {s['title']}{score_text}")

# 사용자 입력 처리
if prompt := st.chat_input("채용 공고에 대해 질문하세요"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

# 마지막 메시지가 user이면 응답 생성
if st.session_state.messages and st.session_state.messages[-1]["role"] == "user":
    with st.chat_message("assistant"):
        with st.spinner("답변 생성 중..."):
            try:
                response = requests.post(
                    f"{API_URL}/api/query",
                    json={
                        "question": st.session_state.messages[-1]["content"],
                        "top_k": top_k,
                        "use_reranker": use_reranker,
                    },
                    timeout=60,
                )
                response.raise_for_status()
                data = response.json()
                answer = data["answer"]
                sources = data.get("sources", [])
                processing_time = data.get("processing_time", 0)

                st.markdown(answer)
                if sources:
                    with st.expander("참조 문서"):
                        for s in sources:
                            score = s.get("relevance_score")
                            score_text = f" (관련도: {score})" if score else ""
                            st.markdown(f"- **{s['company']}** - {s['title']}{score_text}")
                st.caption(f"응답 시간: {processing_time}초")

            except requests.ConnectionError:
                answer = "FastAPI 서버에 연결할 수 없습니다. `python -m app.main`으로 서버를 먼저 실행해주세요."
                sources = []
                st.error(answer)
            except Exception as e:
                answer = f"오류가 발생했습니다: {e}"
                sources = []
                st.error(answer)

        st.session_state.messages.append({
            "role": "assistant",
            "content": answer,
            "sources": sources,
        })
