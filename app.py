# -*- coding: utf-8 -*-
"""
고민 난장회의 — Gradio 단일 앱
'고민난장회의_Gradio_수정사항_사양.md' 6개 수정사항 구현.

  (1) 인원 제한 없는 페르소나 다중 선택
  (2) 카카오톡 톤 말풍선 (페르소나별 개별 말풍선, 좌=페르소나 / 우=사용자)
  (3) 캐릭터 프로필 이미지 + 첫 글자 fallback
  (4) 입장 시퀀스 (초기 로딩 → 선택 → 단톡방 생성 로딩 → 한 명씩 입장)
  (5) 입력 중 응답 정지 / 전송 후 자동 응답
  (6) 말풍선 간격 1.4초 + "타이핑 중…" 인디케이터

화면 흐름:
  start → loading1 → select → loading2 → chat
"""

import time
import random
import gradio as gr

import tools
from tools import (
    PERSONAS, PERSONA_IDS, persona_name, avatar_for, user_avatar,
    generate_reply, parse_speakers, detect_mentions,
)
from llm import provider_info

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ---- 상수 (사양서 §6) ----
BUBBLE_INTERVAL_SEC = 1.4     # 말풍선 사이 고정 간격
TYPING_HINT_SEC = 0.5         # "타이핑 중…" 노출 시간 (1.4초 구간 내)
ENTER_INTERVAL_SEC = 0.7      # 입장 안내 한 명씩 간격
PAUSE_POLL_SEC = 0.3          # 입력 중 정지 상태 폴링 간격
PAUSE_MAX_WAIT = 120          # 정지 최대 대기 (안전장치)
MAX_AUTO_MSGS = 30            # 자동 대화 1세션 최대 발언 수 (비용/과열 방지; 유저 입력 시 즉시 중단)


