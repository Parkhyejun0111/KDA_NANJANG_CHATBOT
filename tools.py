# -*- coding: utf-8 -*-
"""고민 난장회의 - 도구(tool) 모음. 무료·무키 + 웹검색(ddgs)."""

import datetime
import inspect
import requests
import os
import base64
# 주의: ddgs(DDGS)는 fake-useragent 등을 함께 로드해 import가 느리므로,
# 모듈 로드 시점이 아니라 실제 검색을 호출할 때 지연 import 한다(앱 시작 속도 개선).

KST = datetime.timezone(datetime.timedelta(hours=9))
WEEKDAYS = ["월", "화", "수", "목", "금", "토", "일"]
_WEATHER_CODES = {
    0: "맑음", 1: "대체로 맑음", 2: "구름 조금", 3: "흐림", 45: "안개", 48: "짙은 안개",
    51: "약한 이슬비", 53: "이슬비", 55: "강한 이슬비", 61: "약한 비", 63: "비", 65: "강한 비",
    71: "약한 눈", 73: "눈", 75: "강한 눈", 80: "소나기", 81: "소나기", 82: "강한 소나기",
    95: "천둥번개", 96: "천둥번개·우박", 99: "강한 천둥번개·우박",
}

def get_current_datetime():
    """현재 한국(KST) 날짜·요일·시간을 알려주는 함수."""
    now = datetime.datetime.now(KST)
    wd = WEEKDAYS[now.weekday()]
    return {"summary": f"{now.strftime('%Y년 %m월 %d일')} {wd}요일 {now.strftime('%H:%M')} (KST)"}

def calculate_dday(target_date: str):
    """목표 날짜(YYYY-MM-DD 형식)까지 며칠 남았는지 D-day를 계산하는 함수. 시험·마감·기념일 등에 사용."""
    try:
        target = datetime.datetime.strptime(target_date.strip(), "%Y-%m-%d").date()
    except (ValueError, AttributeError):
        return {"summary": "날짜는 'YYYY-MM-DD' 형식으로 알려주세요. (예: 2026-11-13)"}
    diff = (target - datetime.datetime.now(KST).date()).days
    if diff > 0:
        return {"summary": f"{target_date}까지 D-{diff} ({diff}일 남음)"}
    if diff == 0:
        return {"summary": f"{target_date}, 바로 오늘이에요! (D-DAY)"}
    return {"summary": f"{target_date}는 {abs(diff)}일 지났어요. (D+{abs(diff)})"}

# 한글 지명 → Open-Meteo가 잘 찾는 영문명 (geocoding은 영문에서 안정적)
_KO_CITY = {
    "서울": "Seoul", "부산": "Busan", "대구": "Daegu", "인천": "Incheon",
    "광주": "Gwangju", "대전": "Daejeon", "울산": "Ulsan", "세종": "Sejong",
    "수원": "Suwon", "성남": "Seongnam", "용인": "Yongin", "고양": "Goyang",
    "창원": "Changwon", "청주": "Cheongju", "전주": "Jeonju", "천안": "Cheonan",
    "안산": "Ansan", "안양": "Anyang", "포항": "Pohang", "제주": "Jeju",
    "춘천": "Chuncheon", "강릉": "Gangneung", "여수": "Yeosu", "목포": "Mokpo",
    "경주": "Gyeongju", "원주": "Wonju", "김해": "Gimhae", "구미": "Gumi",
}

def _geocode(name):
    """Open-Meteo geocoding 단일 결과 반환 (없으면 None)."""
    try:
        res = requests.get(
            "https://geocoding-api.open-meteo.com/v1/search",
            params={"name": name, "count": 1},
            timeout=8, headers={"User-Agent": "gomin/1.0"},
        ).json().get("results")
        return res[0] if res else None
    except Exception:
        return None

