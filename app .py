"""외출 전 1분 | Streamlit 앱
실행: pip install -r requirements.txt && streamlit run app.py
배포: GitHub에 두 파일을 올리고 Streamlit Community Cloud에서 app.py 선택.
QR: 배포 후 앱의 'QR로 공유'에 실제 https://...streamlit.app 주소 입력.
서버 파일/DB에 개인정보를 저장하지 않습니다. 세션 종료 시 초기화될 수 있으니
개인 준비물은 JSON 백업을 내려받으세요. QR에는 개인 준비물을 넣지 않습니다.
"""
from __future__ import annotations

import hashlib
import io
import json
from urllib.parse import urlencode, urlsplit, urlunsplit

import qrcode
import streamlit as st

PURPOSES = {
    "출근·등교": ["사원증·학생증", "노트북·태블릿", "필기구", "업무·수업 자료"],
    "병원·약국": ["신분증", "진료 관련 서류", "복용약 정보", "예약 정보"],
    "운동·산책": ["운동화", "운동복", "수건", "물"],
    "여행·장거리": ["충전기", "보조배터리", "예약·승차 정보", "여벌 옷", "세면도구"],
    "장보기·쇼핑": ["장바구니", "구매 목록"],
    "약속·데이트": ["예약 정보", "휴대용 티슈"],
    "공부·도서관": ["책·학습 자료", "필기구", "노트북·태블릿", "이어폰"],
    "나들이·피크닉": ["돗자리", "간식", "물", "쓰레기봉투"],
    "출장·외근": ["노트북·태블릿", "충전기", "업무·수업 자료", "명함", "예약·승차 정보"],
    "관공서·은행": ["신분증", "방문 업무 관련 서류", "예약 정보"],
}
WEATHERS = {
    "맑음": ["자외선 차단제"],
    "흐림": [],
    "비": ["우산", "방수 가방·커버"],
    "눈·빙판": ["미끄럼 방지 신발", "장갑", "우산"],
    "폭염·더위": ["물", "모자", "자외선 차단제", "휴대용 선풍기"],
    "한파·추위": ["겉옷", "장갑", "목도리", "핫팩"],
    "미세먼지": ["보건용 마스크"],
    "큰 일교차": ["겉옷"],
    "강한 바람": ["바람막이", "모자 고정 확인"],
}
TRANSITS = {
    "도보": ["편한 신발"],
    "대중교통": ["교통카드", "이어폰"],
    "자가용": ["차량 키", "운전면허증", "주차 정보"],
    "택시": ["목적지 주소"],
    "자전거·킥보드": ["헬멧", "안전등", "잠금장치"],
    "기차·고속버스": ["예약·승차 정보", "신분증", "보조배터리"],
    "비행기": ["신분증", "항공권·예약 정보", "수하물 규정 확인"],
}
PLACES = {
    "실내": [],
    "야외·공원": ["물", "자외선 차단제", "휴대용 티슈"],
    "산·숲": ["등산화", "물", "간식", "벌레 기피제", "보조배터리"],
    "바다·물놀이": ["수건", "여벌 옷", "방수팩", "자외선 차단제"],
    "공연·전시·경기장": ["입장권·예약 정보", "신분증"],
    "숙박": ["세면도구", "여벌 옷", "충전기", "예약 정보"],
    "해외": ["여권", "항공권·예약 정보", "해외 결제수단", "여행자보험 정보", "현지 통신수단", "변환 플러그"],
}
DURATIONS = ["잠깐 · 2시간 이내", "반나절 · 2~6시간", "하루 · 6시간 이상", "1박 이상"]
COMPANIONS = ["혼자", "아이와", "반려동물과", "어르신과"]
PRESETS = {
    "☔ 비 오는 출근길": (["출근·등교"], ["비"], ["대중교통"], ["실내"], DURATIONS[2]),
    "🏥 병원 다녀오기": (["병원·약국"], ["흐림"], ["대중교통"], ["실내"], DURATIONS[0]),
    "🌿 주말 나들이": (["나들이·피크닉"], ["맑음"], ["자가용"], ["야외·공원"], DURATIONS[1]),
    "🧳 1박 여행": (["여행·장거리"], ["흐림"], ["기차·고속버스"], ["숙박"], DURATIONS[3]),
}
CRITICAL = {"휴대폰", "결제수단", "신분증", "여권", "차량 키", "운전면허증", "개인 복용약", "교통카드"}