# ===========================================================================
# 카카오톡 톤 커스텀 CSS
# ===========================================================================
CSS = """
/* ===== B급 감성 다크 테마 =====
   검은 배경 + 궁서체 + 형광색 폭격. 90년대 전단지/옛날 플래시게임 감성.
   진지함 금지, 촌스러울수록 정답. */
* { font-family: "Batang", "바탕", "BatangChe", "AppleMyungjo", "명조",
    "Nanum Myeongjo", "Apple SD Gothic Neo", serif !important; }

:root {
  --bg: #0a0a12;
  --neon-yellow: #FFEC00;
  --neon-pink: #FF00A0;
  --neon-cyan: #00F0FF;
  --neon-green: #39FF14;
  --blood: #C81212;
}

.gradio-container { max-width: 480px !important; margin: 0 auto !important;
  background: #0a0a12 !important; }
body, .gradio-container { background:
  radial-gradient(circle at 20% 10%, #1a0a2e 0%, #0a0a12 55%) !important; }
footer { display: none !important; }

/* ===== 채팅 영역 ===== */
#chatbox { background: #1a1626 !important; border: 1px solid #3a3450 !important;
  border-radius: 0 !important; box-shadow: none !important; }
#chatbox .message-row { padding: 1px 0 !important; margin: 6px 0 !important; }
#chatbox .message { border: none !important; box-shadow: none !important;
  background: transparent !important; padding: 0 !important; }
#chatbox .bubble-wrap { background: transparent !important; }

/* 내 메시지 컨테이너 — 배경 제거(내부 .utext가 실제 말풍선) */
#chatbox .message.user { background: transparent !important; border: none !important;
  box-shadow: none !important; padding: 0 !important; }

/* 내 이름+아바타 줄 (우측 정렬) */
#chatbox .uname { display: flex !important; align-items: center; gap: 6px; margin-bottom: 4px;
  justify-content: flex-end; font-size: 13px; color: #A89BC9 !important; font-weight: 700; }

/* 내 말풍선 — 차분한 노랑톤 + 검은 글씨 (우측) */
#chatbox .utext { background: #E8C84A !important; color: #1a1626 !important;
  border-radius: 14px; border-top-right-radius: 4px; padding: 9px 13px;
  font-size: 15px; line-height: 1.5; display: inline-block; max-width: 100%;
  font-weight: 600; box-shadow: 1px 2px 4px rgba(0,0,0,0.3); }
#chatbox .utext, #chatbox .utext * { color: #1a1626 !important; text-shadow: none !important; }

/* 캐릭터 말풍선 (좌측) — 밝은 배경 + 진한 글씨 (대비 확실히) */
#chatbox .ptext { background: #F5F1FA !important; color: #1a1626 !important;
  border: none !important;
  border-radius: 14px; border-top-left-radius: 4px; padding: 9px 13px;
  font-size: 15px; line-height: 1.55; display: inline-block; max-width: 100%;
  box-shadow: 1px 2px 4px rgba(0,0,0,0.3); }
/* 말풍선 안 자식 요소(p, span 등)까지 진한 글씨 강제 — 흰 글씨 덮어쓰기 방지 */
#chatbox .ptext, #chatbox .ptext * { color: #1a1626 !important; text-shadow: none !important; }

#chatbox .pname { display: flex; align-items: center; gap: 6px; margin-bottom: 4px;
  font-size: 13px; color: #A89BC9 !important; font-weight: 700;
  text-shadow: none !important; }

/* 시스템 안내 — 차분한 회보라 알약 */
#chatbox .sys-note { display: block; text-align: center; margin: 6px auto;
  background: rgba(168,155,201,0.15); color: #A89BC9 !important; font-size: 12px; font-weight: 600;
  padding: 5px 14px; border: none; border-radius: 99px;
  width: fit-content; max-width: 90%; text-shadow: none !important; }

/* ===== 시작 화면 ===== */
.center-wrap { display:flex; flex-direction:column; align-items:center; justify-content:center;
  min-height: 56vh; text-align:center; gap: 4px; padding: 14px; }
.hero-badge { font-size: 13px; font-weight: 800; letter-spacing: 1px; color: #000;
  background: var(--neon-green); padding: 4px 14px; border-radius: 0; margin-bottom: 16px;
  transform: rotate(-3deg); display: inline-block; border: 2px solid #000;
  box-shadow: 3px 3px 0 var(--blood); }
.hero-emoji { font-size: 52px; margin-bottom: 8px; transform: rotate(-7deg); display:inline-block;
  filter: drop-shadow(0 0 12px var(--neon-pink)); }
.hero-title { font-size: 33px; font-weight: 900; line-height: 1.3; color: var(--neon-yellow);
  letter-spacing: 0px; text-shadow: 3px 3px 0 var(--neon-pink), 0 0 18px rgba(255,236,0,0.5); }
.hero-title .pop { color: var(--neon-cyan); text-shadow: 3px 3px 0 var(--blood),
  0 0 18px rgba(0,240,255,0.6); white-space: nowrap; }
.hero-sub { color: var(--neon-cyan); font-size: 13.5px; line-height:1.7; margin-top: 14px;
  text-shadow: 0 0 8px rgba(0,240,255,0.4); }

/* ===== 페르소나 선택 — 카드형 ===== */
.sel-head { padding: 18px 18px 4px; }
.sel-title { font-size: 24px; font-weight: 900; color: var(--neon-yellow);
  text-shadow: 2px 2px 0 var(--neon-pink); }
.sel-sub { color: var(--neon-cyan); font-size: 12.5px; margin-top: 4px; }

/* ===== 프로필 카드 그리드 (보기용) ===== */
.pcard-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px;
  padding: 6px 14px 2px; }
.pcard { position: relative; display: flex; flex-direction: column; align-items: center;
  gap: 6px; background: #1c1430; border: 2px solid #3a3450; border-radius: 12px;
  padding: 12px 6px 10px; user-select: none;
  transition: border-color 120ms ease, box-shadow 120ms ease; }
.pcard-img { width: 62px; height: 62px; border-radius: 50%; object-fit: cover;
  border: 2px solid #4a4060; }
.pcard-name { font-size: 11.5px; font-weight: 800; color: #ECE8F5; text-align: center;
  line-height: 1.2; height: 28px; display: flex; align-items: center;
  justify-content: center; }
/* 긴 이름(이희창 등)은 글씨를 살짝 줄여 2줄에 맞춤 */
.pcard-name.long { font-size: 10px; }
.pcard-check { position: absolute; top: 6px; right: 6px; width: 20px; height: 20px;
  border-radius: 50%; background: var(--neon-pink); color: #fff; font-size: 12px;
  font-weight: 900; display: flex; align-items: center; justify-content: center;
  opacity: 0; transform: scale(0.5); transition: all 120ms ease; }
/* 선택된 카드 */
.pcard.sel { border-color: var(--neon-yellow); background: #2e2410;
  box-shadow: 0 0 0 1px var(--neon-yellow), 3px 4px 0 rgba(255,236,0,0.35); }
.pcard.sel .pcard-img { border-color: var(--neon-yellow); }
.pcard.sel .pcard-check { opacity: 1; transform: scale(1); }

/* 선택 화면: 카드+버튼 한 셀 */
.select-row { gap: 8px !important; margin-bottom: 8px !important; }
.select-cell { gap: 4px !important; }
.pick-btn button { background: #221d33 !important; color: #ECE8F5 !important;
  border: 1px solid #4a4060 !important; border-radius: 8px !important;
  font-size: 12px !important; font-weight: 700 !important; padding: 6px 0 !important;
  width: 100% !important; }
.pick-btn button:hover { border-color: var(--neon-pink) !important;
  color: var(--neon-pink) !important; }

/* ===== 버튼 ===== */
.kakao-btn button { background: var(--neon-pink) !important; color: #fff !important; font-weight:900 !important;
  border: 3px solid #000 !important; border-radius: 0 !important; font-size: 17px !important;
  box-shadow: 4px 4px 0 var(--neon-yellow) !important; transition: transform 80ms ease !important;
  text-shadow: 1px 1px 0 #000 !important; letter-spacing: 1px !important; }
.kakao-btn button:hover { transform: translate(-1px,-1px) !important;
  box-shadow: 5px 5px 0 var(--neon-cyan) !important; }
.kakao-btn button:active { transform: translate(2px,2px) !important;
  box-shadow: 2px 2px 0 var(--neon-yellow) !important; }

/* 로딩 */
.brand-title { font-size: 23px; font-weight: 900; color: var(--neon-yellow) !important;
  text-shadow: 2px 2px 0 var(--neon-pink); }
.loading-line { font-size:14px; padding:5px 0; color: var(--neon-green) !important; font-weight: 700;
  text-shadow: 0 0 6px rgba(57,255,20,0.5); }
.disclaimer-small { text-align:center; font-size:10.5px; color:#6a5a8a; padding:6px; }

/* 입력창 */
#chatbox + * textarea, textarea { background: #221d33 !important; color: #ECE8F5 !important;
  border: 1px solid #3a3450 !important; }

/* 자동채팅 토글 */
.auto-toggle { background: #221d33 !important; border: 1px solid #3a3450 !important;
  border-radius: 8px !important; padding: 6px 10px !important; margin: 6px 0 !important; }
.auto-toggle label, .auto-toggle span { color: #E8C84A !important; font-size: 13px !important;
  font-weight: 700 !important; }
.auto-toggle input[type="checkbox"] { accent-color: #FF00A0 !important; }

/* 페르소나 인라인 아바타 */
#chatbox img.pavatar {
  width: 42px !important; height: 42px !important;
  min-width: 42px !important; max-width: 42px !important;
  border-radius: 50% !important; object-fit: cover !important;
  display: inline-block !important; vertical-align: middle !important;
  margin: 0 8px 0 0 !important; border: 2px solid #4a4060 !important; }
"""