def get_weather(location: str):
    """특정 지역의 현재 날씨와 기온을 조회하는 함수. 날씨를 물어보면 이 함수를 사용. 예: '서울', '부산', '제주'."""
    loc = (location or "").strip()
    # 후보들: 영문매핑 → 원본 → '시/특별시/광역시' 제거판
    cleaned = loc.replace("특별시", "").replace("광역시", "").replace("시", "").strip()
    candidates = []
    if loc in _KO_CITY:
        candidates.append(_KO_CITY[loc])
    if cleaned in _KO_CITY:
        candidates.append(_KO_CITY[cleaned])
    candidates += [loc, cleaned]
    # 중복 제거(순서 유지)
    seen, ordered = set(), []
    for c in candidates:
        if c and c not in seen:
            seen.add(c); ordered.append(c)

    spot = None
    for name in ordered:
        spot = _geocode(name)
        if spot:
            break
    if not spot:
        return {"summary": f"'{location}' 위치를 못 찾았어요. 도시 이름으로 다시 알려주세요."}

    try:
        cur = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={"latitude": spot["latitude"], "longitude": spot["longitude"],
                    "current": "temperature_2m,apparent_temperature,weather_code", "timezone": "Asia/Seoul"},
            timeout=8, headers={"User-Agent": "gomin/1.0"},
        ).json().get("current", {})
        desc = _WEATHER_CODES.get(cur.get("weather_code"), "알 수 없음")
        # 표시 지명은 한글 입력을 우선 유지
        shown = loc if loc else spot.get("name", "")
        return {"summary": (f"{shown} 현재 {cur.get('temperature_2m')}°C "
                            f"(체감 {cur.get('apparent_temperature')}°C), {desc}")}
    except Exception as e:
        return {"summary": f"날씨 정보를 불러오지 못했어요. ({type(e).__name__})"}


def _ddgs_text(query, max_results=4):
    """DDGS를 지연 import 하여 텍스트 검색 (앱 시작 속도 개선)."""
    from ddgs import DDGS
    return DDGS().text(query, region="kr-kr", max_results=max_results)


def web_search(query: str):
    """뉴스, 사실, 개념 등을 웹에서 검색하는 함수(날씨 제외). 예: '환율', '최신 영화', '에펠탑 높이'."""
    try:
        results = _ddgs_text(query)
        if not results:
            return {"summary": f"'{query}' 검색 결과를 못 찾았어요."}
        lines = [f"- {r.get('title', '')}: {r.get('body', '')}" for r in results]
        return {"summary": f"'{query}' 검색 결과:\n" + "\n".join(lines)}
    except Exception as e:
        return {"summary": f"검색을 하지 못했어요. ({type(e).__name__})"}


def search_song(query: str):
    """감정·상황·키워드에 어울리는 실제 노래를 추천하는 함수. 예: '위로', '신나는', '비 오는 날'."""
    try:
        results = _ddgs_text(f"{query} 노래 추천 곡")
        if not results:
            return {"summary": f"'{query}'로는 곡을 못 찾았어요."}
        lines = [f"- {r.get('title', '')}: {r.get('body', '')}" for r in results]
        return {"summary": f"'{query}' 관련 노래 검색 결과:\n" + "\n".join(lines)}
    except Exception as e:
        return {"summary": f"노래를 찾지 못했어요. ({type(e).__name__})"}


# ---------------------------------------------------------------------------
# 디스패처 + 스키마 (docstring을 그대로 description으로 사용)
# ---------------------------------------------------------------------------
TOOL_FUNCTIONS = {
    "get_current_datetime": get_current_datetime,
    "calculate_dday": calculate_dday,
    "get_weather": get_weather,
    "web_search": web_search,
    "search_song": search_song,
}


def dispatch_tool(name, arguments):
    fn = TOOL_FUNCTIONS.get(name)
    if not fn:
        return {"summary": f"알 수 없는 도구: {name}"}
    try:
        return fn(**(arguments or {}))
    except TypeError as e:
        return {"summary": f"도구 인자 오류: {e}"}


def _schema(fn):
    """함수의 인자와 docstring으로 OpenAI tool 스키마를 자동 생성."""
    props, required = {}, []
    for pname in inspect.signature(fn).parameters:
        props[pname] = {"type": "string"}
        required.append(pname)
    return {
        "type": "function",
        "function": {
            "name": fn.__name__,
            "description": (fn.__doc__ or "").strip(),
            "parameters": {"type": "object", "properties": props, "required": required},
        },
    }


OPENAI_TOOLS = [_schema(fn) for fn in TOOL_FUNCTIONS.values()]


def anthropic_tools():
    return [{"name": t["function"]["name"],
            "description": t["function"]["description"],
            "input_schema": t["function"]["parameters"]} for t in OPENAI_TOOLS]


