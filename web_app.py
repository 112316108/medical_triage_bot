# ============================================================
# web_app.py  ─  醫療分診機器人網頁版（Gradio）
# 負責人：112316108
# 說明：與桌面版（triage_bot.py）共用 prompts.py 與 knowledge_base.json，
#       可在本機執行，或部署到 Hugging Face Spaces 讓評審直接操作
# 執行：python web_app.py  → 瀏覽器開啟 http://127.0.0.1:7860
# ============================================================

import json
import os
import re
import tempfile
import threading
import time
from collections import deque
from datetime import datetime

import gradio as gr
from dotenv import load_dotenv
from groq import Groq

from prompts import (SYSTEM_PROMPT, SYSTEM_PROMPT_EN,
                     SYSTEM_PROMPT_SIMPLE, SYSTEM_PROMPT_SIMPLE_EN, DISCLAIMER_TEXT)
from evaluation.evaluate import parse_light

load_dotenv()

HERE = os.path.dirname(os.path.abspath(__file__))
MODEL = os.getenv("GROQ_MODEL", "qwen/qwen3.8-27b")

# ── 公開網址的使用限制（避免 API 額度被用光）──────────────────
MAX_INPUT_CHARS = 500        # 單則訊息字數上限
MAX_TURNS = 15               # 每個瀏覽器分頁的對話輪數上限
GLOBAL_PER_MINUTE = 20       # 全站每分鐘 API 呼叫上限

_recent_calls = deque()
_rate_lock = threading.Lock()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

with open(os.path.join(HERE, "knowledge_base.json"), encoding="utf-8") as f:
    KB = json.load(f)

SYMPTOMS = {
    "zh": ["🤕 頭痛", "🌡 發燒", "💔 胸痛", "🤢 腹痛", "😷 咳嗽", "🦴 外傷", "😵 頭暈", "🤮 噁心"],
    "en": ["🤕 Headache", "🌡 Fever", "💔 Chest Pain", "🤢 Abdominal Pain",
           "😷 Cough", "🦴 Injury", "😵 Dizziness", "🤮 Nausea"],
}

TEXT = {
    "zh": {
        "kb": "📚 來自知識庫",
        "too_long": f"⚠️ 訊息過長，請精簡在 {MAX_INPUT_CHARS} 字以內。",
        "turn_limit": f"⚠️ 本次對話已達 {MAX_TURNS} 輪上限，請按「清除對話」重新開始。",
        "busy": "⚠️ 目前使用人數較多，請約一分鐘後再試。",
        "error": "⚠️ 連線失敗：{err}",
        "not_agreed": "請先閱讀上方免責聲明並勾選同意。",
        "badge_none": "尚未評估",
        "lights": {"red": "🔴 紅燈｜立即就醫", "yellow": "🟡 黃燈｜優先處理",
                   "green": "🟢 綠燈｜一般門診"},
        "you": "您", "ai": "分診 AI",
    },
    "en": {
        "kb": "📚 From knowledge base",
        "too_long": f"⚠️ Message too long. Please keep it under {MAX_INPUT_CHARS} characters.",
        "turn_limit": f"⚠️ This chat reached the {MAX_TURNS}-turn limit. Press \"Clear\" to start over.",
        "busy": "⚠️ Too many requests right now. Please try again in a minute.",
        "error": "⚠️ Connection failed: {err}",
        "not_agreed": "Please read the disclaimer above and tick the checkbox first.",
        "badge_none": "Not assessed yet",
        "lights": {"red": "🔴 Red · Seek care immediately", "yellow": "🟡 Yellow · Urgent",
                   "green": "🟢 Green · Regular clinic"},
        "you": "You", "ai": "Triage AI",
    },
}


# ── 小工具 ───────────────────────────────────────────────────

def _lang(choice: str) -> str:
    return "en" if choice == "English" else "zh"


def _allow_call() -> bool:
    """全站速率限制：一分鐘內呼叫次數超過上限就拒絕"""
    now = time.time()
    with _rate_lock:
        while _recent_calls and now - _recent_calls[0] > 60:
            _recent_calls.popleft()
        if len(_recent_calls) >= GLOBAL_PER_MINUTE:
            return False
        _recent_calls.append(now)
        return True


NEGATION = re.compile(
    r"(沒有|沒|無|不|未|否認)[^，,。；;、\s但可而卻還]{0,4}"
    r"|\b(no|not|without|denies?)\s+[a-z]+(\s+[a-z]+)?", re.I)


def _strip_negated(text: str) -> str:
    """刪掉被否定的片段（例：「沒有發燒」「no fever」），避免知識庫誤命中"""
    return NEGATION.sub(" ", text)