# ===========================================================================
# Chatbot 메시지 변환
# 내부 history: [{"role":"user"/"assistant", "pid"?, "name", "content"}]
# Gradio Chatbot(type="messages")는 role + content 사용. 아바타/이름은 metadata로.
# ===========================================================================
def _avatar_html(pid):
    """작은 원형 아바타 <img> (이미지 파일 또는 첫 글자 fallback)."""
    src = avatar_for(pid)
    return f'<img class="pavatar" src="{src}" alt="">'


def _user_avatar_html():
    return f'<img class="pavatar" src="{user_avatar()}" alt="">'


def to_chat(history):
    msgs = []
    for h in history:
        if h["role"] == "user":
            # 유저도 프로필(아바타+이름) 표시 — 우측 정렬용 클래스
            head = f'<div class="pname uname">{h["name"]}{_user_avatar_html()}</div>'
            msgs.append({"role": "user",
                         "content": f'{head}<div class="utext">{h["content"]}</div>'})
        elif h["role"] == "system":
            # 카톡식 회색 중앙 안내 (metadata 박스 대신 직접 마크업)
            msgs.append({"role": "assistant",
                         "content": f'<div class="sys-note">{h["content"]}</div>'})
        else:
            # 페르소나: 본문 앞에 [아바타 + 이름] 한 줄, 그 아래 내용
            pid = h.get("pid")
            avatar = _avatar_html(pid) if pid else ""
            head = f'<div class="pname">{avatar}<span>{h["name"]}</span></div>'
            msgs.append({"role": "assistant",
                         "content": f'{head}<div class="ptext">{h["content"]}</div>'})
    return msgs