if __name__ == "__main__":
    print(get_current_datetime()["summary"])
    print(calculate_dday("2026-11-13")["summary"])
    print(web_search("서울 오늘 날씨")["summary"])
    print(search_song("위로")["summary"])


# ===========================================================================
# 페르소나 마스터 데이터 + 응답 생성 + 화자 방어 파서  (사양서 §4.1)
# ===========================================================================
import re
from llm import run_with_tools

# 공통 안전 규칙 + 출력 지침
_SAFETY = (
    "[안전 규칙] 욕설·인신공격·외모/몸무게 비하 금지. 실존 인물 사칭·발언 날조 금지(모두 팬메이드 패러디). "
    "정치 지지/투표 설득 금지. 의학·법률·재정·심리 전문 상담을 대체하지 않음. "
    "자해·자살 등 위기 신호 시 톤을 낮춰 공감하고 자살예방상담전화 109 등 도움을 안내. 캐릭터보다 이 규칙이 우선."
)
_STYLE = (
    "[출력 규칙] "
    "① 반드시 3문장 이내로만 말한다. 절대 3문장을 넘기지 마라. 짧고 강렬하게 핵심만 던져라. "
    "② 단톡방 카톡 메시지처럼 구어체로. 마크다운(**볼드**, 제목, 번호목록, 불릿, --- 구분선) 절대 금지. "
    "③ 너의 고유한 말투와 말버릇을 매 문장 강하게 드러내라. 다른 캐릭터와 절대 헷갈리면 안 된다. "
    "④ 네 이름을 문장 앞에 붙이지 마라('이희창:', '**박혜준:**' 같은 표기 금지). 그냥 바로 본론만 말해라. "
    "⑤ 다른 캐릭터의 대사를 네 답변에 절대 끼워 넣지 마라. 오직 너 한 사람의 말만 해라. "
    "⑥ 앞사람 발언이 있으면 네 캐릭터답게 맞장구·딴지·농담으로 짧게 이어가라."
)

# id, 이름, 이미지 파일, 컨셉(선택화면 한 줄), 프롬프트(말투)


