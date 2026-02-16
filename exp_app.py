import json
from datetime import datetime
import os
import streamlit as st
import random
from supabase import create_client
from utils import Q_HIVAU, Q_SeQA, AB_CRITERIA, format_ab_round


st.set_page_config(page_title="User Study", layout="wide")

@st.cache_resource
def get_supabase():
    return create_client(st.secrets["SUPABASE_URL"],
                         st.secrets["SUPABASE_KEY"])


# -------------------------------
# 초기 세션 설정
# -------------------------------

if "username" not in st.session_state:
    st.session_state.username = ""

if "result_path" not in st.session_state:
    st.session_state.result_path = None

if "stage" not in st.session_state:
    st.session_state.stage = "start" # stages: start -> exp_intro -> explanation -> ab_intro -> ab_test -> mos_intro -> mos_test -> done

if "ab_round" not in st.session_state:
    st.session_state.ab_round = 0

if "ab_round_data" not in st.session_state:
    st.session_state.ab_round_data = []  # 각 round의 질문 세트 저장

if "ab_used_hivau" not in st.session_state:
    st.session_state.ab_used_hivau = {cat: set() for cat in Q_HIVAU}

if "ab_used_seqa" not in st.session_state:
    st.session_state.ab_used_seqa = {cat: set() for cat in Q_SeQA}

if "ab_choices" not in st.session_state:
    st.session_state.ab_choices = {}  # round별 선택 저장

if "ab_results" not in st.session_state:
    st.session_state.ab_results = []

if "mos_index" not in st.session_state:
    st.session_state.mos_index = 0

if "mos_questions" not in st.session_state:
    # Ours 내부 평가용: Anomaly + Surveillance
    anomaly = Q_SeQA["Anomaly"]
    surveillance = Q_SeQA["Surveillance"]
    merged = [("Anomaly", q) for q in anomaly] + \
             [("Surveillance", q) for q in surveillance]
    random.shuffle(merged)
    st.session_state.mos_questions = merged

if "mos_results" not in st.session_state:
    st.session_state.mos_results = []


# -------------------------------
# 메인 설명 페이지
# -------------------------------
if st.session_state.stage == "start":
    st.title("User Study")

    st.session_state.username = st.text_input("Username을 입력하세요")

    st.markdown("""
                수집된 username은 개인 식별의 용도로 사용되지 않습니다.
                실험의 예상 소요 시간은 약 10분입니다.   
                """)

    if st.button("실험 시작"):

        if st.session_state.username.strip() == "":
            st.error("Username을 입력해주세요.")
            st.stop()

        today = datetime.now().strftime("%y%m%d_%H%M%S")
        st.session_state.username = f"{today}_{st.session_state.username}"
        st.session_state.stage = "exp_intro"
        st.rerun()


if st.session_state.stage == "exp_intro":
    st.title("실험 소개")

    st.markdown("""
                본 실험은 보안 관제 상황에서 QA 세트의 업무 보조 효과를 평가하기 위한 사용자 실험입니다. 
                본 실험은 보안 관제사가 LLM을 활용하여 CCTV 영상을 분석하기 위해 질의를 입력하는 상황을 가정하며,
                참여자는 제시된 질문이 CCTV 영상과 함께 입력될 때 실제 보안 관제 업무 수행에 얼마나 도움이 되는지 평가합니다.
                실험 시 모든 질문은 영어로 제시되며, 괄호로 제공되는 한국어 번역은 참고용임을 인지해 주시길 바랍니다.
                """)

    st.markdown("")  
    st.markdown("""
                실험은 총 2단계로 구성됩니다.  
                1. A/B 테스트: 두 질문 세트 중 어느 세트가 보안 관제 업무 수행에 더 도움이 되는지를 선택하는 단계입니다. 총 3라운드로 진행됩니다.  
                2. MOS 평가: 각 개별 질문이 보안 관제 업무와 얼마나 관련성이 높은지를 5점 척도로 평가합니다. 총 27개의 항목이 제시됩니다.
                """)

    
    st.markdown("") 
    st.markdown("""
                본 실험에서는 참가자가 보안 관제사의 역할을 가정하고, 제시된 질문 세트가 위와 같은 업무 수행 과정에 얼마나 실질적으로 기여하는지를 평가하게 됩니다. 
                평가 시 단순한 문장 표현의 자연스러움보다는, 실제 관제 업무의 의사결정 보조 효과를 기준으로 판단해 주시기 바랍니다.
                본 내용은 각 단계 실험 시작 전 다시 확인할 수 있습니다.

                보안 관제 업무는 다음과 같은 단계로 구성됩니다.

                1. 영상 모니터링 (Continuous Monitoring)
                CCTV 영상 및 관련 데이터를 실시간으로 관찰하여 이상 행동, 비정상 사건, 잠재적 위험 신호를 탐지합니다.

                2. 상황 판단 (Threat Assessment)
                탐지된 이벤트가 실제 보안 위협인지 평가하며, 오경보(False Alarm)를 배제하기 위한 추가 분석을 수행합니다.

                3. 대응 조치 (Incident Response)
                위협으로 판단될 경우, 출동 요청, 원격 확인, 추가 정보 수집 등 적절한 대응을 수행합니다.

                4. 보고 및 기록 (Reporting and Logging)
                사건 발생 경위와 판단 근거, 대응 결과를 기록하여 사후 분석 및 향후 대응 전략 개선에 활용합니다.

                """)

    if st.button("A/B 테스트로 이동"):
        st.session_state.stage = "ab_intro"
        st.rerun()