def typing_bubble(history, pid):
    """타이핑 인디케이터를 임시 말풍선으로."""
    tmp = history + [{"role": "assistant", "pid": pid, "name": persona_name(pid), "content": "● ● ●"}]
    return to_chat(tmp)


# ===========================================================================
# 화면 전환 헬퍼 — 5개 screen group의 visible 토글
# ===========================================================================
def show(screen):
    return {
        "start":    gr.update(visible=(screen == "start")),
        "loading1": gr.update(visible=(screen == "loading1")),
        "select":   gr.update(visible=(screen == "select")),
        "loading2": gr.update(visible=(screen == "loading2")),
        "chat":     gr.update(visible=(screen == "chat")),
    }


# ===========================================================================
# 이벤트 핸들러
# ===========================================================================
def on_start(nickname, state):
    """[1] 시작 → [2] 초기 로딩."""
    if not (nickname or "").strip():
        gr.Warning("닉네임을 입력해주세요.")
        # 변화 없음
        s = show("start")
        return (s["start"], s["loading1"], s["select"], s["loading2"], s["chat"],
                state, gr.update(), gr.update())

    state["nickname"] = nickname.strip()
    s = show("loading1")

    # 초기 로딩 항목 점진 표시 + 진행률
    items = ["서버 연결 중…", "캐릭터 명단 불러오는 중…", "단톡방 엔진 준비 중…", "입장 준비 완료!"]
    html = ""
    for i, it in enumerate(items, 1):
        html += f"<div class='loading-line'>✓ {it}</div>"
        yield (s["start"], s["loading1"], s["select"], s["loading2"], s["chat"],
               state, gr.update(value=html), gr.update(visible=False))
        time.sleep(0.5)

    # 완료 → "친구 초대하러 가기" 버튼 노출
    yield (s["start"], s["loading1"], s["select"], s["loading2"], s["chat"],
           state, gr.update(value=html), gr.update(visible=True))


def on_go_select(state):
    """[2] → [3] 페르소나 선택."""
    s = show("select")
    return s["start"], s["loading1"], s["select"], s["loading2"], s["chat"]


def _persona_card_html(pid, picked):
    """프로필 사진(크게) + 이름(작게) 카드 1개 (버튼은 아래 별도 컴포넌트)."""
    p = PERSONAS[pid]
    sel = "sel" if pid in picked else ""
    # 아주 긴 이름(공백 포함 9자 이상)만 글씨를 줄여 칸에 맞춤 (예: 낙방 선비 이희창)
    name_cls = "pcard-name long" if len(p["name"]) >= 9 else "pcard-name"
    return (
        f'<div class="pcard {sel}">'
        f'<img class="pcard-img" src="{avatar_for(pid)}" alt="">'
        f'<div class="{name_cls}">{p["name"]}</div>'
        f'<div class="pcard-check">✓</div>'
        f'</div>'
    )