def search_kb(text: str, lang: str):
    """與桌面版相同的關鍵字比對，命中分數最高的條目"""
    text_lower = _strip_negated(text.lower())
    best, best_score = None, 0
    for entry in KB.get(lang, []):
        score = sum(1 for kw in entry.get("keywords", []) if kw.lower() in text_lower)
        if score > best_score:
            best_score, best = score, entry
    return best if best_score >= 1 else None


def system_prompt(lang, mode, age, gender, conditions, medications):
    if lang == "en":
        base = SYSTEM_PROMPT_SIMPLE_EN if mode == "simple" else SYSTEM_PROMPT_EN
        header, labels = "[Patient Information]", ["Age", "Gender", "Chronic Conditions", "Current Medications"]
    else:
        base = SYSTEM_PROMPT_SIMPLE if mode == "simple" else SYSTEM_PROMPT
        header, labels = "【病患基本資料】", ["年齡", "性別", "慢性病史", "目前用藥"]
    profile = [f"{l}：{v}" for l, v in zip(labels, [age, gender, conditions, medications]) if v]
    return base + ("\n\n" + "\n".join([header] + profile) if profile else "")


def badge_html(light, lang):
    t = TEXT[lang]
    label = t["lights"][light] if light else t["badge_none"]
    return f'<div class="badge badge-{light or "none"}">{label}</div>'


def to_chatbot(history):
    return [{"role": m["role"], "content": m.get("display", m["content"])} for m in history]


# ── 主要對話流程 ─────────────────────────────────────────────

def respond(message, history, lang_choice, mode_choice, age, gender, conditions, medications, agreed):
    lang = _lang(lang_choice)
    mode = "simple" if mode_choice in ("簡易模式", "Simple") else "pro"
    t = TEXT[lang]
    message = (message or "").strip()
    last_light = next((parse_light(m["content"]) for m in reversed(history)
                       if m["role"] == "assistant" and parse_light(m["content"])), None)

    def notice(text):
        shown = history + [{"role": "assistant", "content": text, "display": text, "notice": True}]
        return to_chatbot(shown), history, badge_html(last_light, lang), message

    if not agreed:
        yield notice(t["not_agreed"]); return
    if not message:
        return
    if len(message) > MAX_INPUT_CHARS:
        yield notice(t["too_long"]); return
    if sum(m["role"] == "user" for m in history) >= MAX_TURNS:
        yield notice(t["turn_limit"]); return

    history = history + [{"role": "user", "content": message}]

    # 優先查詢本地知識庫（與桌面版行為一致）
    kb = search_kb(message, lang)
    if kb:
        reply = kb["answer"]
        history.append({"role": "assistant", "content": reply, "display": f"{reply}\n\n*{t['kb']}*"})
        yield to_chatbot(history), history, badge_html(parse_light(reply) or last_light, lang), ""
        return

    if not _allow_call():
        history.append({"role": "assistant", "content": t["busy"], "display": t["busy"], "notice": True})
        yield to_chatbot(history), history[:-2], badge_html(last_light, lang), message
        return

    messages = [{"role": "system", "content": system_prompt(lang, mode, age, gender, conditions, medications)}]
    messages += [{"role": m["role"], "content": m["content"]} for m in history if not m.get("notice")]
    history.append({"role": "assistant", "content": ""})
    try:
        stream = client.chat.completions.create(
            model=MODEL, messages=messages, max_tokens=1024, temperature=0.4, stream=True)
        reply = ""
        for chunk in stream:
            reply += chunk.choices[0].delta.content or ""
            clean = re.sub(r"<think>.*?(</think>|$)", "", reply, flags=re.S).strip()
            history[-1] = {"role": "assistant", "content": clean}
            yield to_chatbot(history), history, badge_html(parse_light(clean) or last_light, lang), ""
    except Exception as e:
        err = t["error"].format(err=e)
        history[-1] = {"role": "assistant", "content": err, "display": err, "notice": True}
        yield to_chatbot(history), history, badge_html(last_light, lang), ""