# -------------------------------
# A/B 테스트 (3 round)
# -------------------------------


if st.session_state.stage == "ab_intro":
    st.title("A/B 테스트")

    st.markdown("""
                본 실험은 두 데이터세트의 질문 세트 중 어떤 질문 세트가 보안 관제사의 의사결정에 더 도움이 되는지를 평가하기 위한 실험입니다.
                이 단계에서는 두 개의 질문 세트(Set A, Set B)가 제시되며, 실험은 총 3라운드로 진행됩니다. 
                3번째 라운드에서 ‘다음’ 버튼을 누르면 즉시 MOS 평가 설명 페이지로 이동하며, 이후에는 A/B 테스트의 이전 라운드로 돌아갈 수 없습니다.
                """)

    st.markdown("") 
    st.markdown("""
                보안 관제 업무는 다음과 같은 단계로 구성됩니다.

                1. 영상 모니터링 (Continuous Monitoring)
                CCTV 영상 및 관련 데이터를 실시간으로 관찰하여 이상 행동, 비정상 사건, 잠재적 위험 신호를 탐지합니다.

                2. 상황 판단 (Threat Assessment)
                탐지된 이벤트가 실제 보안 위협인지 평가하며, 오경보(False Alarm)를 배제하기 위한 추가 분석을 수행합니다.

                3. 대응 조치 (Incident Response)
                위협으로 판단될 경우, 출동 요청, 원격 확인, 추가 정보 수집 등 적절한 대응을 수행합니다.

                4. 보고 및 기록 (Reporting and Logging)
                사건 발생 경위와 판단 근거, 대응 결과를 기록하여 사후 분석 및 향후 대응 전략 개선에 활용합니다.

                """)

    if st.button("실험 시작"):
        st.session_state.stage = "ab_test"
        st.rerun()


elif st.session_state.stage == "ab_test":

    st.title(f"A/B 테스트 (Round {st.session_state.ab_round + 1} / 3)")

    if st.session_state.ab_round >= 3:
        st.session_state.stage = "mos_intro"
        st.rerun()

    # 이미 생성된 round인지 확인
    if st.session_state.ab_round < len(st.session_state.ab_round_data):
        round_data = st.session_state.ab_round_data[st.session_state.ab_round]
    else:
        # ---- 새로 생성 ----
        hivau_sample = []
        for cat in Q_HIVAU:
            candidates = list(set(Q_HIVAU[cat]) - st.session_state.ab_used_hivau[cat])
            q = random.choice(candidates)
            hivau_sample.append((cat, q))
            st.session_state.ab_used_hivau[cat].add(q)

        seqa_sample = []
        for cat in Q_SeQA:
            candidates = list(set(Q_SeQA[cat]) - st.session_state.ab_used_seqa[cat])
            q = random.choice(candidates)
            seqa_sample.append((cat, q))
            st.session_state.ab_used_seqa[cat].add(q)

        if random.random() > 0.5:
            round_data = {
                "A": ("HIVAU", hivau_sample),
                "B": ("SeQA", seqa_sample)
            }
        else:
            round_data = {
                "A": ("SeQA", seqa_sample),
                "B": ("HIVAU", hivau_sample)
            }

        st.session_state.ab_round_data.append(round_data)

    A_label, A_set = round_data["A"]
    B_label, B_set = round_data["B"]

    # ---------------- question sets 출력 ----------------
    col_left, col_right = st.columns(2)
    with col_left:
        st.subheader("Set A")
        for _, q in A_set:
            st.markdown(f"- {q}")
    with col_right:
        st.subheader("Set B")
        for _, q in B_set:
            st.markdown(f"- {q}")

    # ---------------- 선택 UI ----------------
    _, col_center, _ = st.columns([1, 2, 1])
    with col_center:
        round_idx = st.session_state.ab_round
        st.markdown("---")

        default_choices = st.session_state.ab_choices.get(round_idx, {})
        choices = {}

        for i, criterion in enumerate(AB_CRITERIA):
            key = f"ab_choice_{round_idx}_{i}"

            default_value = default_choices.get(i)

            selection = st.radio(
                criterion,
                ["A", "B"],
                index=None if default_value is None else ["A", "B"].index(default_value),
                horizontal=True,
                key=key
            )

            choices[i] = selection

    # ---------------- 버튼 UI ----------------
    col_left, col_right = st.columns([4, 1])
    
    with col_left:
        if st.session_state.ab_round > 0:
            if st.button("이전"):
                st.session_state.ab_round -= 1
                st.rerun()

    with col_right:
        if st.button("다음"):

            # 선택 안 한 기준 찾기
            unanswered = [i+1 for i in range(len(AB_CRITERIA)) if choices[i] is None]

            if unanswered:
                st.error(f"다음 기준이 선택되지 않았습니다: {unanswered}")
                st.stop()

            # 선택 저장
            st.session_state.ab_choices[round_idx] = choices

            formatted = format_ab_round(round_data, choices)

            if round_idx >= len(st.session_state.ab_results):
                st.session_state.ab_results.append(formatted)
            else:
                st.session_state.ab_results[round_idx] = formatted

            st.session_state.ab_round += 1
            st.rerun()