def render_one_card(pid, picked):
    """카드 1개를 그리드 셀 없이 단독 렌더 (개별 HTML 컴포넌트용)."""
    return _persona_card_html(pid, picked)


def render_cards(picked):
    """선택 상태를 반영한 11개 카드 그리드 HTML (전체 리셋용)."""
    cards = "".join(_persona_card_html(pid, picked) for pid in PERSONA_IDS)
    return f'<div class="pcard-grid">{cards}</div>'


def btn_label(pid, picked):
    """선택 버튼 라벨 (선택 상태에 따라 토글)."""
    return "✓ 선택됨" if pid in picked else "선택"


def on_toggle_persona(pid, picked):
    """선택 버튼 클릭 시 선택/해제 토글. 해당 카드 + 버튼 라벨만 갱신."""
    picked = list(picked or [])
    if pid in picked:
        picked.remove(pid)
    else:
        picked.append(pid)
    return picked, render_one_card(pid, picked), gr.update(value=btn_label(pid, picked))


def on_make_room(selected, state):
    """[3] → [4] 단톡방 생성 로딩 → [5] 채팅방 입장 시퀀스."""
    if not selected:
        gr.Warning("최소 한 명을 선택해주세요!")
        s = show("select")
        yield (s["start"], s["loading1"], s["select"], s["loading2"], s["chat"],
               state, gr.update(), gr.update(), gr.update())
        return

    state["personas"] = selected
    state["history"] = []
    state["typing"] = ""   # 입력창 내용 (정지 판단용)
    state["epoch"] = state.get("epoch", 0) + 1

    # --- [4] 단톡방 생성 로딩: 선택한 페르소나만 한 줄씩 ---
    s = show("loading2")
    actions = {
        "mz": "셀카 각도 잡는 중", "seonbi": "갓 고쳐 쓰는 중", "busan": "헛기침 다듬는 중",
        "tutor": "화이트보드 닦는 중", "noh": "팔레트 꺼내는 중", "han": "타임머신 예열 중",
        "minami": "발성 연습 중", "lee": "브리핑 자료 챙기는 중", "sim": "출석부 펴는 중",
        "kid": "텐텐 까먹는 중", "hyori": "요가 매트 펴는 중",
    }
    html = ""
    for pid in selected:
        html += f"<div class='loading-line'>✓ {persona_name(pid)}가 {actions.get(pid,'준비하는 중')}…</div>"
        yield (s["start"], s["loading1"], s["select"], s["loading2"], s["chat"],
               state, gr.update(value=html), gr.update(), gr.update())
        time.sleep(0.4)
    time.sleep(0.4)

    # --- [5] 채팅방으로 전환 + 입장 시퀀스 ---
    s = show("chat")
    history = state["history"]
    history.append({"role": "system", "name": "안내", "content": f"{state['nickname']} 님이 들어왔습니다."})
    yield (s["start"], s["loading1"], s["select"], s["loading2"], s["chat"],
           state, gr.update(), to_chat(history), _members_text(selected))
    time.sleep(ENTER_INTERVAL_SEC)

    # 한 명씩 차례로 입장 안내
    for pid in selected:
        history.append({"role": "system", "name": "안내", "content": f"{persona_name(pid)} 님이 들어왔습니다."})
        yield (s["start"], s["loading1"], s["select"], s["loading2"], s["chat"],
               state, gr.update(), to_chat(history), _members_text(selected))
        time.sleep(ENTER_INTERVAL_SEC)

    # 첫 고민 입력 유도
    history.append({"role": "system", "name": "안내", "content": "고민을 입력해보세요. 모두가 한마디씩 거듭니다 💬"})
    yield (s["start"], s["loading1"], s["select"], s["loading2"], s["chat"],
           state, gr.update(), to_chat(history), _members_text(selected))