def item_key(name):
    return "packed_" + hashlib.sha256(name.encode("utf-8")).hexdigest()[:20]


def clean_items(raw):
    """줄바꿈/쉼표 구분, 중복 제거, 길이 및 개수 제한."""
    parts = raw.replace(",", "\n").splitlines() if isinstance(raw, str) else raw
    result = []
    for part in parts:
        if not isinstance(part, str):
            continue
        text = " ".join(part.split())[:60]
        if text and text not in result:
            result.append(text)
        if len(result) >= 80:
            break
    return result


def build_items(purposes, weathers, transits, places, duration, companions, medicine, custom):
    items = {}
    def add(names, reason, category):
        for name in names:
            if name not in items:
                items[name] = {"reasons": [], "category": category}
            if reason not in items[name]["reasons"]:
                items[name]["reasons"].append(reason)
    add(["휴대폰", "결제수단", "집 열쇠·도어락 수단"], "외출 기본", "기본 준비물")
    for chosen, rules, category in [(purposes, PURPOSES, "목적별 준비물"), (weathers, WEATHERS, "날씨·이동 준비물"), (transits, TRANSITS, "날씨·이동 준비물"), (places, PLACES, "장소·동행 준비물")]:
        for value in chosen:
            add(rules.get(value, []), value, category)
    if duration in DURATIONS[2:]:
        add(["충전기", "보조배터리", "물"], duration, "목적별 준비물")
    if duration == DURATIONS[3]:
        add(["세면도구", "여벌 옷"], "1박 이상", "목적별 준비물")
    if "아이와" in companions:
        add(["아이 간식", "물티슈", "아이 여벌 옷"], "아이와", "장소·동행 준비물")
    if "반려동물과" in companions:
        add(["목줄·하네스", "배변봉투", "반려동물 물·물그릇"], "반려동물과", "장소·동행 준비물")
    if "어르신과" in companions:
        add(["비상 연락처", "필요한 보행 보조도구"], "어르신과", "장소·동행 준비물")
    if medicine:
        add(["개인 복용약"], "복용약 챙기기 선택", "기본 준비물")
    add(clean_items(custom), "직접 등록", "개인 준비물")
    return items


def valid_url(url):
    try:
        p = urlsplit(url.strip())
        return p.scheme in ("https", "http") and bool(p.hostname) and not p.username and not p.password
    except ValueError:
        return False


def shared_url(base, config=None):
    p = urlsplit(base.strip())
    query = urlencode({"plan": json.dumps(config, ensure_ascii=False, separators=(",", ":"))}) if config else ""
    return urlunsplit((p.scheme, p.netloc, p.path or "/", query, ""))


def apply_config(config):
    for key, choices in [("purpose", PURPOSES), ("weather", WEATHERS), ("transit", TRANSITS), ("place", PLACES), ("companion", COMPANIONS)]:
        if isinstance(config.get(key), list):
            st.session_state[key] = [v for v in config[key] if isinstance(v, str) and v in choices]
    if config.get("duration") in DURATIONS:
        st.session_state.duration = config["duration"]


def reset_checks():
    for key in list(st.session_state):
        if key.startswith("packed_"):
            del st.session_state[key]
    st.session_state.pop("celebrated", None)


def use_preset(label):
    p, w, t, l, d = PRESETS[label]
    apply_config(dict(purpose=p, weather=w, transit=t, place=l, duration=d, companion=["혼자"]))
    reset_checks()