# -------------------------------
# 5점 척도 MOS 평가
# -------------------------------

elif st.session_state.stage == "mos_intro":
    st.title("MOS 평가 소개")

    st.markdown("""
                이 단계에서는 각 개별 질문이 보안 관제 업무와 얼마나 관련성이 높은지를 5점 척도로 평가합니다.
                """)
    
    st.markdown("") 
    st.markdown("""
                평가 기준은 다음과 같습니다.
                - 1점: 전혀 관련 없음
                - 2점: 거의 관련 없음
                - 3점: 보통 수준의 관련성
                - 4점: 높은 관련 있음
                - 5점: 매우 높은 관련 있음
                """)

    
    st.markdown("") 
    st.markdown("""
                보안 관제 업무는 다음과 같은 단계로 구성됩니다.

                1. 영상 모니터링 (Continuous Monitoring)
                CCTV 영상 및 관련 데이터를 실시간으로 관찰하여 이상 행동, 비정상 사건, 잠재적 위험 신호를 탐지합니다.

                2. 상황 판단 (Threat Assessment)
                탐지된 이벤트가 실제 보안 위협인지 평가하며, 오경보(False Alarm)를 배제하기 위한 추가 분석을 수행합니다.

                3. 대응 조치 (Incident Response)
                위협으로 판단될 경우, 출동 요청, 원격 확인, 추가 정보 수집 등 적절한 대응을 수행합니다.

                4. 보고 및 기록 (Reporting and Logging)
                사건 발생 경위와 판단 근거, 대응 결과를 기록하여 사후 분석 및 향후 대응 전략 개선에 활용합니다.

                """)
    
    if st.button("실험 시작"):
        st.session_state.stage = "mos_test"
        st.rerun()


elif st.session_state.stage == "mos_test":

    st.title("5점 척도 평가")

    st.markdown("""
    아래 질문들이 보안 관제사의 업무와 얼마나 관련성이 높다고 생각하십니까?
    각 문항에 대해 **1점(전혀 관련 없음) ~ 5점(매우 관련 있음)** 중 선택해주세요.
    """)

    questions = st.session_state.mos_questions

    responses = {}

    # -------------------------------
    # 모든 질문 한 번에 출력
    # -------------------------------
    for idx, (category, question) in enumerate(questions):

        st.markdown(f"---")
        st.markdown(f"{idx+1}. {question}")
        
        score = st.radio(
            label="점수 선택",
            options=[1, 2, 3, 4, 5],
            horizontal=True,
            index=None,
            key=f"mos_full_{idx}"
        )

        responses[idx] = {
            "category": category,
            "question": question,
            "score": score
        }

    st.markdown("---")

    # -------------------------------
    # 제출 버튼
    # -------------------------------
    if st.button("제출하기"):

        for item in responses.values():
            if item["score"] is None:
                st.error(f"응답하지 않은 문항이 있습니다. 모든 문항에 응답해야 합니다.")
                st.stop()

        # 모든 문항 응답 완료
        st.session_state.mos_results = list(responses.values())
        st.session_state.stage = "done"
        st.rerun()



# -------------------------------
# 종료 페이지
# -------------------------------
elif st.session_state.stage == "done":

    st.title("실험이 완료되었습니다.")
    st.write("참여해주셔서 감사합니다.")

    final_output = {
        "ab_test": st.session_state.ab_results,
        "mos": st.session_state.mos_results
    }

    if "uploaded" not in st.session_state:
        supabase = get_supabase()
        response = supabase.table("user_study_results").insert({
            "participant_id": st.session_state.username,
            "data": final_output
        }).execute()

        if response.data:
            st.success("결과가 저장되었습니다.")
            st.session_state.uploaded = True
        else:
            st.error("저장 실패")
    else:
        st.success("결과가 이미 저장되었습니다.")