def _members_text(selected):
    names = " · ".join(persona_name(p) for p in selected)
    return gr.update(value=f"<b>고민 난장방</b> <span style='color:#2C3E50;font-size:12px'>({len(selected)}명: {names})</span>")


def on_typing(text, state):
    """입력창 변화 감지 → 글자가 있으면 진행 중인 응답을 멈추도록 epoch 증가 (사양서 5번)."""
    has_text = bool((text or "").strip())
    # 빈 칸 -> 채워짐 으로 바뀌는 순간에만 한 번 끊는다
    if has_text and not state.get("typing", "").strip():
        state["epoch"] = state.get("epoch", 0) + 1
    state["typing"] = text or ""
    return state


def _emit_one(history, pid, state, my_epoch):
    """한 캐릭터의 응답을 생성해 말풍선으로 내보내는 제너레이터(헬퍼).
    중단(epoch 불일치) 시 False 신호를 위해 yield 후 호출측에서 epoch 확인."""
    # 타이핑 인디케이터 (원본 history를 변경하지 않음 — typing_bubble이 새 리스트 생성)
    yield gr.update(), typing_bubble(history, pid), state
    time.sleep(TYPING_HINT_SEC)
    if state.get("epoch") != my_epoch:
        return
    # 응답 생성 — 항상 state의 최신 history를 사용 (자동채팅 중 새 메시지 맥락 반영)
    cur_history = state.get("history", history)
    try:
        raw = generate_reply(cur_history, pid)
    except Exception as e:
        raw = f"(앗, 응답 생성 중 문제가 생겼어요: {type(e).__name__})"
    # LLM 호출이 끝난 직후 확인 — 호출 중 새 메시지가 왔으면 이 응답은 버린다
    if state.get("epoch") != my_epoch:
        return
    # 방어 파서 → 개별 말풍선
    for seg_pid, seg_text in parse_speakers(raw, pid):
        history.append({"role": "assistant", "pid": seg_pid,
                        "name": persona_name(seg_pid), "content": seg_text})
        yield gr.update(), to_chat(history), state
        time.sleep(BUBBLE_INTERVAL_SEC)
        if state.get("epoch") != my_epoch:
            return


def on_send(message, auto_mode, state):
    """
    메시지 전송 처리. 두 가지 모드:
    - 기본(호명) 모드: 메시지에서 호명된 캐릭터만 1회씩 답하고 끝. 아무도 호명 안 하면 선택자 전원이 1회씩.
    - 자동채팅 모드(auto_mode=True): 선택된 캐릭터들이 '무작위 순서'로 계속 대화(유저 개입 전까지).
    유저가 입력/전송하면 epoch이 바뀌어 진행 중 응답이 즉시 중단됨.
    """
    message = (message or "").strip()
    history = state.get("history", [])
    selected = state.get("personas", [])

    if not message:
        yield gr.update(), to_chat(history), state
        return

    # 이 전송을 최신으로 표시 → 이전 루프는 epoch 불일치로 종료
    state["typing"] = ""
    state["epoch"] = state.get("epoch", 0) + 1
    my_epoch = state["epoch"]

    # 사용자 말풍선 즉시
    history.append({"role": "user", "name": state.get("nickname", "나"), "content": message})
    yield gr.update(value=""), to_chat(history), state

    if auto_mode:
        # ===== 자동채팅 모드: 무작위 순서로 계속 대화 =====
        spoken = 0
        last_pid = None
        while spoken < MAX_AUTO_MSGS:
            if state.get("epoch") != my_epoch:
                return
            # 무작위 선택 (직전 화자 연속 방지)
            candidates = [p for p in selected if p != last_pid] or selected
            pid = random.choice(candidates)
            last_pid = pid
            before = len(history)
            for out in _emit_one(history, pid, state, my_epoch):
                yield out
            if state.get("epoch") != my_epoch:
                return
            spoken += (len(history) - before)
        history.append({"role": "system", "name": "안내",
                        "content": "(자동 대화가 잠시 멈췄어요. 메시지를 입력하면 이어집니다 💬)"})
        yield gr.update(), to_chat(history), state
    else:
        # ===== 기본(호명) 모드: 호명된 사람만 1회씩, 없으면 전원 1회씩 =====
        responders = detect_mentions(message, selected) or selected
        for pid in responders:
            if state.get("epoch") != my_epoch:
                return
            for out in _emit_one(history, pid, state, my_epoch):
                yield out
        # 끝 → 유저 재입력 대기 (자동 이어가기 없음)