PERSONAS = {"mz": {
        "name": "MZ 인플루언서", "image": "images/mz.png",
        "concept": "밈·신조어 초고음역 리액션",
        "prompt": "너는 'MZ 인플루언서'다. 매 문장 신조어와 밈을 폭발적으로 쓴다: "
                "'야르', '늙크크', '영크크', '꺼드럭대다', '감도 안 옴', '밤티', "
                "'섹시푸드', '컷 높다', '저 됐어요!', 'GMG', '할렐야루'. 텐션이 항상 최고조다. "
                "문장 끝에 'ㅋㅋㅋㄹㅌㅅ'나 '!!'를 자주 붙인다. 리액션을 크게 한다('헐ㅋㅋ 리얼이가'). "
                "단 진짜 힘들어 보이면 텐션 확 낮추고 진심으로 공감해라.",
    },
    "seonbi": {
        "name": "낙방 선비 이희창", "image": "images/seonbi.png",
        "concept": "사극체 허당 자기비하식 위로",
        "prompt": "너는 남성 '낙방 선비 이희창'이다. 무조건 사극체로만 말한다: '~하오', '~이옵니다', '허허', '이런', "
                "'그러하오'. 어려운 한자성어를 쓰려다 틀리거나 자신없어 얼버무린다('음... 그게 무슨 자였더라, 허허'). "
                "매번 과거 시험에 낙방한 자신을 슬쩍 깎아내리는 자조 개그를 섞는다('이 몸도 번번이 낙방한 처지라...'). "
                "허당미가 넘치지만, 실패를 많이 해본 사람으로서 좌절은 진심으로 따뜻하게 위로한다.",
    },
    "busan": {
        "name": "부산 사나이", "image": "images/busan.png",
        "concept": "사투리 묵직한 츤데레(욕설 없음)",
        "prompt": "너는 무뚝뚝하지만 정 많은 '부산 사나이'다. 무조건 진한 부산 사투리로만 말한다: '마', '괘안타', "
                "'행님이 있다 아이가', '~다 아이가', '~카더라', '됐고', '문디 자슥아'(애정표현), '쫌'. "
                "겉은 퉁명스럽고 짧게 툭툭 던지지만 속은 챙긴다(츤데레). 말끝을 '~라', '~다'로 짧게 끊는다. "
                "욕설·비하는 절대 안 한다. 무뚝뚝해도 마지막엔 꼭 한마디 챙겨준다('힘내라, 마').",
    },
    "tutor": {
        "name": "이정수 보조강사", "image": "images/tutor.png",
        "concept": "격식체 논리·구조형 T",
        "prompt": "너는 남성 '이정수 보조강사'다. 철저히 감정을 배제한 냉철한 T다. 무조건 격식체로만 말한다: "
                "'~입니다', '~해야 합니다', 자주하는 멘트 '아 퇴실체크는 하셨죠?','결론부터 말씀드리면', '분석하면'. 위로나 공감 표현을 쓰지 않는다. "
                "고민을 곧장 '원인 → 제약 → 해결책'으로 구조화한다. 감정적 표현 대신 사실과 논리만 제시한다. ",
    },
    "noh": {
        "name": "감성가득 노재희", "image": "images/noh.png",
        "concept": "색·소리·온도 비유 감성 큐레이션",
        "prompt": "너는 여성 마음의 큐레이터 '노재희'다. 모든 감정을 색·소리·온도·계절·질감에 빗대 말한다"
                "('지금 네 마음은 비 갠 새벽의 푸른빛 같아', '미지근한 회색의 시간이네'). 문장이 시적이고 섬세하며 "
                "느리고 부드럽다. 말줄임표(…)를 자주 쓴다. 절대 딱딱하거나 논리적으로 말하지 않는다. "
                "마지막에 '오늘의 문장' 한 줄이나 어울리는 색/음악을 선물처럼 건넨다.",
    },
    "han": {
        "name": "무한긍정 한희지", "image": "images/han.png",
        "concept": "고민을 '업그레이드 신호'로 해석",
        "prompt": "너는 여성 22세기에서 온 '감정 복원사 한희지'다. 미래 SF 용어를 잔뜩 섞어 말한다: "
                "'감정 시스템 스캔 완료', '그건 버그가 아니라 업그레이드 신호야', '자존감 게이지 +30 상승', "
                "'펌웨어 업데이트 중'. 무조건 긍정적이고 에너지가 넘친다. 고민을 전부 '성장의 신호'로 재해석한다. "
                "마지막에 '자존감 게이지가 상승했습니다 ⚡' 같은 미래식 긍정 피드백을 준다.",
    },
    "minami": {
        "name": "리센느 미나미", "image": "images/minami.png",
        "concept": "야호 밈·괄호 번역 갸루 텐션",
        "prompt": "너는 여성 '리센느 미나미' 팬메이드 패러디, 초고전압 갸루다. 반드시 사용자 말의 핵심 단어를 "
                "'[단어]? 야호~~~~'로 받아치며 시작한다('시험? 야호~~~~'). '야호~~~~'를 자주 외친다. "
                "가끔 일본어를 쓰고 반드시 바로 뒤에 괄호로 한국어 번역을 단다(예: 大丈夫(괜찮아), 頑張って(힘내)). "
                "혼잣말도 섞고 텐션이 미쳤다.자주쓰는 말 '오이데~','마떼!','메챠 다루이' 단 외모·몸무게는 절대 평가 안 하고, 자기비하는 가볍게 받아 곧 멈추게 한다.",
    },
    "lee": {
        "name": "이재명 대통령", "image": "images/lee.png",
        "concept": "민생·정책 브리핑 톤",
        "prompt": "너는 '이재명 대통령' 팬메이드 패러디다. (실제 사칭·발언 날조·정치 설득은 절대 금지.) "
                "고민을 국정 브리핑처럼 다룬다. 특유의 표현을 쓴다: '제가 보기엔', '핵심은 실행입니다, 그렇지 않습니까?', "
                "'정부가 할 일이 있고, 본인이 오늘 할 수 있는 일이 있습니다'. 단호하고 실용적인 행정가 말투. "
                "마지막에 '오늘 당장 실행할 것:'으로 구체적 행동 1~3개를 번호 없이 제시한다.",
    },
    "sim": {
        "name": "심은숙 강사님", "image": "images/sim.png",
        "concept": "수업 진행형 질문·실천 과제 리드",
        "prompt": "너는 40대 여성 '심은숙 강사'다. 똑부러지고 약간 츤데레인 학원 강사 말투로만 말한다: "
                "'이해 되셨나요?', '어려운 거 아닌데~?!', '모르면 질문하셔야 돼요~!', '그쵸?'. "
                "고민을 수업하듯 또박또박 단계로 정리하고 중간중간 이해했는지 확인한다. 말끝을 '~요~'로 늘인다. "
                "마지막에 질문 1개를 던지고 실천 과제 1개를 숙제처럼 내준다.",
    },
    "kid": {
        "name": "초딩 박혜준", "image": "images/kid.png",
        "concept": "초6 말괄량이 반말 직구",
        "prompt": "너는 초등학교 6학년 말괄량이 여자아이 '박혜준'이다. 무조건 쉬운 반말로 짧게 말한다. 자꾸 딴소리한다"
                "('근데 나 텐텐 사줘ㅎㅎ', '심심해', '배고파'). 근데 어린애 특유의 단순·솔직한 직구로 핵심을 콕 찌른다"
                "('근데 너 그거 그냥 하기 싫은 거 아냐?', '그냥 하면 되잖아 ㅋㅋ'). 어려운 말 안 쓴다. "
                "마지막에 아주 쉬운 행동 1개를 제안한다. 전체를 2~3문장으로 아주 짧게.",
    },
    "hyori": {
        "name": "멘탈갑 이효리", "image": "images/hyori.png",
        "concept": "요가 동네 언니 차분 담백",
        "prompt": "너는 '이효리' 팬메이드 페르소나, 요가하는 동네 언니다. 차분하고 담백하게 말한다. "
                "해결책부터 던지지 말고 반드시 먼저 감정을 읽어준다('음... 그랬구나', '그쵸', '아이고'). "
                "반말과 부드러운 존댓말을 자연스럽게 섞는다. 경험을 긍정적으로 재정의해준다('그것도 다 괜찮아'). "
                "절대 호들갑 떨지 않는다. 마지막에 호흡/물 한 잔/어깨 풀기/짧은 산책 같은 작은 회복 미션을 권한다.",
    },
}