def export_txt(history, lang_choice):
    """把對話存成文字檔供下載（網頁版以 .txt 取代桌面版的 PDF 匯出）"""
    t = TEXT[_lang(lang_choice)]
    lines = [f"醫療分診機器人 對話紀錄  {datetime.now():%Y-%m-%d %H:%M}", "=" * 40, ""]
    for m in history:
        if m.get("notice"):
            continue
        lines += [f"【{t['you'] if m['role'] == 'user' else t['ai']}】", m["content"], ""]
    lines += ["-" * 40, "⚕️ 本評估僅供參考，不能替代正式醫療診斷。"]
    path = os.path.join(tempfile.gettempdir(), f"triage_{datetime.now():%Y%m%d_%H%M%S}.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return gr.update(value=path, visible=True)


def switch_language(lang_choice):
    lang = _lang(lang_choice)
    return [gr.update(value=s) for s in SYMPTOMS[lang]] + [badge_html(None, lang)]


def add_symptom(current, sym):
    word = sym.split(" ", 1)[1] if " " in sym else sym
    current = (current or "").strip()
    return f"{current}、{word}" if current else word


# ── 介面 ─────────────────────────────────────────────────────

CSS = """
.header {background:#00838F; color:#fff; padding:18px 22px; border-radius:12px;}
.header h1 {margin:0; font-size:1.6em; color:#fff;}
.header p {margin:4px 0 0; color:#B2EBF2;}
.disclaimer {background:#FFF8E1; border-left:5px solid #F9A825; padding:10px 16px;
             border-radius:8px; white-space:pre-line; font-size:0.92em;}
.badge {padding:14px; border-radius:10px; font-size:1.25em; font-weight:700; text-align:center;}
.badge-red {background:#FFEBEE; color:#C62828; border:2px solid #E53935;}
.badge-yellow {background:#FFF8E1; color:#8D6E00; border:2px solid #F9A825;}
.badge-green {background:#E8F5E9; color:#1B5E20; border:2px solid #388E3C;}
.badge-none {background:#ECEFF1; color:#546E7A; border:2px dashed #90A4AE;}
"""

with gr.Blocks(title="醫療分診機器人 Medical Triage Bot") as demo:
    gr.HTML('<div class="header"><h1>🏥 醫療分診機器人 Medical Triage Bot</h1>'
            '<p>描述您的症狀，AI 依緊急程度給出 🔴🟡🟢 燈號與建議科別</p></div>')
    gr.HTML(f'<div class="disclaimer">{DISCLAIMER_TEXT.replace("點擊「我已了解，繼續使用」", "勾選下方方框")}</div>')
    agreed = gr.Checkbox(label="我已閱讀並同意以上免責聲明 / I have read and agree to the disclaimer", value=False)

    history = gr.State([])

    with gr.Row():
        with gr.Column(scale=3):
            chatbot = gr.Chatbot(label="對話", height=480)
            with gr.Row():
                sym_btns = [gr.Button(s, size="sm", min_width=60) for s in SYMPTOMS["zh"]]
            with gr.Row():
                msg = gr.Textbox(placeholder="請描述您的症狀，例如：昨天開始發燒 38.5 度，喉嚨很痛…",
                                 show_label=False, scale=5, lines=2, max_lines=5)
                send = gr.Button("傳送 ▶", variant="primary", scale=1)
            with gr.Row():
                clear = gr.Button("🗑 清除對話", size="sm")
                download = gr.Button("📄 下載對話紀錄", size="sm")
            file_out = gr.File(label="對話紀錄", visible=False)

        with gr.Column(scale=1, min_width=260):
            gr.Markdown("### 目前評估")
            badge = gr.HTML(badge_html(None, "zh"))
            lang = gr.Radio(["中文", "English"], value="中文", label="語言 Language")
            mode = gr.Radio(["專業模式", "簡易模式"], value="專業模式", label="回答模式",
                            info="簡易模式用白話文回答")
            with gr.Accordion("👤 病患基本資料（選填）", open=False):
                age = gr.Textbox(label="年齡")
                gender = gr.Dropdown(["", "男", "女", "其他"], label="性別")
                conditions = gr.Textbox(label="慢性病史")
                medications = gr.Textbox(label="目前用藥")
            gr.Markdown(
                f"<small>模型：`{MODEL}`（via Groq）<br>"
                "分診準確度評估見 [GitHub](https://github.com/112316108/medical_triage_bot)<br>"
                "🚨 緊急狀況請直接撥打 <b>119</b></small>")

    inputs = [msg, history, lang, mode, age, gender, conditions, medications, agreed]
    outputs = [chatbot, history, badge, msg]
    send.click(respond, inputs, outputs)
    msg.submit(respond, inputs, outputs)
    for b in sym_btns:
        b.click(add_symptom, [msg, b], msg)
    clear.click(lambda l: ([], [], badge_html(None, _lang(l)), gr.update(visible=False)),
                [lang], [chatbot, history, badge, file_out])
    download.click(export_txt, [history, lang], file_out)
    lang.change(switch_language, [lang], sym_btns + [badge])


if __name__ == "__main__":
    demo.queue(default_concurrency_limit=4).launch(
        css=CSS, theme=gr.themes.Soft(primary_hue="teal"))