def on_exit(state):
    """종료 → 상태 초기화 → 시작 화면. 카드/버튼도 전부 미선택 상태로 리셋."""
    state.clear()
    state.update({"nickname": "", "personas": [], "history": [], "typing": "", "epoch": 0})
    s = show("start")
    # 출력 순서: screens(5) + state + nickname + picked_state(빈) + chatbox(빈)
    #            + 카드 11개(미선택) + 버튼 11개("선택" 라벨)
    out = [s["start"], s["loading1"], s["select"], s["loading2"], s["chat"],
           state, gr.update(value=""), [], gr.update(value=[])]
    out += [render_one_card(pid, []) for pid in PERSONA_IDS]
    out += [gr.update(value="선택") for pid in PERSONA_IDS]
    return tuple(out)


# ===========================================================================
# UI 빌드
# ===========================================================================
def build():
    dark_theme = gr.themes.Base(
        primary_hue="pink", secondary_hue="purple", neutral_hue="slate",
    ).set(
        body_background_fill="#0a0a12",
        body_background_fill_dark="#0a0a12",
        background_fill_primary="#12101f",
        block_background_fill="#12101f",
        body_text_color="#f0e6ff",
        block_border_color="#2a1a3e",
        input_background_fill="#1c1430",
    )
    with gr.Blocks(title="고민 난장회의", css=CSS, theme=dark_theme) as demo:
        state = gr.State({"nickname": "", "personas": [], "history": [], "typing": "", "epoch": 0})

        # ---- [1] 시작 ----
        with gr.Group(visible=True) as g_start:
            gr.HTML("<div class='center-wrap'>"
                    "<div class='hero-badge'>⚠ 주의: 정신 사나움</div>"
                    "<div class='hero-emoji'>🗣️</div>"
                    "<div class='hero-title'>이상한 사람들이<br><span class='pop'>내 고민에 난입</span>한다</div>"
                    "<div class='hero-sub'>진지한 상담은 기대 마세요.<br>11명의 수상한 캐릭터가 우르르 몰려와 한마디씩 거듭니다.</div></div>")
            nickname = gr.Textbox(placeholder="닉네임을 입력하세요", show_label=False, max_lines=1)
            start_btn = gr.Button("난장판 입장하기", elem_classes="kakao-btn")

        # ---- [2] 초기 로딩 ----
        with gr.Group(visible=False) as g_loading1:
            gr.HTML("<div class='brand-title' style='text-align:center;margin-top:30px'>입장 준비 중…</div>")
            loading1_html = gr.HTML("")
            invite_btn = gr.Button("친구 초대하러 가기", elem_classes="kakao-btn", visible=False)

        # ---- [3] 페르소나 선택 ----
        with gr.Group(visible=False) as g_select:
            gr.HTML("<div class='sel-head'>"
                    "<div class='sel-title'>누구를 부를까요? 🤔</div>"
                    "<div class='sel-sub'>카드 아래 [선택] 버튼을 눌러 고르세요 · 많이 부를수록 정신없어집니다</div></div>")
            picked_state = gr.State([])
            persona_cards = {}   # pid -> gr.HTML (카드)
            persona_btns = {}    # pid -> gr.Button (선택 버튼)
            # 3열 그리드: 한 컬럼에 [카드 + 선택 버튼] 한 세트
            cols_per_row = 3
            ids = PERSONA_IDS
            for r in range(0, len(ids), cols_per_row):
                with gr.Row(elem_classes="select-row"):
                    for pid in ids[r:r+cols_per_row]:
                        with gr.Column(elem_classes="select-cell", min_width=90):
                            persona_cards[pid] = gr.HTML(render_one_card(pid, []))
                            persona_btns[pid] = gr.Button("선택", size="sm",
                                                          elem_classes="pick-btn")
            make_room_btn = gr.Button("이들을 단톡방에 소환", elem_classes="kakao-btn")

        # ---- [4] 단톡방 생성 로딩 ----
        with gr.Group(visible=False) as g_loading2:
            gr.HTML("<div class='brand-title' style='text-align:center;margin-top:30px'>단톡방 만드는 중…</div>")
            loading2_html = gr.HTML("")

        # ---- [5] 채팅방 ----
        with gr.Group(visible=False) as g_chat:
            chat_header = gr.HTML("<b>고민 난장방</b>")
            chatbox = gr.Chatbot(type="messages", height=440, elem_id="chatbox",
                                 show_label=False, avatar_images=None)
            auto_toggle = gr.Checkbox(
                label="🔥 자동채팅 (켜면 캐릭터들끼리 무작위로 계속 떠듭니다)",
                value=False, elem_classes="auto-toggle")
            with gr.Row():
                message = gr.Textbox(placeholder="고민을 입력… (이름을 부르면 그 사람만 답해요)",
                                     show_label=False, scale=8, max_lines=3)
                send_btn = gr.Button("전송", scale=1, elem_classes="kakao-btn")
            exit_btn = gr.Button("나가기", size="sm")

        gr.HTML("<div class='disclaimer-small'>모든 캐릭터는 팬메이드 패러디이며 실제 인물과 무관합니다 · AI 생성 오락 콘텐츠</div>")

        screens = [g_start, g_loading1, g_select, g_loading2, g_chat]

        # ---- 이벤트 바인딩 ----
        start_btn.click(on_start, [nickname, state],
                        screens + [state, loading1_html, invite_btn])

        invite_btn.click(on_go_select, [state], screens)

        # 선택 버튼: 각 버튼 클릭 → 토글 → 해당 카드 HTML + 버튼 라벨 갱신
        for pid, btn in persona_btns.items():
            btn.click(on_toggle_persona,
                      [gr.State(pid), picked_state],
                      [picked_state, persona_cards[pid], btn])

        make_room_btn.click(on_make_room, [picked_state, state],
                            screens + [state, loading2_html, chatbox, chat_header])

        # 입력 중 정지: 사용자가 직접 타이핑할 때만 발동 (input). 프로그램이 비울 땐 발동 안 함.
        message.input(on_typing, [message, state], [state])

        send_btn.click(on_send, [message, auto_toggle, state], [message, chatbox, state],
                       concurrency_limit=1, concurrency_id="chat_turn")
        message.submit(on_send, [message, auto_toggle, state], [message, chatbox, state],
                       concurrency_limit=1, concurrency_id="chat_turn")

        # 나가기: 카드/버튼 전부 초기 상태로 되돌림
        exit_outputs = screens + [state, nickname, picked_state, chatbox]
        exit_outputs += [persona_cards[pid] for pid in PERSONA_IDS]
        exit_outputs += [persona_btns[pid] for pid in PERSONA_IDS]
        exit_btn.click(on_exit, [state], exit_outputs)

    demo.queue(default_concurrency_limit=8)
    return demo


if __name__ == "__main__":
    print(">>> 앱 빌드 중...")
    demo = build()
    print(">>> 빌드 완료. 서버를 시작합니다.")
    print(">>> 잠시 후 아래에 표시되는 'Running on local URL' 주소를 브라우저에 입력하세요.")
    # server_name 미지정(기본 127.0.0.1) + 포트 충돌 시 자동으로 다음 포트 탐색
    demo.launch(show_api=False)