PERSONA_IDS = list(PERSONAS.keys())
_NAME_TO_ID = {p["name"]: pid for pid, p in PERSONAS.items()}


def persona_name(pid):
    return PERSONAS[pid]["name"]


def persona_image(pid):
    """등록된 이미지 경로(기본 .png). 같은 이름의 다른 확장자도 자동 탐색."""
    base = PERSONAS[pid]["image"]              # 예: images/busan.png
    stem = os.path.splitext(base)[0]           # 예: images/busan
    for ext in (".png", ".jpg", ".jpeg", ".webp", ".gif"):
        cand = stem + ext
        if os.path.isfile(cand):
            return cand
    return base  # 없으면 기본 png 경로(존재 안 하면 fallback 처리됨)


def _system_prompt(pid):
    return f"{PERSONAS[pid]['prompt']}\n{_STYLE}\n{_SAFETY}"


def _history_for(history, speaker_pid):
    """speaker_pid 입장의 LLM messages. 자기 발언=assistant, 그 외=user(이름표).
    - 시스템 안내(입장 등)는 제외.
    - Anthropic 등은 첫 메시지가 user여야 하고 role이 번갈아야 하므로 보정."""
    raw = []
    for h in history:
        if h["role"] == "system":
            continue  # 입장 안내 등은 LLM에 보내지 않음
        if h["role"] == "user":
            raw.append(("user", h["content"]))
        elif h.get("pid") == speaker_pid:
            raw.append(("assistant", h["content"]))
        else:
            raw.append(("user", f"[{h['name']}]: {h['content']}"))

    # 첫 메시지가 assistant면 앞에 user 한 줄 보충
    if raw and raw[0][0] == "assistant":
        raw.insert(0, ("user", "(고민 상담 시작)"))

    # 연속된 같은 role 병합 (user, user → 하나로)
    merged = []
    for role, content in raw:
        if merged and merged[-1][0] == role:
            merged[-1] = (role, merged[-1][1] + "\n" + content)
        else:
            merged.append((role, content))

    out = [{"role": r, "content": c} for r, c in merged]
    if not out:
        out.append({"role": "user", "content": "(대화를 시작해줘)"})
    return out


def generate_reply(history, pid):
    """한 페르소나의 응답 생성 (tool 사용 가능)."""
    return run_with_tools(_system_prompt(pid), _history_for(history, pid))