def main():
    st.set_page_config(page_title="외출 전 1분", page_icon="🎒", layout="centered")
    st.markdown('''<style>
    .stApp {background:#f7f8fc;}
    .block-container {max-width:850px;padding-top:2rem;padding-bottom:3rem;}
    h1,h2,h3 {letter-spacing:-0.04em; color:#182640;}
    .hero {padding:25px 26px;border-radius:24px;background:linear-gradient(120deg,#172b4d,#284b7b);color:white;margin-bottom:20px;}
    .hero h1 {color:white;margin:8px 0;font-size:2.25rem;}
    .hero p {color:#e2eaf6;margin:0;line-height:1.7;}
    .eyebrow {font-size:.78rem;letter-spacing:.15em;font-weight:700;color:#a8eee1;}
    div[data-testid="stMetric"] {background:white;border:1px solid #dde4ed;border-radius:16px;padding:15px;}
    .stButton button,.stDownloadButton button {border-radius:12px;min-height:44px;}
    div[data-testid="stExpander"] {background:#fff;border-radius:14px;}
    @media(max-width:600px){.block-container{padding:1.2rem 1rem 3rem;}.hero{padding:22px 18px;}.hero h1{font-size:1.9rem;}}
    </style>''', unsafe_allow_html=True)
    defaults = dict(purpose=["출근·등교"], weather=["맑음"], transit=["대중교통"], place=["실내"], duration=DURATIONS[1], companion=["혼자"], custom_items=[], medicine=False)
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value
    if not st.session_state.get("query_loaded"):
        st.session_state.query_loaded = True
        raw = st.query_params.get("plan", "")
        if raw:
            try:
                if len(raw) > 8000:
                    raise ValueError
                config = json.loads(raw)
                if not isinstance(config, dict):
                    raise ValueError
                apply_config(config)
            except (ValueError, TypeError):
                st.warning("공유 설정을 읽지 못했어요. 기본 설정으로 시작합니다.")
    st.markdown('<div class="hero"><div class="eyebrow">ONE MINUTE, READY TO GO</div><h1>🎒 외출 전 1분</h1><p>어디로 가든, 빠뜨림 없이.<br>오늘의 상황을 고르면 필요한 물건을 모아드려요.</p></div>', unsafe_allow_html=True)
    plan_tab, share_tab, help_tab = st.tabs(["✅ 오늘의 준비", "📱 QR로 공유", "💡 사용 안내"])
    with plan_tab:
        st.caption("빠른 시작 · 예시를 선택하고 내 상황에 맞게 바꿔보세요.")
        cols = st.columns(2)
        for i, label in enumerate(PRESETS):
            cols[i % 2].button(label, on_click=use_preset, args=(label,), use_container_width=True)
        st.subheader("01 · 오늘은 어떤 외출인가요?")
        st.multiselect("외출 목적 · 여러 개 선택 가능", list(PURPOSES), key="purpose")
        c1, c2 = st.columns(2)
        with c1:
            st.multiselect("날씨 조건", list(WEATHERS), key="weather", help="비+추위처럼 함께 선택하세요. 실시간 날씨 조회가 아닌 직접 선택 방식입니다.")
            st.multiselect("교통편", list(TRANSITS), key="transit")
        with c2:
            st.multiselect("장소·환경", list(PLACES), key="place")
            st.selectbox("외출 시간", DURATIONS, key="duration")
        st.multiselect("동행", COMPANIONS, key="companion")
        st.checkbox("개인 복용약을 챙겨야 해요", key="medicine")
        with st.expander("＋ 내 준비물 등록 · 백업", expanded=False):
            with st.form("personal_form", clear_on_submit=True):
                raw = st.text_area("개인 준비물", placeholder="안경, 립밤\n개인 텀블러", max_chars=5000, help="쉼표 또는 줄바꿈으로 구분하세요. 최대 80개, 항목당 60자입니다.")
                if st.form_submit_button("준비물에 추가", use_container_width=True):
                    st.session_state.custom_items = clean_items(st.session_state.custom_items + clean_items(raw))
                    st.success("개인 준비물 목록을 반영했어요.")
            st.multiselect("등록된 개인 준비물 · ×로 삭제", options=st.session_state.custom_items, default=st.session_state.custom_items, key="custom_editor_" + hashlib.md5(json.dumps(st.session_state.custom_items, ensure_ascii=False).encode()).hexdigest(), on_change=None)
            editor_key = "custom_editor_" + hashlib.md5(json.dumps(st.session_state.custom_items, ensure_ascii=False).encode()).hexdigest()
            edited = st.session_state.get(editor_key, st.session_state.custom_items)
            if edited != st.session_state.custom_items:
                st.session_state.custom_items = edited
                st.rerun()
            backup = json.dumps({"version": 1, "items": st.session_state.custom_items}, ensure_ascii=False, indent=2)
            st.download_button("개인 준비물 백업 (.json)", backup, "my_items.json", "application/json", use_container_width=True)
            uploaded = st.file_uploader("백업 복원 · JSON, 50KB 이하", type=["json"])
            if st.button("백업 준비물 합치기", disabled=uploaded is None):
                try:
                    if uploaded.size > 50000:
                        raise ValueError("파일 크기는 50KB 이하여야 합니다.")
                    data = json.loads(uploaded.getvalue().decode("utf-8-sig"))
                    if not isinstance(data, dict) or not isinstance(data.get("items"), list) or not all(isinstance(x, str) for x in data["items"]):
                        raise ValueError("items 문자열 목록이 있는 백업 파일이 필요합니다.")
                    st.session_state.custom_items = clean_items(st.session_state.custom_items + data["items"])
                    st.rerun()
                except (ValueError, UnicodeError) as exc:
                    st.error(f"복원하지 못했어요: {exc}")
            st.caption("개인 준비물과 체크 상태는 현재 세션에서 유지됩니다. 새로고침·접속 종료 시 사라질 수 있어요. 다른 기기에서는 백업을 복원하세요.")
        items = build_items(st.session_state.purpose, st.session_state.weather, st.session_state.transit, st.session_state.place, st.session_state.duration, st.session_state.companion, st.session_state.medicine, st.session_state.custom_items)
        if not st.session_state.purpose:
            st.info("외출 목적을 선택하면 더 정확한 준비물 목록을 만들 수 있어요.")
        st.subheader("02 · 가방에 넣고 체크하세요")
        st.caption("선택을 바꾸면 목록이 즉시 바뀝니다. 같은 준비물은 합치고 체크 상태는 유지해요. ★는 우선 확인 항목입니다.")
        # 체크박스가 변경된 실행에서는 session_state에 이미 최신 값이 반영됩니다.
        total = len(items)
        done = sum(bool(st.session_state.get(item_key(name), False)) for name in items)
        a, b, c = st.columns(3)
        a.metric("전체 준비물", f"{total}개")
        b.metric("챙긴 준비물", f"{done}개")
        c.metric("남은 준비물", f"{total - done}개")
        st.progress(done / total if total else 0, text=f"준비 완료 {round(done / total * 100) if total else 0}%")
        show_missing = st.toggle("아직 챙기지 않은 물건만 보기", value=False)
        st.button("↺ 체크만 모두 초기화", on_click=reset_checks)
        rendered_keys = set()
        for category in ["기본 준비물", "목적별 준비물", "날씨·이동 준비물", "장소·동행 준비물", "개인 준비물"]:
            visible = [(name, info) for name, info in items.items() if info["category"] == category and not (show_missing and st.session_state.get(item_key(name), False))]
            if visible:
                with st.container(border=True):
                    st.markdown(f"**{category}**")
                    for name, info in visible:
                        # 숨겨진 위젯도 상태가 지워지지 않도록 마지막에 별도 보존합니다.
                        st.checkbox(("★ " if name in CRITICAL else "") + name, key=item_key(name), help="추천 이유: " + " · ".join(info["reasons"]))
                        rendered_keys.add(item_key(name))
        # Streamlit은 렌더되지 않은 위젯의 상태를 정리하므로 재할당하여 보존합니다.
        for key in list(st.session_state):
            if key.startswith("packed_") and key not in rendered_keys:
                st.session_state[key] = st.session_state[key]
        remaining = [name for name in items if not st.session_state.get(item_key(name), False)]
        if not remaining:
            st.success("🎉 준비 완료! 휴대폰·결제수단·집 열쇠를 마지막으로 확인하고 출발하세요.")
        else:
            urgent = [name for name in remaining if name in CRITICAL]
            if urgent:
                st.warning("먼저 확인해요: " + ", ".join(urgent))
        if "해외" in st.session_state.place or "비행기" in st.session_state.transit:
            st.info("여권 유효기간·비자·항공사 수하물 및 보조배터리 반입 규정은 공식 안내에서 별도로 확인하세요.")
        if "병원·약국" in st.session_state.purpose:
            st.caption("진료 서류와 본인확인 수단은 방문 기관에 따라 다릅니다. 예약 안내를 확인하세요.")
        text = "외출 전 1분 · 준비물\n" + " / ".join(st.session_state.purpose) + "\n\n" + "\n".join(("[✓] " if st.session_state.get(item_key(n), False) else "[ ] ") + n for n in items)
        st.download_button("↓ 현재 체크리스트 저장 (.txt)", text.encode("utf-8-sig"), "outing_checklist.txt", "text/plain", use_container_width=True)
        with st.expander("03 · 문 닫기 전 10초 확인"):
            st.write("가스·전열기구 끄기 → 창문·문 잠금 → 휴대폰 배터리 → 목적지·예약 시간 확인")
            st.caption("준비물 추천은 참고용입니다. 안전·건강 및 기관별 필수 요건을 보장하지 않습니다.")
    with share_tab:
        st.subheader("스캔하면 바로, 외출 준비")
        st.write("앱을 먼저 배포한 뒤 실제 접속 주소를 입력하면 QR 이미지를 만들 수 있어요. 카메라로 스캔하면 설치 없이 브라우저에서 열립니다.")
        base = st.text_input("배포한 앱 주소", placeholder="https://내앱이름.streamlit.app", max_chars=500)
        include_plan = st.checkbox("현재 상황 선택도 함께 공유", value=True, help="목적·날씨·교통·장소·시간·동행만 공유합니다. 개인 준비물, 복용약 선택, 체크 상태는 포함하지 않습니다.")
        if base:
            if not valid_url(base):
                st.error("http:// 또는 https://로 시작하는 올바른 앱 주소를 입력하세요.")
            else:
                config = {k: st.session_state[k] for k in ["purpose", "weather", "transit", "place", "duration", "companion"]} if include_plan else None
                url = shared_url(base, config)
                try:
                    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=9, border=4)
                    qr.add_data(url)
                    qr.make(fit=True)
                    image = qr.make_image(fill_color="#172b4d", back_color="white")
                    buf = io.BytesIO()
                    image.save(buf, format="PNG")
                    st.image(buf.getvalue(), width=280, caption="휴대폰 기본 카메라로 스캔하세요")
                    st.download_button("QR 이미지 다운로드", buf.getvalue(), "outing_qr.png", "image/png", use_container_width=True)
                    st.link_button("공유 주소 열기", url, use_container_width=True)
                    st.code(url, language=None)
                    st.caption("접근 권한이 제한된 앱은 스캔 후 로그인이 필요합니다. 인쇄 전 다른 휴대폰에서 테스트하세요. 상황을 바꾸면 QR을 다시 다운로드하세요.")
                except qrcode.exceptions.DataOverflowError:
                    st.error("공유할 선택이 너무 많습니다. 상황 공유를 끄거나 선택을 줄여주세요.")
    with help_tab:
        st.subheader("사용은 간단하게")
        st.markdown("1. **상황 선택** — 목적·날씨·교통편·장소를 복수 선택합니다.\n2. **내 물건 추가** — 안경, 렌즈 등 개인 준비물을 등록합니다.\n3. **넣고 체크** — 추천 이유를 참고해 실제로 챙긴 물건을 체크합니다.\n4. **출발** — 남은 물건과 문단속을 확인합니다.")
        st.subheader("GitHub → 웹 앱 → QR")
        st.markdown("1. GitHub 저장소의 같은 폴더에 `app.py`, `requirements.txt`를 올립니다.\n2. Streamlit Community Cloud에서 GitHub를 연결하고 저장소·브랜치·`app.py`를 선택해 배포합니다.\n3. 배포된 앱의 주소를 **QR로 공유** 탭에 넣습니다.\n4. QR 이미지를 다운로드해 안내문 등에 사용합니다.")
        st.code("pip install -r requirements.txt\nstreamlit run app.py", language="bash")
        st.info("GitHub에 파일을 올리는 것만으로 Python 앱이 실행되지는 않습니다. Streamlit 등 앱 실행 서비스가 필요하며, GitHub Pages에서는 직접 실행할 수 없습니다.")
        st.caption("API 키·외부 날씨 서비스·회원가입 없이 동작합니다. QR은 앱 접속 링크이며 QR 스캔 자체가 준비물을 인식하는 기능은 아닙니다. 서버 재시작·브라우저 새로고침 시 세션 정보는 초기화될 수 있습니다.")
    st.caption("외출 전 1분 · 가볍게 챙기고, 편하게 출발하세요.")


if __name__ == "__main__":
    main()
