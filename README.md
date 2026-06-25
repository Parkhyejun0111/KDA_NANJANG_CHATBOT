[README.md](https://github.com/user-attachments/files/29324000/README.md)
# 고민 난장회의 챗봇

여러 페르소나를 선택해 고민을 나누는 Gradio 기반 챗봇입니다. 사용자가 닉네임을 입력하고 대화방에 참여할 캐릭터를 고르면, 선택된 페르소나들이 각자의 말투와 관점으로 답변합니다.

## 주요 기능

- 여러 캐릭터 페르소나 선택
- 사용자 메시지에 대한 자동 응답
- 특정 인물 이름을 언급하면 해당 페르소나 우선 응답
- 현재 날짜/시간, D-day 계산, 날씨, 웹 검색, 노래 추천 도구 사용
- `images` 폴더의 캐릭터 이미지를 아바타로 표시
- OpenAI 또는 Anthropic 모델 선택 가능

## 폴더 구성

```text
0625_chatbot/
├─ app.py              # Gradio 화면과 사용자 흐름
├─ llm.py              # LLM 제공자 설정 및 도구 호출 처리
├─ tools.py            # 페르소나, 검색, 날씨, 날짜 도구
├─ requirements.txt    # 필요한 패키지 목록
├─ images/             # 캐릭터 및 사용자 아바타 이미지
└─ .env                # API 키와 모델 설정
```

## 실행 방법

1. 필요한 패키지를 설치합니다.

```bash
pip install -r requirements.txt
```

2. `.env` 파일에 사용할 API 키와 모델을 설정합니다.

```env
LLM_PROVIDER=openai
OPENAI_API_KEY=your_openai_api_key
OPENAI_MODEL=gpt-4o-mini
```

Anthropic을 사용할 경우 아래처럼 설정할 수 있습니다.

```env
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=your_anthropic_api_key
ANTHROPIC_MODEL=claude-haiku-4-5
```

3. 앱을 실행합니다.

```bash
python app.py
```

실행 후 터미널에 표시되는 로컬 주소를 브라우저에서 열면 사용할 수 있습니다.

## 페르소나

- MZ 인플루언서
- 낙방 선비 이희창
- 부산 사나이
- 이정수 보조강사
- 감성가득 노재희
- 무한긍정 한희지
- 리센느 미나미
- 이재명 대통령 패러디
- 심은숙 강사님
- 초딩 박혜준
- 멘탈갑 이효리

## 참고

- `.env` 파일에는 API 키가 들어갈 수 있으므로 공유하지 않는 것이 좋습니다.
- `images/user.png`가 있으면 사용자 아바타로 사용됩니다.
- 앱은 기본적으로 로컬 환경에서 실행됩니다.