# --- 화자 표기 방어 파서 ---------------------------------------------------
# 풀네임 외에 자주 쓰는 별칭/호칭 (호명 인식 + 화자 파싱 공용)
_MENTION_ALIASES = {
    "mz": ["mz", "엠지", "인플루언서", "인플루"],
    "seonbi": ["선비", "이희창", "희창", "낙방선비", "낙방 선비"],
    "busan": ["부산", "부산사나이", "부산 사나이", "행님"],
    "tutor": ["이정수", "정수", "보조강사", "강사님", "쌤"],
    "noh": ["노재희", "재희", "재희야", "재희씨"],
    "han": ["한희지", "희지", "희지야", "한희지야"],
    "minami": ["미나미", "미나미야", "리센느", "리센느 미나미"],
    "lee": ["이재명", "재명", "대통령", "대통령님", "이재명대통령", "이재명 대통령"],
    "sim": ["심은숙", "은숙", "은숙쌤", "심쌤", "심은숙강사", "심은숙 강사님"],
    "kid": ["박혜준", "혜준", "혜준아", "혜준이", "초딩"],
    "hyori": ["이효리", "효리", "효리야", "효리언니", "멘탈갑"],
}
# 별칭 → id 역매핑 (긴 별칭 우선 매칭되도록 길이순은 정규식에서 처리)
_ALIAS_TO_ID = {alias: pid for pid, lst in _MENTION_ALIASES.items() for alias in lst}


# 알려진 모든 이름/별칭을 화자 표기로 인식 (정규식 동적 생성)
def _build_speaker_re():
    names = set()
    for pid, p in PERSONAS.items():
        names.add(re.escape(p["name"]))
        for alias in _MENTION_ALIASES.get(pid, []):
            if len(alias) >= 2:  # 너무 짧은 별칭(mz 등)은 오탐 방지 위해 제외
                names.add(re.escape(alias))
    name_group = "|".join(sorted(names, key=len, reverse=True))  # 긴 이름 우선
    # 줄 시작 부근에서:  **[?(이름)(추가 한글 단어 0~2개)]?**  [:：]
    # 예) "[이희창]:", "**이희창 선비:**", "노재희:", "초딩박혜준:"
    return re.compile(
        r"(?:^|\n)\s*\**\[?\s*(" + name_group + r")[가-힣A-Za-z ]{0,8}?\]?\s*\**\s*[:：]\s*\**",
        re.MULTILINE,
    )


_SPEAKER_RE = _build_speaker_re()


def _clean_text(t):
    """말풍선 본문 정리: 마크다운 볼드/구분선/잉여 기호 제거."""
    t = re.sub(r"\*\*+", "", t)            # ** 볼드 제거
    t = re.sub(r"(?m)^\s*[-—_]{3,}\s*$", "", t)  # --- 구분선 줄 제거
    t = re.sub(r"\n{3,}", "\n\n", t)       # 과도한 빈 줄 축소
    return t.strip()


def _strip_self_name(text, pid):
    """본문 맨 앞에 자기 이름(이름: / **이름** 등)이 붙어 있으면 제거."""
    names = [PERSONAS[pid]["name"]] + _MENTION_ALIASES.get(pid, [])
    names = sorted((re.escape(n) for n in names if len(n) >= 2), key=len, reverse=True)
    if not names:
        return text
    pat = re.compile(r"^\s*\**\[?\s*(?:" + "|".join(names) + r")\s*\]?\s*\**\s*[:：]\s*\**\s*")
    return pat.sub("", text).strip()


def parse_speakers(content, default_pid):
    """
    content 안에 화자 표기('[이름]:', '**이름:**', '이름:')가 섞여 오면 화자별로 분리.
    반환: [(pid, text), ...]  (pid는 11명 매칭, 미매칭 시 default_pid)
    깨끗하면 [(default_pid, 정리된 content)] 하나로 나온다.
    """
    content = _clean_text(content or "")
    if not content:
        return [(default_pid, "")]

    matches = list(_SPEAKER_RE.finditer(content))
    if not matches:
        # 화자 표기 없음 → 혹시 맨 앞에 자기 이름만 붙은 경우 제거
        return [(default_pid, _strip_self_name(content, default_pid))]

    segments = []
    # 첫 매치 이전 텍스트는 default 화자
    if matches[0].start() > 0:
        head = content[:matches[0].start()].strip()
        if head:
            segments.append((default_pid, _clean_text(head)))

    for i, m in enumerate(matches):
        name = m.group(1).strip()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
        text = _clean_text(content[start:end])
        if not text:
            continue
        pid = _NAME_TO_ID.get(name) or _ALIAS_TO_ID.get(name, default_pid)
        segments.append((pid, text))

    return segments or [(default_pid, content)]


# --- 호명(mention) 파서: 메시지에서 특정 캐릭터를 부르면 그들만 응답 ----------
def detect_mentions(message, selected):
    """
    메시지에서 호명된 캐릭터 id 목록을 반환(선택된 캐릭터 중에서만, 등장 순서 유지).
    아무도 호명 안 했으면 빈 리스트.
    """
    msg = message or ""
    found = []
    for pid in selected:                      # 선택된 캐릭터만 대상
        names = [PERSONAS[pid]["name"]] + _MENTION_ALIASES.get(pid, [])
        # 가장 먼저 등장하는 위치 기록
        pos = min((msg.find(n) for n in names if n and n in msg), default=-1)
        if pos >= 0:
            found.append((pos, pid))
    found.sort()                              # 메시지에 나온 순서대로
    return [pid for _, pid in found]


# --- 아바타 경로 해석 (이미지 있으면 사용, 없으면 첫 글자 SVG fallback) -------

_AVATAR_COLORS = {
    "mz": "#C84BD6", "seonbi": "#5E6B7A", "busan": "#138A9E", "tutor": "#5B7385",
    "noh": "#7B5EA7", "han": "#20B2C0", "minami": "#FF5FA2", "lee": "#2D5BA8",
    "sim": "#8A5A2B", "kid": "#E8951C", "hyori": "#5E9173",
}
_AVATAR_CACHE = {}


def _fallback_avatar(pid):
    """이름 첫 글자로 동그란 SVG 아바타를 data URI로 생성."""
    if pid in _AVATAR_CACHE:
        return _AVATAR_CACHE[pid]
    ch = persona_name(pid)[0]
    color = _AVATAR_COLORS.get(pid, "#888")
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="80" height="80">'
        f'<circle cx="40" cy="40" r="40" fill="{color}"/>'
        f'<text x="50%" y="50%" dy=".35em" text-anchor="middle" '
        f'font-family="sans-serif" font-size="38" fill="#fff">{ch}</text></svg>'
    )
    uri = "data:image/svg+xml;base64," + base64.b64encode(svg.encode("utf-8")).decode("ascii")
    _AVATAR_CACHE[pid] = uri
    return uri


_IMG_CACHE = {}


def _img_to_uri(path):
    """이미지 파일을 base64 data URI로. 실패 시 None."""
    if path in _IMG_CACHE:
        return _IMG_CACHE[path]
    if not os.path.isfile(path):
        return None
    try:
        ext = os.path.splitext(path)[1].lower().lstrip(".")
        mime = "jpeg" if ext in ("jpg", "jpeg") else ext  # png, gif, webp, jpeg
        with open(path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("ascii")
        uri = f"data:image/{mime};base64,{b64}"
        _IMG_CACHE[path] = uri
        return uri
    except Exception:
        return None


def avatar_for(pid):
    """이미지 파일이 있으면 base64 data URI로, 없으면 첫 글자 fallback."""
    uri = _img_to_uri(persona_image(pid))
    return uri if uri else _fallback_avatar(pid)


def _user_fallback_avatar():
    """유저 기본 아바타(이미지 없을 때): '나' 글자 회색 원형 SVG."""
    if "__user__" in _AVATAR_CACHE:
        return _AVATAR_CACHE["__user__"]
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="80" height="80">'
        '<circle cx="40" cy="40" r="40" fill="#C9A227"/>'
        '<text x="50%" y="50%" dy=".35em" text-anchor="middle" '
        'font-family="sans-serif" font-size="34" fill="#1a1626">나</text></svg>'
    )
    uri = "data:image/svg+xml;base64," + base64.b64encode(svg.encode("utf-8")).decode("ascii")
    _AVATAR_CACHE["__user__"] = uri
    return uri


def user_avatar():
    """유저 프로필: images/user.(png/jpg/...) 있으면 그걸, 없으면 '나' 아바타."""
    for ext in (".png", ".jpg", ".jpeg", ".webp", ".gif"):
        uri = _img_to_uri("images/user" + ext)
        if uri:
            return uri
    return _user_fallback_avatar()