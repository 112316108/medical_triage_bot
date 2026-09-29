# ============================================================
# triage_bot.py  ─  醫療分診機器人主程式
# 負責人：A 同學
# 說明：tkinter 聊天介面 + Groq API 呼叫 + 對話歷史管理
# 使用模型：llama-3.3-70b-versatile（via Groq）
# ============================================================

import os
import glob
import json
import threading
from datetime import datetime

import tkinter as tk
from tkinter import messagebox
from groq import Groq
from dotenv import load_dotenv

from prompts import (SYSTEM_PROMPT, SYSTEM_PROMPT_EN,
                     SYSTEM_PROMPT_SIMPLE, SYSTEM_PROMPT_SIMPLE_EN,
                     DISCLAIMER_TEXT, SUMMARY_ZH, SUMMARY_EN)
from utils import export_to_pdf, save_conversation, load_conversation

# 載入 .env 中的 API Key
load_dotenv()


# ══════════════════════════════════════════════════════════════
# 色彩主題（醫療藍綠色系）
# ══════════════════════════════════════════════════════════════
C = {
    "header_bg":   "#00838F",  # 標題列背景：深青綠
    "header_fg":   "#FFFFFF",  # 標題列文字：白
    "header_sub":  "#B2EBF2",  # 標題副文字：淺青
    "app_bg":      "#E0F7FA",  # 主視窗背景：極淺青
    "chat_bg":     "#F5FDFE",  # 聊天區背景
    "input_bg":    "#FFFFFF",  # 輸入框背景：白
    "border":      "#00838F",  # 邊框色
    "user_row":    "#B2EBF2",  # 使用者訊息列背景
    "ai_row":      "#E8F5E9",  # AI 訊息列背景
    "text_dark":   "#00363A",  # 主要文字：深青黑
    "text_user":   "#006064",  # 使用者標籤顏色
    "text_ai":     "#1B5E20",  # AI 標籤顏色
    "text_hint":   "#78909C",  # 提示文字：藍灰
    "sep":         "#80DEEA",  # 訊息分隔線
    "ts":          "#90A4AE",  # 時間戳
    "thinking":    "#546E7A",  # AI 思考中文字
    "red":         "#E53935",  # 紅燈
    "yellow":      "#F9A825",  # 黃燈
    "green":       "#388E3C",  # 綠燈
    "btn_send":    "#00838F",  # 傳送鈕
    "btn_export":  "#00695C",  # 匯出鈕
    "btn_clear":   "#78909C",  # 清除鈕
    "status_ok":   "#80CBC4",  # 狀態：待機
    "status_busy": "#FFB300",  # 狀態：思考中
    "status_err":  "#E53935",  # 狀態：錯誤
}

FONT = "Microsoft JhengHei"   # 主字型（繁體中文）

# 症狀快捷按鈕清單（中英文各一份）
SYMPTOMS = {
    "zh": ["🤕 頭痛", "🌡 發燒", "💔 胸痛", "🤢 腹痛", "😷 咳嗽", "🦴 外傷", "😵 頭暈", "🤮 噁心"],
    "en": ["🤕 Headache", "🌡 Fever", "💔 Chest Pain", "🤢 Abdominal Pain",
           "😷 Cough", "🦴 Injury", "😵 Dizziness", "🤮 Nausea"],
}

# 所有 UI 文字的中英對照表
UI = {
    "zh": {
        "title":          "醫療分診助理 AI",
        "status_ok":      "● 待機中",
        "status_busy":    "● AI 思考中…",
        "status_summary": "● 產生摘要中…",
        "status_err":     "● 連線錯誤",
        "hint":           "Enter 傳送  ·  Shift+Enter 換行  ·  請描述您的症狀",
        "quick":          "快捷：",
        "send":           "傳送\n▶",
        "btn_export":     "📄 匯出 PDF",
        "btn_clear":      "🗑 清除對話",
        "btn_save":       "💾 儲存對話",
        "btn_load":       "📂 載入對話",
        "btn_summary":    "📋 對話摘要",
        "mode_pro":       "⚕️ 專業模式",
        "mode_simple":    "💬 簡易模式",
        "lang_btn":       "🌐 English",
        "count":          "對話輪數：{n}",
        "user_lbl":       "👤 您",
        "ai_lbl":         "🤖 分診護理師 AI",
        "thinking":       "⏳ AI 分析中，請稍候…",
        "btn_profile":    "👤 病患資料",
        "btn_history":    "📚 歷史紀錄",
        "mic_idle":       "🎤",
        "mic_rec":        "⏹",
        "status_rec":     "● 錄音中…",
    },
    "en": {
        "title":          "Medical Triage Assistant AI",
        "status_ok":      "● Standby",
        "status_busy":    "● AI Thinking…",
        "status_summary": "● Generating Summary…",
        "status_err":     "● Connection Error",
        "hint":           "Enter to send  ·  Shift+Enter for newline  ·  Describe your symptoms",
        "quick":          "Quick:",
        "send":           "Send\n▶",
        "btn_export":     "📄 Export PDF",
        "btn_clear":      "🗑 Clear Chat",
        "btn_save":       "💾 Save Chat",
        "btn_load":       "📂 Load Chat",
        "btn_summary":    "📋 Summary",
        "mode_pro":       "⚕️ Pro Mode",
        "mode_simple":    "💬 Simple Mode",
        "lang_btn":       "🌐 中文",
        "count":          "Turns: {n}",
        "user_lbl":       "👤 You",
        "ai_lbl":         "🤖 Triage AI",
        "thinking":       "⏳ Analyzing, please wait…",
        "btn_profile":    "👤 Patient Info",
        "btn_history":    "📚 History",
        "mic_idle":       "🎤",
        "mic_rec":        "⏹",
        "status_rec":     "● Recording…",
    },
}


# ══════════════════════════════════════════════════════════════
# 主應用程式類別
# ══════════════════════════════════════════════════════════════

class TriageBotApp:
    """醫療分診機器人 tkinter 應用程式"""

    def __init__(self, root: tk.Tk):
        self.root = root
        self.conversation_history: list = []  # 完整對話歷史（含 system）
        self.is_waiting = False               # 是否正在等待 AI 回應
        self.lang = "zh"                      # 目前介面語言（zh / en）
        self.font_size = 12                   # 聊天文字字體大小
        self.mode = "pro"                     # 回覆模式（pro 專業 / simple 簡易）
        self.patient_profile: dict = {}       # 病患基本資料（注入 system prompt）

        # ── 初始化 Groq 客戶端 ────────────────────────────────
        api_key = os.getenv("GROQ_API_KEY", "")
        if not api_key or api_key == "gsk_xxxxx":
            messagebox.showerror(
                "API Key 錯誤",
                "請先在 .env 檔案中填入有效的 GROQ_API_KEY，再重新執行程式。"
            )
            self.root.destroy()
            return

        self.client = Groq(api_key=api_key)

        # 對話歷史第一筆固定為 system prompt
        self.conversation_history.append({
            "role": "system",
            "content": SYSTEM_PROMPT,
        })

        # ── 建立 UI ───────────────────────────────────────────
        self._setup_window()
        self._show_disclaimer()   # 啟動時強制顯示免責聲明
        self._build_ui()
        self._show_welcome()      # 聊天區顯示歡迎訊息

    # ──────────────────────────────────────────────────────────
    # 視窗設定
    # ──────────────────────────────────────────────────────────

    def _setup_window(self):
        """設定主視窗大小、標題、背景與置中位置"""
        self.root.title("🏥 醫療分診助理 AI")
        self.root.geometry("860x720")
        self.root.minsize(700, 560)
        self.root.configure(bg=C["app_bg"])
        # 視窗置中顯示
        self.root.update_idletasks()
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        x  = (sw - 860) // 2
        y  = (sh - 720) // 2
        self.root.geometry(f"860x720+{x}+{y}")

    # ──────────────────────────────────────────────────────────
    # 免責聲明對話框
    # ──────────────────────────────────────────────────────────

    def _show_disclaimer(self):
        """
        啟動時彈出免責聲明視窗（強制置頂）。
        使用者點「我已了解」才能繼續；點「離開」則結束程式。
        """
        W, H = 520, 440
        dlg = tk.Toplevel(self.root)
        dlg.title("使用前請閱讀免責聲明")
        dlg.resizable(False, False)
        dlg.configure(bg="#FFFFFF")
        dlg.grab_set()        # 鎖定焦點（強制使用者先處理）
        dlg.transient(self.root)

        # 置中（先設定尺寸再計算位置）
        dlg.update_idletasks()
        x = (dlg.winfo_screenwidth()  - W) // 2
        y = (dlg.winfo_screenheight() - H) // 2
        dlg.geometry(f"{W}x{H}+{x}+{y}")

        # 標題
        tk.Label(
            dlg, text="⚕️  醫療免責聲明",
            font=(FONT, 15, "bold"),
            fg=C["header_bg"], bg="#FFFFFF"
        ).pack(pady=(18, 8))

        # 按鈕列先 pack（side="bottom"），確保永遠可見不被文字框擠掉
        btn_row = tk.Frame(dlg, bg="#FFFFFF")
        btn_row.pack(side="bottom", pady=14)

        # 聲明文字區（唯讀，含捲軸）
        frame = tk.Frame(dlg, bg="#F5F5F5", relief="groove", bd=1)
        frame.pack(padx=22, fill="both", expand=True, pady=(0, 4))

        txt = tk.Text(
            frame,
            font=(FONT, 11), wrap="word",
            bg="#F5F5F5", fg=C["text_dark"],
            relief="flat", padx=14, pady=10,
            state="normal"
        )
        txt.insert("1.0", DISCLAIMER_TEXT)
        txt.config(state="disabled")
        txt.pack(fill="both", expand=True)

        def on_agree():
            dlg.destroy()

        def on_decline():
            self.root.destroy()

        tk.Button(
            btn_row, text="  ✔  我已了解，繼續使用  ",
            font=(FONT, 11, "bold"),
            bg=C["header_bg"], fg="#FFFFFF",
            activebackground=C["btn_export"],
            relief="flat", cursor="hand2",
            padx=8, pady=6,
            command=on_agree
        ).pack(side="left", padx=8)

        tk.Button(
            btn_row, text="  ✘  離開  ",
            font=(FONT, 11),
            bg=C["btn_clear"], fg="#FFFFFF",
            relief="flat", cursor="hand2",
            padx=8, pady=6,
            command=on_decline
        ).pack(side="left", padx=8)

        dlg.protocol("WM_DELETE_WINDOW", on_decline)
        self.root.wait_window(dlg)  # 阻塞直到對話框關閉

    # ──────────────────────────────────────────────────────────
    # UI 建構
    # ──────────────────────────────────────────────────────────

    def _build_ui(self):
        """依序建立標題列、聊天區、症狀列、輸入區、底部工具列"""
        self._build_header()
        self._build_chat_area()
        self._build_symptom_bar()   # 症狀快捷按鈕
        self._build_input_area()
        self._build_bottom_bar()

    def _build_header(self):
        """標題列：LOGO 圖示 + 系統名稱 + 狀態燈號"""
        header = tk.Frame(self.root, bg=C["header_bg"], height=70)
        header.pack(fill="x")
        header.pack_propagate(False)

        # 左側圖示區
        left = tk.Frame(header, bg=C["header_bg"])
        left.pack(side="left", padx=18, fill="y")

        tk.Label(left, text="🏥", font=("Segoe UI Emoji", 26),
                 bg=C["header_bg"], fg="#FFFFFF").pack(side="left", padx=(0, 10))

        name_col = tk.Frame(left, bg=C["header_bg"])
        name_col.pack(side="left")

        self.title_lbl = tk.Label(name_col, text=UI["zh"]["title"],
                 font=(FONT, 17, "bold"),
                 bg=C["header_bg"], fg="#FFFFFF")
        self.title_lbl.pack(anchor="w")

        tk.Label(name_col,
                 text="Medical Triage Assistant  ·  Groq Llama-3.3-70b",
                 font=(FONT, 9), bg=C["header_bg"], fg=C["header_sub"]).pack(anchor="w")

        # 右側狀態燈
        self.status_lbl = tk.Label(
            header, text="● 待機中",
            font=(FONT, 10), bg=C["header_bg"], fg=C["status_ok"]
        )
        self.status_lbl.pack(side="right", padx=20)

    def _build_chat_area(self):
        """聊天顯示區：唯讀 Text 元件 + 右側捲軸"""
        outer = tk.Frame(self.root, bg=C["app_bg"])
        outer.pack(fill="both", expand=True, padx=14, pady=(10, 0))

        self.chat = tk.Text(
            outer,
            wrap="word",
            font=(FONT, 12),
            bg=C["chat_bg"], fg=C["text_dark"],
            relief="flat",
            padx=10, pady=6,
            spacing3=3,
            selectbackground="#4DD0E1",          # 反白背景色
            selectforeground="#FFFFFF",          # 反白文字色
            inactiveselectbackground="#4DD0E1",  # 失焦時仍保持反白可見
        )
        # 保持 normal 讓滑鼠可框選，但封鎖鍵盤修改
        self.chat.bind("<Key>", self._block_chat_edit)
        sb = tk.Scrollbar(outer, command=self.chat.yview, bg=C["app_bg"])
        self.chat.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.chat.pack(fill="both", expand=True)
        # 右鍵選單：複製功能
        self.chat.bind("<Button-3>", self._show_context_menu)

        # ── 定義文字樣式標籤 ──────────────────────────────────
        self.chat.tag_configure("user_lbl",
            foreground=C["text_user"], font=(FONT, 11, "bold"))
        self.chat.tag_configure("user_msg",
            foreground=C["text_dark"], font=(FONT, 12),
            lmargin1=16, lmargin2=16, background=C["user_row"])
        self.chat.tag_configure("ai_lbl",
            foreground=C["text_ai"], font=(FONT, 11, "bold"))
        self.chat.tag_configure("ai_msg",
            foreground=C["text_dark"], font=(FONT, 12),
            lmargin1=16, lmargin2=16, background=C["ai_row"])
        self.chat.tag_configure("ts",
            foreground=C["ts"], font=(FONT, 9))
        self.chat.tag_configure("sep",
            foreground=C["sep"], font=(FONT, 8))
        self.chat.tag_configure("thinking",
            foreground=C["thinking"], font=(FONT, 11, "italic"))
        # 緊急燈號標籤（文字會用對應顏色顯示）
        self.chat.tag_configure("red_line",
            foreground=C["red"], font=(FONT, 12, "bold"),
            lmargin1=16, lmargin2=16, background=C["ai_row"])
        self.chat.tag_configure("yellow_line",
            foreground=C["yellow"], font=(FONT, 12, "bold"),
            lmargin1=16, lmargin2=16, background=C["ai_row"])
        self.chat.tag_configure("green_line",
            foreground=C["green"], font=(FONT, 12, "bold"),
            lmargin1=16, lmargin2=16, background=C["ai_row"])

        self.chat.tag_configure("kb_badge",
            foreground="#5C6BC0", font=(FONT, 9, "italic"),
            lmargin1=16, lmargin2=16)

        # 讓內建 sel tag 畫在所有自訂 tag 之上，才能正確顯示反白
        self.chat.tag_raise("sel")

    def _build_input_area(self):
        """輸入區：多行文字框 + 傳送按鈕（Enter 傳送，Shift+Enter 換行）"""
        # 帶邊框的容器
        wrapper = tk.Frame(self.root, bg=C["border"], pady=2)
        wrapper.pack(fill="x", padx=14, pady=(8, 2))

        inner = tk.Frame(wrapper, bg=C["input_bg"])
        inner.pack(fill="x")

        self.input_box = tk.Text(
            inner, height=3,
            font=(FONT, 12),
            bg=C["input_bg"], fg=C["text_dark"],
            relief="flat", padx=12, pady=8,
            wrap="word",
            insertbackground=C["header_bg"],  # 游標顏色
        )
        self.input_box.pack(side="left", fill="both", expand=True)
        self.input_box.bind("<Return>",       self._on_enter)
        self.input_box.bind("<Shift-Return>", lambda e: None)  # 換行不攔截

        self.send_btn = tk.Button(
            inner, text=UI["zh"]["send"],
            font=(FONT, 11, "bold"),
            bg=C["btn_send"], fg="#FFFFFF",
            activebackground=C["btn_export"],
            relief="flat", cursor="hand2", width=6,
            command=self._send_message
        )
        self.send_btn.pack(side="right", fill="y", padx=3, pady=3)

        self.mic_btn = tk.Button(
            inner, text=UI["zh"]["mic_idle"],
            font=("Segoe UI Emoji", 14),
            bg=C["input_bg"], fg=C["header_bg"],
            activebackground=C["user_row"],
            relief="flat", cursor="hand2", width=3,
            command=self._voice_input
        )
        self.mic_btn.pack(side="right", fill="y", pady=3)

        # 快捷鍵提示
        self.hint_lbl = tk.Label(
            self.root, text=UI["zh"]["hint"],
            font=(FONT, 9), bg=C["app_bg"], fg=C["text_hint"]
        )
        self.hint_lbl.pack()

    def _build_bottom_bar(self):
        """底部工具列（兩行）"""
        # ── 第一行：原有功能 ──────────────────────────────────
        bar1 = tk.Frame(self.root, bg=C["app_bg"])
        bar1.pack(fill="x", padx=14, pady=(4, 2))

        self.export_btn = tk.Button(
            bar1, text=UI["zh"]["btn_export"],
            font=(FONT, 10), bg=C["btn_export"], fg="#FFFFFF",
            activebackground="#004D40",
            relief="flat", cursor="hand2", padx=10, pady=5,
            command=self._export_pdf
        )
        self.export_btn.pack(side="left", padx=(0, 8))

        self.clear_btn = tk.Button(
            bar1, text=UI["zh"]["btn_clear"],
            font=(FONT, 10), bg=C["btn_clear"], fg="#FFFFFF",
            activebackground="#546E7A",
            relief="flat", cursor="hand2", padx=10, pady=5,
            command=self._clear_chat
        )
        self.clear_btn.pack(side="left", padx=(0, 16))

        # 字體大小：A-  12pt  A+
        tk.Button(bar1, text="A-", font=(FONT, 10), bg=C["app_bg"], fg=C["text_dark"],
                  relief="groove", cursor="hand2", padx=6, pady=4,
                  command=lambda: self._change_font_size(-1)).pack(side="left")

        self.size_lbl = tk.Label(bar1, text=f"{self.font_size}pt",
                                  font=(FONT, 9), bg=C["app_bg"], fg=C["text_hint"], width=4)
        self.size_lbl.pack(side="left")

        tk.Button(bar1, text="A+", font=(FONT, 10), bg=C["app_bg"], fg=C["text_dark"],
                  relief="groove", cursor="hand2", padx=6, pady=4,
                  command=lambda: self._change_font_size(1)).pack(side="left", padx=(0, 12))

        # 語言切換
        self.lang_btn = tk.Button(
            bar1, text="🌐 English",
            font=(FONT, 10), bg=C["header_bg"], fg="#FFFFFF",
            activebackground="#006064",
            relief="flat", cursor="hand2", padx=10, pady=5,
            command=self._toggle_language
        )
        self.lang_btn.pack(side="left")

        # 對話輪數（靠右）
        self.count_lbl = tk.Label(bar1, text="對話輪數：0",
                                   font=(FONT, 9), bg=C["app_bg"], fg=C["text_hint"])
        self.count_lbl.pack(side="right")

        # ── 第二行：中等功能 ──────────────────────────────────
        bar2 = tk.Frame(self.root, bg=C["app_bg"])
        bar2.pack(fill="x", padx=14, pady=(0, 10))

        self.save_btn = tk.Button(
            bar2, text=UI["zh"]["btn_save"],
            font=(FONT, 10), bg="#00695C", fg="#FFFFFF",
            activebackground="#004D40",
            relief="flat", cursor="hand2", padx=10, pady=5,
            command=self._save_chat
        )
        self.save_btn.pack(side="left", padx=(0, 8))

        self.load_btn = tk.Button(
            bar2, text=UI["zh"]["btn_load"],
            font=(FONT, 10), bg="#00695C", fg="#FFFFFF",
            activebackground="#004D40",
            relief="flat", cursor="hand2", padx=10, pady=5,
            command=self._load_chat
        )
        self.load_btn.pack(side="left", padx=(0, 8))

        self.summary_btn = tk.Button(
            bar2, text=UI["zh"]["btn_summary"],
            font=(FONT, 10), bg="#0277BD", fg="#FFFFFF",
            activebackground="#01579B",
            relief="flat", cursor="hand2", padx=10, pady=5,
            command=self._summarize
        )
        self.summary_btn.pack(side="left", padx=(0, 16))

        # 模式切換：專業 ↔ 簡易
        self.mode_btn = tk.Button(
            bar2, text=UI["zh"]["mode_pro"],
            font=(FONT, 10), bg=C["header_bg"], fg="#FFFFFF",
            activebackground="#006064",
            relief="flat", cursor="hand2", padx=10, pady=5,
            command=self._toggle_mode
        )
        self.mode_btn.pack(side="left", padx=(0, 16))

        # ── 第三行：進階功能 ──────────────────────────────────
        bar3 = tk.Frame(self.root, bg=C["app_bg"])
        bar3.pack(fill="x", padx=14, pady=(0, 10))

        self.profile_btn = tk.Button(
            bar3, text=UI["zh"]["btn_profile"],
            font=(FONT, 10), bg="#5C6BC0", fg="#FFFFFF",
            activebackground="#3949AB",
            relief="flat", cursor="hand2", padx=10, pady=5,
            command=self._show_patient_form
        )
        self.profile_btn.pack(side="left", padx=(0, 8))

        self.history_btn = tk.Button(
            bar3, text=UI["zh"]["btn_history"],
            font=(FONT, 10), bg="#5C6BC0", fg="#FFFFFF",
            activebackground="#3949AB",
            relief="flat", cursor="hand2", padx=10, pady=5,
            command=self._show_history
        )
        self.history_btn.pack(side="left")

    # ──────────────────────────────────────────────────────────
    # 訊息傳送與 API 呼叫
    # ──────────────────────────────────────────────────────────

    def _on_enter(self, event):
        """Enter 鍵：傳送訊息（Shift+Enter 則允許換行）"""
        if event.state & 0x1:     # Shift 鍵按下時不攔截
            return
        self._send_message()
        return "break"            # 阻止 Enter 的預設換行行為

    def _send_message(self):
        """讀取輸入框內容，顯示使用者訊息並呼叫 API"""
        if self.is_waiting:
            return

        text = self.input_box.get("1.0", "end-1c").strip()
        if not text:
            return

        # 清空輸入框
        self.input_box.delete("1.0", "end")

        # 顯示使用者訊息，並加入歷史
        self._insert_user_msg(text)
        self.conversation_history.append({"role": "user", "content": text})

        # ── 優先查詢本地知識庫 ────────────────────────────────
        kb_match = self._search_knowledge_base(text)
        if kb_match:
            reply = kb_match["answer"]
            self.conversation_history.append({"role": "assistant", "content": reply})
            self._insert_ai_msg(reply)
            badge = "  📚 來自知識庫\n" if self.lang == "zh" else "  📚 From knowledge base\n"
            self.chat.insert("end", badge, "kb_badge")
            self._update_count()
            return

        # ── 知識庫無命中 → 呼叫 Groq API ─────────────────────
        self.is_waiting = True
        self._set_status(UI[self.lang]["status_busy"], C["status_busy"])
        self.send_btn.config(state="disabled")
        self._insert_thinking()

        # 在背景執行緒呼叫 API，避免 UI 凍結
        threading.Thread(target=self._call_api, daemon=True).start()

    def _call_api(self):
        """背景執行緒：以串流模式呼叫 Groq API，逐塊推送到主執行緒"""
        try:
            stream = self.client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=self.conversation_history,
                max_tokens=1024,
                temperature=0.4,
                stream=True,
            )
            self.root.after(0, self._begin_stream)
            chunks = []
            for chunk in stream:
                delta = chunk.choices[0].delta.content or ""
                if delta:
                    chunks.append(delta)
                    self.root.after(0, self._on_stream_chunk, delta)
            full_reply = "".join(chunks)
            self.conversation_history.append({"role": "assistant", "content": full_reply})
            self.root.after(0, self._on_stream_done)
        except Exception as e:
            self.root.after(0, self._on_stream_error, str(e))

    def _begin_stream(self):
        """串流開始：移除思考提示，插入 AI 標籤與時間戳，記錄內容起始位置"""
        self._remove_thinking()
        ts = datetime.now().strftime("%H:%M")
        self.chat.insert("end", f"\n  {UI[self.lang]['ai_lbl']}  ", "ai_lbl")
        self.chat.insert("end", f"[{ts}]\n", "ts")
        self._stream_start = self.chat.index("end")

    def _on_stream_chunk(self, delta: str):
        """逐塊插入串流文字"""
        self.chat.insert("end", delta, "ai_msg")
        self.chat.see("end")

    def _on_stream_done(self):
        """串流完成：補分隔線、套用緊急燈號顏色、恢復 UI"""
        self.chat.insert("end", "\n  " + "─" * 52 + "\n", "sep")
        self._colorize_urgency()
        self._update_count()
        self.is_waiting = False
        self._set_status(UI[self.lang]["status_ok"], C["status_ok"])
        self.send_btn.config(state="normal")

    def _on_stream_error(self, err: str):
        """串流發生例外：移除思考提示，顯示錯誤訊息"""
        self._remove_thinking()
        self._insert_ai_msg(f"⚠️  連線失敗：{err}\n請確認 API Key 與網路連線。")
        self.is_waiting = False
        self._set_status(UI[self.lang]["status_err"], C["status_err"])
        self.send_btn.config(state="normal")

    def _colorize_urgency(self):
        """掃描串流後的 AI 訊息，對含緊急燈號關鍵字的行套用彩色標籤"""
        if not hasattr(self, "_stream_start"):
            return
        start_line = int(self._stream_start.split(".")[0])
        end_line   = int(self.chat.index("end-1c").split(".")[0])
        for ln in range(start_line, end_line + 1):
            ls = f"{ln}.0"
            le = f"{ln}.end"
            text = self.chat.get(ls, le)
            if "紅燈" in text or "🔴" in text:
                tag = "red_line"
            elif "黃燈" in text or "🟡" in text:
                tag = "yellow_line"
            elif "綠燈" in text or "🟢" in text:
                tag = "green_line"
            else:
                continue
            self.chat.tag_remove("ai_msg", ls, f"{le}+1c")
            self.chat.tag_add(tag, ls, f"{le}+1c")

    # ──────────────────────────────────────────────────────────
    # 聊天顯示區 ─ 文字插入輔助方法
    # ──────────────────────────────────────────────────────────

    def _chat_insert(self, *args):
        """解除 Text 唯讀保護、插入內容後再鎖回"""

        self.chat.insert(*args)

        self.chat.see("end")

    def _insert_user_msg(self, text: str):
        """在聊天區插入使用者訊息（淺青色背景）"""
        ts = datetime.now().strftime("%H:%M")

        self.chat.insert("end", f"\n  {UI[self.lang]['user_lbl']}  ", "user_lbl")
        self.chat.insert("end", f"[{ts}]\n", "ts")
        self.chat.insert("end", f"  {text}\n", "user_msg")

        self.chat.see("end")

    def _insert_ai_msg(self, text: str):
        """
        在聊天區插入 AI 訊息（淺綠色背景）。
        自動偵測緊急燈號關鍵字，套用對應顏色。
        """
        ts = datetime.now().strftime("%H:%M")

        self.chat.insert("end", f"\n  {UI[self.lang]['ai_lbl']}  ", "ai_lbl")
        self.chat.insert("end", f"[{ts}]\n", "ts")

        for line in text.split("\n"):
            # 判斷該行屬於哪個燈號，套用對應顏色標籤
            if "紅燈" in line or "🔴" in line:
                tag = "red_line"
            elif "黃燈" in line or "🟡" in line:
                tag = "yellow_line"
            elif "綠燈" in line or "🟢" in line:
                tag = "green_line"
            else:
                tag = "ai_msg"
            self.chat.insert("end", f"  {line}\n", tag)

        self.chat.insert("end", "  " + "─" * 52 + "\n", "sep")

        self.chat.see("end")

    def _insert_thinking(self):
        """插入「AI 思考中」動態提示，並記錄插入前位置供後續刪除"""

        # 記錄當前結尾字元索引，用於精確刪除思考提示
        self._think_idx = self.chat.index("end-1c")
        self.chat.insert("end", f"\n  {UI[self.lang]['thinking']}", "thinking")

        self.chat.see("end")

    def _remove_thinking(self):
        """找到思考提示文字並整行刪除"""

        pos = self.chat.search("⏳", "end", stopindex="1.0", backwards=True)
        if pos:
            line = int(pos.split(".")[0])
            # 刪除：前一行的換行符 + 思考提示這一整行（不含其尾端換行）
            self.chat.delete(f"{line}.0 -1c", f"{line}.end")


    # ──────────────────────────────────────────────────────────
    # 功能按鈕動作
    # ──────────────────────────────────────────────────────────

    def _export_pdf(self):
        """呼叫 utils.export_to_pdf，匯出目前的對話紀錄"""
        # 過濾掉 system prompt，只匯出 user / assistant 的訊息
        history = [m for m in self.conversation_history if m["role"] != "system"]
        if not history:
            messagebox.showinfo("提示", "目前沒有對話紀錄可以匯出。")
            return

        ok, result = export_to_pdf(history)
        if ok:
            messagebox.showinfo("匯出成功 ✅", f"PDF 已儲存至：\n{result}")
        else:
            if result != "使用者取消儲存。":
                messagebox.showerror("匯出失敗 ❌", result)

    def _clear_chat(self):
        """清除所有對話（保留 system prompt），並重新顯示歡迎訊息"""
        if not messagebox.askyesno("確認清除", "確定要清除所有對話紀錄嗎？\n此動作無法復原。"):
            return
        # 只保留第 0 筆（system prompt）
        self.conversation_history = [self.conversation_history[0]]

        self.chat.delete("1.0", "end")

        self._update_count()
        self._show_welcome()

    def _show_welcome(self):
        """程式啟動或清除後顯示歡迎訊息（依目前語言切換內容）"""
        if self.lang == "en":
            welcome = (
                "Hello! I'm Triage AI, your medical triage assistant.\n\n"
                "Please describe your symptoms, for example:\n"
                "  • Headache with fever for two days\n"
                "  • Chest tightness and shortness of breath\n"
                "  • Swollen right ankle after a fall\n\n"
                "I'll assess urgency (🔴🟡🟢) and suggest a department.\n\n"
                "⚠️  For emergencies (chest pain, difficulty breathing,\n"
                "     loss of consciousness), call 119 immediately."
            )
        else:
            welcome = (
                "您好！我是醫療分診助理 AI，名叫「小護」。\n\n"
                "請描述您目前的不適症狀，例如：\n"
                "  • 頭痛合併發燒已兩天\n"
                "  • 胸口悶痛且喘不過氣\n"
                "  • 右腳踝扭傷腫脹\n\n"
                "我會協助您評估緊急程度（🔴🟡🟢）並建議就診科別。\n\n"
                "⚠️  若有緊急症狀（胸痛、呼吸困難、意識不清等），\n"
                "     請立即撥打 119 或前往急診，勿等候 AI 回應。"
            )
        self._insert_ai_msg(welcome)

    # ──────────────────────────────────────────────────────────
    # 症狀快捷按鈕列
    # ──────────────────────────────────────────────────────────

    def _build_symptom_bar(self):
        """建立症狀快捷按鈕列（在聊天區和輸入框之間）"""
        self.symptom_frame = tk.Frame(self.root, bg=C["app_bg"])
        self.symptom_frame.pack(fill="x", padx=14, pady=(4, 0))
        self._render_symptom_btns()

    def _render_symptom_btns(self):
        """依目前語言清除並重繪症狀快捷按鈕"""
        for w in self.symptom_frame.winfo_children():
            w.destroy()

        tk.Label(self.symptom_frame, text=UI[self.lang]["quick"],
                 font=(FONT, 9), bg=C["app_bg"], fg=C["text_hint"]).pack(side="left", padx=(0, 4))

        for sym in SYMPTOMS[self.lang]:
            tk.Button(
                self.symptom_frame, text=sym,
                font=(FONT, 9), bg="#E0F2F1", fg=C["text_dark"],
                activebackground=C["user_row"],
                relief="flat", cursor="hand2", padx=6, pady=2,
                command=lambda s=sym: self._symptom_click(s)
            ).pack(side="left", padx=2)

    def _symptom_click(self, sym: str):
        """點擊症狀按鈕：將症狀文字附加到輸入框"""
        # 去除 emoji 前綴，例如 "🤕 頭痛" → "頭痛"
        text = sym.split(" ", 1)[1] if " " in sym else sym
        current = self.input_box.get("1.0", "end-1c").strip()
        if current:
            self.input_box.insert("end", f"、{text}")
        else:
            self.input_box.insert("end", text)
        self.input_box.focus_set()

    # ──────────────────────────────────────────────────────────
    # 新功能：語言切換 / 字體大小 / 右鍵複製
    # ──────────────────────────────────────────────────────────

    def _toggle_language(self):
        """切換中文 ↔ English：更新 UI，若有對話則呼叫 API 翻譯後重繪"""
        self.lang = "en" if self.lang == "zh" else "zh"
        self.conversation_history[0]["content"] = self._current_system_prompt()
        self._update_ui_lang()
        self._render_symptom_btns()

        to_translate = [m for m in self.conversation_history if m["role"] != "system"]
        if to_translate:
            status = "● Translating…" if self.lang == "en" else "● 翻譯中…"
            self._set_status(status, C["status_busy"])
            self.send_btn.config(state="disabled")
            self.lang_btn.config(state="disabled")
            threading.Thread(target=self._translate_history, daemon=True).start()
        else:
            self._redraw_conversation()

    def _update_ui_lang(self):
        """將所有 UI 按鈕、標籤更新為目前語言"""
        t = UI[self.lang]
        self.title_lbl.config(text=t["title"])
        self.hint_lbl.config(text=t["hint"])
        self.send_btn.config(text=t["send"])
        self.lang_btn.config(text=t["lang_btn"])
        self.export_btn.config(text=t["btn_export"])
        self.clear_btn.config(text=t["btn_clear"])
        self.save_btn.config(text=t["btn_save"])
        self.load_btn.config(text=t["btn_load"])
        self.summary_btn.config(text=t["btn_summary"])
        key = "mode_simple" if self.mode == "simple" else "mode_pro"
        self.mode_btn.config(text=t[key])
        self.mic_btn.config(text=t["mic_idle"])
        self.profile_btn.config(text=t["btn_profile"])
        self.history_btn.config(text=t["btn_history"])
        self._set_status(t["status_ok"], C["status_ok"])
        self._update_count()

    def _redraw_conversation(self):
        """清空聊天區，用新語言角色標籤重新繪製所有歷史訊息"""
        self.chat.delete("1.0", "end")
        messages = [m for m in self.conversation_history if m["role"] != "system"]
        if not messages:
            self._show_welcome()
            return
        for msg in messages:
            if msg["role"] == "user":
                self._insert_user_msg(msg["content"])
            elif msg["role"] == "assistant":
                self._insert_ai_msg(msg["content"])

    def _translate_history(self):
        """背景執行緒：一次 API 呼叫批次翻譯所有 user / assistant 訊息"""
        to_translate = [m for m in self.conversation_history if m["role"] != "system"]
        target = "English" if self.lang == "en" else "繁體中文（台灣用語）"

        numbered = "\n\n".join(
            f"[{i + 1}]\n{m['content']}"
            for i, m in enumerate(to_translate)
        )
        prompt = (
            f"Translate each of the following {len(to_translate)} messages to {target}.\n"
            "Preserve all formatting symbols (━━━, 【】, 🔴, 🟡, 🟢, bullet points, etc.) exactly.\n"
            'Separate each translated message with exactly "===END===" on its own line.\n'
            "Output translations only — no explanation, no numbering.\n\n"
            f"{numbered}"
        )
        try:
            resp = self.client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=4096,
                temperature=0.1,
            )
            raw   = resp.choices[0].message.content
            parts = [p.strip() for p in raw.split("===END===") if p.strip()]
            # 若回傳數量不足，以原文補齊
            if len(parts) < len(to_translate):
                parts += [m["content"] for m in to_translate[len(parts):]]
            self.root.after(0, self._on_translation_done, parts[:len(to_translate)])
        except Exception as e:
            self.root.after(0, self._on_translation_error, str(e))

    def _on_translation_done(self, translated: list):
        """翻譯完成：更新 conversation_history 內容並重繪對話"""
        idx = 0
        for m in self.conversation_history:
            if m["role"] != "system":
                if idx < len(translated):
                    m["content"] = translated[idx]
                idx += 1
        self._redraw_conversation()
        self._set_status(UI[self.lang]["status_ok"], C["status_ok"])
        self.send_btn.config(state="normal")
        self.lang_btn.config(state="normal")

    def _on_translation_error(self, err: str):
        """翻譯 API 失敗：保留原文重繪，顯示警告"""
        self._redraw_conversation()
        self._set_status(UI[self.lang]["status_ok"], C["status_ok"])
        self.send_btn.config(state="normal")
        self.lang_btn.config(state="normal")
        title = "Translation Failed" if self.lang == "en" else "翻譯失敗"
        body  = (f"Failed to translate: {err}" if self.lang == "en"
                 else f"無法翻譯對話內容：{err}\n（保留原文顯示）")
        messagebox.showwarning(title, body)

    def _change_font_size(self, delta: int):
        """調整聊天區字體大小（最小 9，最大 18）"""
        self.font_size = max(9, min(18, self.font_size + delta))
        self.size_lbl.config(text=f"{self.font_size}pt")
        self._apply_font_size()

    def _apply_font_size(self):
        """將目前的 font_size 套用到所有訊息內容標籤"""
        fs = self.font_size
        for tag, extra in [
            ("user_msg",    {}),
            ("ai_msg",      {}),
            ("red_line",    {"bold": True}),
            ("yellow_line", {"bold": True}),
            ("green_line",  {"bold": True}),
        ]:
            style = (FONT, fs, "bold") if extra.get("bold") else (FONT, fs)
            self.chat.tag_configure(tag, font=style)

    def _block_chat_edit(self, event):
        """封鎖聊天區的鍵盤輸入，但允許 Ctrl+C / Ctrl+A 等複製選取操作"""
        if event.state & 0x4:          # Ctrl 按住：允許全部（複製、全選等）
            return
        if event.keysym in (           # 允許方向鍵、Page Up/Down 捲動
            "Left", "Right", "Up", "Down",
            "Home", "End", "Prior", "Next",
            "Shift_L", "Shift_R", "Control_L", "Control_R",
        ):
            return
        return "break"                 # 封鎖其他所有按鍵（防止輸入）

    def _show_context_menu(self, event):
        """右鍵點擊聊天區時顯示複製選單"""
        menu = tk.Menu(self.root, tearoff=0)
        menu.add_command(label="複製選取文字 / Copy Selected", command=self._copy_selected)
        menu.add_command(label="複製全部對話 / Copy All",      command=self._copy_all)
        menu.tk_popup(event.x_root, event.y_root)

    def _copy_selected(self):
        """複製聊天區中已選取的文字到剪貼簿"""
        try:
            text = self.chat.get(tk.SEL_FIRST, tk.SEL_LAST)
            self.root.clipboard_clear()
            self.root.clipboard_append(text)
        except tk.TclError:
            pass  # 沒有選取文字時不做任何動作

    def _copy_all(self):
        """複製整個聊天區的文字到剪貼簿"""
        text = self.chat.get("1.0", "end-1c")
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        messagebox.showinfo("已複製", "全部對話已複製到剪貼簿。")

    # ──────────────────────────────────────────────────────────
    # 中等功能：模式切換 / 儲存載入 / 對話摘要
    # ──────────────────────────────────────────────────────────

    def _current_system_prompt(self) -> str:
        """依目前語言、模式、病患資料，組合最終系統提示詞"""
        if self.lang == "en":
            base = SYSTEM_PROMPT_SIMPLE_EN if self.mode == "simple" else SYSTEM_PROMPT_EN
        else:
            base = SYSTEM_PROMPT_SIMPLE if self.mode == "simple" else SYSTEM_PROMPT
        if self.patient_profile:
            base += "\n\n" + self._format_profile_for_prompt()
        return base

    def _toggle_mode(self):
        """切換專業 ↔ 簡易模式，直接更新 system prompt，不清除對話"""
        self.mode = "simple" if self.mode == "pro" else "pro"
        # 更新 conversation_history 第 0 筆（system prompt）
        self.conversation_history[0]["content"] = self._current_system_prompt()
        key = "mode_simple" if self.mode == "simple" else "mode_pro"
        self.mode_btn.config(text=UI[self.lang][key],
                             bg="#78909C" if self.mode == "simple" else C["header_bg"])
        label = UI[self.lang][key].split(" ", 1)[1]
        messagebox.showinfo("Mode" if self.lang == "en" else "模式切換",
                            f"Switched to {label}." if self.lang == "en"
                            else f"已切換至【{label}】，下一則回覆立即生效。")

    def _save_chat(self):
        """將對話紀錄儲存為 JSON 檔案"""
        history = [m for m in self.conversation_history if m["role"] != "system"]
        if not history:
            messagebox.showinfo("提示", "目前沒有對話紀錄可以儲存。")
            return
        ok, result = save_conversation(history)
        if ok:
            messagebox.showinfo("儲存成功 ✅", f"對話已儲存至：\n{result}")
        elif result != "使用者取消儲存。":
            messagebox.showerror("儲存失敗", result)

    def _load_chat(self):
        """從 JSON 檔案載入先前儲存的對話，並在聊天區重新顯示"""
        if len(self.conversation_history) > 1:
            if not messagebox.askyesno("確認載入", "載入新對話將清除目前的紀錄，確定嗎？"):
                return
        ok, result, messages = load_conversation()
        if not ok:
            if result != "使用者取消載入。":
                messagebox.showerror("載入失敗", result)
            return
        # 重建歷史並重繪聊天區
        self.conversation_history = [{"role": "system", "content": self._current_system_prompt()}]
        self.conversation_history.extend(messages)

        self.chat.delete("1.0", "end")

        for msg in messages:
            if msg["role"] == "user":
                self._insert_user_msg(msg["content"])
            elif msg["role"] == "assistant":
                self._insert_ai_msg(msg["content"])
        self._update_count()
        messagebox.showinfo("載入成功 ✅", f"已載入對話紀錄：\n{result}")

    def _summarize(self):
        """呼叫 API 產生本次對話摘要，顯示於彈出視窗"""
        if len(self.conversation_history) <= 1:
            messagebox.showinfo("提示", "目前沒有對話內容可以摘要。")
            return
        if self.is_waiting:
            return
        self.is_waiting = True
        self._set_status(UI[self.lang]["status_summary"], C["status_busy"])
        # 組合一次性訊息（不加入 conversation_history，不污染對話脈絡）
        req = SUMMARY_EN if self.lang == "en" else SUMMARY_ZH
        messages = self.conversation_history + [{"role": "user", "content": req}]

        def do_summary():
            try:
                resp = self.client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=messages,
                    max_tokens=400,
                    temperature=0.3,
                )
                self.root.after(0, self._on_summary_done, resp.choices[0].message.content)
            except Exception as e:
                self.root.after(0, self._on_summary_error, str(e))

        threading.Thread(target=do_summary, daemon=True).start()

    def _on_summary_done(self, text: str):
        """摘要完成：顯示於彈出視窗"""
        self.is_waiting = False
        self._set_status(UI[self.lang]["status_ok"], C["status_ok"])
        title = "📋 Conversation Summary" if self.lang == "en" else "📋 對話摘要"
        win = tk.Toplevel(self.root)
        win.title(title)
        win.geometry("520x280")
        win.configure(bg="#FFFFFF")
        win.transient(self.root)
        win.update_idletasks()
        x = (win.winfo_screenwidth()  - 520) // 2
        y = (win.winfo_screenheight() - 280) // 2
        win.geometry(f"520x280+{x}+{y}")
        tk.Label(win, text=title, font=(FONT, 13, "bold"),
                 bg="#FFFFFF", fg=C["header_bg"]).pack(pady=(14, 6))
        t = tk.Text(win, wrap="word", font=(FONT, 11),
                    bg="#F5F5F5", fg=C["text_dark"],
                    relief="flat", padx=14, pady=10)
        t.insert("1.0", text)
        t.config(state="disabled")
        t.pack(fill="both", expand=True, padx=16, pady=(0, 14))

    def _on_summary_error(self, err: str):
        """摘要 API 失敗處理"""
        self.is_waiting = False
        self._set_status(UI[self.lang]["status_ok"], C["status_ok"])
        messagebox.showerror("摘要失敗", f"無法產生摘要：{err}")

    # ──────────────────────────────────────────────────────────
    # 知識庫查詢
    # ──────────────────────────────────────────────────────────

    def _load_kb(self) -> dict:
        """載入並快取 knowledge_base.json（首次呼叫時讀檔）"""
        if not hasattr(self, "_kb"):
            kb_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "knowledge_base.json")
            try:
                with open(kb_path, "r", encoding="utf-8") as f:
                    self._kb = json.load(f)
            except Exception:
                self._kb = {"zh": [], "en": []}
        return self._kb

    def _search_knowledge_base(self, text: str):
        """
        以關鍵字比對搜尋本地知識庫。
        回傳命中分數最高的條目，或 None（完全無命中）。
        """
        entries = self._load_kb().get(self.lang, [])
        text_lower = text.lower()
        best, best_score = None, 0
        for entry in entries:
            score = sum(1 for kw in entry.get("keywords", []) if kw.lower() in text_lower)
            if score > best_score:
                best_score, best = score, entry
        return best if best_score >= 1 else None

    # ──────────────────────────────────────────────────────────
    # 進階功能：病患資料 / 語音輸入 / 歷史紀錄管理
    # ──────────────────────────────────────────────────────────

    def _format_profile_for_prompt(self) -> str:
        """將 self.patient_profile 格式化成可附加到 system prompt 的文字"""
        if self.lang == "en":
            header = "[Patient Information]"
            labels = {"age": "Age", "gender": "Gender",
                      "conditions": "Chronic Conditions", "medications": "Current Medications"}
        else:
            header = "【病患基本資料】"
            labels = {"age": "年齡", "gender": "性別",
                      "conditions": "慢性病史", "medications": "目前用藥"}
        lines = [header]
        for key, label in labels.items():
            val = self.patient_profile.get(key, "")
            if val:
                lines.append(f"{label}：{val}")
        return "\n".join(lines)

    def _show_patient_form(self):
        """彈出病患基本資料填寫表單；儲存後自動注入 system prompt"""
        title = "👤 Patient Info" if self.lang == "en" else "👤 病患基本資料"
        win = tk.Toplevel(self.root)
        win.title(title)
        win.geometry("460x360")
        win.configure(bg="#FFFFFF")
        win.resizable(False, False)
        win.transient(self.root)
        win.grab_set()
        win.update_idletasks()
        x = (win.winfo_screenwidth()  - 460) // 2
        y = (win.winfo_screenheight() - 360) // 2
        win.geometry(f"460x360+{x}+{y}")

        tk.Label(win, text=title, font=(FONT, 13, "bold"),
                 bg="#FFFFFF", fg=C["header_bg"]).pack(pady=(16, 10))

        form = tk.Frame(win, bg="#FFFFFF")
        form.pack(fill="both", padx=28, expand=True)

        field_labels = (["Age", "Gender", "Chronic Conditions", "Current Medications"]
                        if self.lang == "en"
                        else ["年齡", "性別", "慢性病史", "目前用藥"])
        keys = ["age", "gender", "conditions", "medications"]

        entries: dict = {}
        gender_var = tk.StringVar()

        for i, (lbl, key) in enumerate(zip(field_labels, keys)):
            tk.Label(form, text=lbl, font=(FONT, 10, "bold"),
                     bg="#FFFFFF", fg=C["text_dark"], anchor="w").grid(
                row=i, column=0, sticky="w", pady=7, padx=(0, 14))

            if key == "gender":
                options = (["Male", "Female", "Other"] if self.lang == "en"
                           else ["男", "女", "其他"])
                gender_var.set(self.patient_profile.get("gender", options[0]))
                om = tk.OptionMenu(form, gender_var, *options)
                om.config(font=(FONT, 10), bg="#F5F5F5", relief="flat", width=18)
                om.grid(row=i, column=1, sticky="w", pady=7)
                entries[key] = gender_var
            else:
                ent = tk.Entry(form, font=(FONT, 10), bg="#F5F5F5", fg=C["text_dark"],
                               relief="groove", width=28)
                ent.insert(0, self.patient_profile.get(key, ""))
                ent.grid(row=i, column=1, sticky="ew", pady=7)
                entries[key] = ent

        form.columnconfigure(1, weight=1)

        def save_profile():
            self.patient_profile = {k: entries[k].get().strip() for k in keys}
            self.patient_profile = {k: v for k, v in self.patient_profile.items() if v}
            self.conversation_history[0]["content"] = self._current_system_prompt()
            win.destroy()
            if self.patient_profile:
                msg = ("Patient info saved and will be included in triage."
                       if self.lang == "en"
                       else "病患資料已儲存，將自動納入分診評估。")
                messagebox.showinfo("✅", msg)

        def clear_profile():
            self.patient_profile = {}
            self.conversation_history[0]["content"] = self._current_system_prompt()
            win.destroy()

        btn_row = tk.Frame(win, bg="#FFFFFF")
        btn_row.pack(pady=(4, 16))
        tk.Button(btn_row, text="Save" if self.lang == "en" else "儲存",
                  font=(FONT, 10, "bold"), bg=C["header_bg"], fg="#FFFFFF",
                  relief="flat", cursor="hand2", padx=14, pady=5,
                  command=save_profile).pack(side="left", padx=6)
        tk.Button(btn_row, text="Clear" if self.lang == "en" else "清除資料",
                  font=(FONT, 10), bg=C["btn_clear"], fg="#FFFFFF",
                  relief="flat", cursor="hand2", padx=14, pady=5,
                  command=clear_profile).pack(side="left", padx=6)
        tk.Button(btn_row, text="Cancel" if self.lang == "en" else "取消",
                  font=(FONT, 10), bg=C["app_bg"], fg=C["text_dark"],
                  relief="flat", cursor="hand2", padx=14, pady=5,
                  command=win.destroy).pack(side="left", padx=6)

    # ── 語音輸入 ─────────────────────────────────────────────────

    def _voice_input(self):
        """點擊麥克風按鈕：在背景執行緒錄音並辨識語音"""
        if getattr(self, "_recording", False):
            return
        try:
            import speech_recognition as sr
        except ImportError:
            messagebox.showerror(
                "缺少套件" if self.lang == "zh" else "Missing Package",
                "請先執行：pip install SpeechRecognition PyAudio"
            )
            return

        self._recording = True
        self.mic_btn.config(text=UI[self.lang]["mic_rec"], fg="#E53935")
        self._set_status(UI[self.lang]["status_rec"], C["status_busy"])

        def _do_record():
            try:
                recognizer = sr.Recognizer()
                with sr.Microphone() as source:
                    recognizer.adjust_for_ambient_noise(source, duration=0.5)
                    audio = recognizer.listen(source, timeout=10, phrase_time_limit=15)
                lang_code = "zh-TW" if self.lang == "zh" else "en-US"
                text = recognizer.recognize_google(audio, language=lang_code)
                self.root.after(0, self._on_voice_done, text)
            except sr.WaitTimeoutError:
                self.root.after(0, self._on_voice_error,
                                "Timeout — no speech detected." if self.lang == "en"
                                else "逾時未偵測到語音，請再試一次。")
            except sr.UnknownValueError:
                self.root.after(0, self._on_voice_error,
                                "Could not understand audio." if self.lang == "en"
                                else "無法辨識語音，請再試一次。")
            except Exception as e:
                self.root.after(0, self._on_voice_error, str(e))

        threading.Thread(target=_do_record, daemon=True).start()

    def _on_voice_done(self, text: str):
        self._recording = False
        self.mic_btn.config(text=UI[self.lang]["mic_idle"], fg=C["header_bg"])
        self._set_status(UI[self.lang]["status_ok"], C["status_ok"])
        self.input_box.insert("end", text)
        self.input_box.focus_set()

    def _on_voice_error(self, err: str):
        self._recording = False
        self.mic_btn.config(text=UI[self.lang]["mic_idle"], fg=C["header_bg"])
        self._set_status(UI[self.lang]["status_ok"], C["status_ok"])
        title = "Voice Error" if self.lang == "en" else "語音輸入失敗"
        messagebox.showwarning(title, err)

    # ── 歷史紀錄管理 ─────────────────────────────────────────────

    def _show_history(self):
        """列出桌面／文件資料夾內的 triage_*.json，提供載入與刪除"""
        patterns = [
            os.path.join(os.getcwd(), "triage_*.json"),
            os.path.join(os.path.expanduser("~"), "Desktop", "triage_*.json"),
            os.path.join(os.path.expanduser("~"), "Documents", "triage_*.json"),
        ]
        found = list(dict.fromkeys(f for p in patterns for f in glob.glob(p)))

        records = []
        for fp in found:
            try:
                with open(fp, "r", encoding="utf-8") as fh:
                    data = json.load(fh)
                records.append({
                    "path":     fp,
                    "saved_at": data.get("saved_at", ""),
                    "count":    len(data.get("messages", [])),
                })
            except Exception:
                pass
        records.sort(key=lambda r: r["saved_at"], reverse=True)

        title = "📚 History" if self.lang == "en" else "📚 歷史紀錄"
        win = tk.Toplevel(self.root)
        win.title(title)
        win.geometry("580x380")
        win.configure(bg="#FFFFFF")
        win.transient(self.root)
        win.update_idletasks()
        x = (win.winfo_screenwidth()  - 580) // 2
        y = (win.winfo_screenheight() - 380) // 2
        win.geometry(f"580x380+{x}+{y}")

        tk.Label(win, text=title, font=(FONT, 13, "bold"),
                 bg="#FFFFFF", fg=C["header_bg"]).pack(pady=(14, 6))

        if not records:
            msg = ("No saved conversation files found.\n"
                   "(Files are searched in current folder, Desktop, and Documents.)"
                   if self.lang == "en"
                   else "找不到已儲存的對話檔案。\n（搜尋範圍：程式目錄、桌面、文件）")
            tk.Label(win, text=msg, font=(FONT, 10), bg="#FFFFFF",
                     fg=C["text_hint"], justify="center").pack(pady=24)
            tk.Button(win, text="Close" if self.lang == "en" else "關閉",
                      font=(FONT, 10), bg=C["app_bg"], fg=C["text_dark"],
                      relief="flat", cursor="hand2", padx=12, pady=5,
                      command=win.destroy).pack()
            return

        # ── 清單 ───────────────────────────────────────────────
        list_frame = tk.Frame(win, bg="#F5F5F5", relief="groove", bd=1)
        list_frame.pack(fill="both", expand=True, padx=16, pady=(0, 6))

        sb = tk.Scrollbar(list_frame)
        sb.pack(side="right", fill="y")
        listbox = tk.Listbox(list_frame, font=(FONT, 10), yscrollcommand=sb.set,
                             bg="#F5F5F5", fg=C["text_dark"], selectmode="single",
                             activestyle="none", relief="flat")
        listbox.pack(fill="both", expand=True)
        sb.config(command=listbox.yview)

        for r in records:
            name  = os.path.basename(r["path"])
            saved = r["saved_at"][:16].replace("T", " ") if r["saved_at"] else "?"
            n     = r["count"]
            label = (f"{name}  ·  {saved}  ·  {n} msgs"
                     if self.lang == "en"
                     else f"{name}  ·  {saved}  ·  {n} 則")
            listbox.insert("end", label)

        # ── 按鈕 ───────────────────────────────────────────────
        btn_row = tk.Frame(win, bg="#FFFFFF")
        btn_row.pack(pady=(0, 12))

        def load_selected():
            idx = listbox.curselection()
            if not idx:
                return
            rec = records[idx[0]]
            if len(self.conversation_history) > 1:
                if not messagebox.askyesno(
                        "Confirm" if self.lang == "en" else "確認載入",
                        "Loading will clear current chat. Continue?"
                        if self.lang == "en"
                        else "載入新對話將清除目前的紀錄，確定嗎？"):
                    return
            try:
                with open(rec["path"], "r", encoding="utf-8") as fh:
                    data = json.load(fh)
                messages = data.get("messages", [])
                self.conversation_history = [
                    {"role": "system", "content": self._current_system_prompt()}
                ]
                self.conversation_history.extend(messages)
                self.chat.delete("1.0", "end")
                for msg in messages:
                    if msg["role"] == "user":
                        self._insert_user_msg(msg["content"])
                    elif msg["role"] == "assistant":
                        self._insert_ai_msg(msg["content"])
                self._update_count()
                win.destroy()
                messagebox.showinfo("✅", f"{'Loaded' if self.lang == 'en' else '已載入'}：{os.path.basename(rec['path'])}")
            except Exception as e:
                messagebox.showerror("Error", str(e))

        def delete_selected():
            idx = listbox.curselection()
            if not idx:
                return
            rec  = records[idx[0]]
            name = os.path.basename(rec["path"])
            if not messagebox.askyesno(
                    "Confirm" if self.lang == "en" else "確認刪除",
                    f"Delete {name}?" if self.lang == "en" else f"確定要刪除 {name}？"):
                return
            try:
                os.remove(rec["path"])
                listbox.delete(idx[0])
                records.pop(idx[0])
            except Exception as e:
                messagebox.showerror("Error", str(e))

        tk.Button(btn_row, text="📂 Load" if self.lang == "en" else "📂 載入",
                  font=(FONT, 10), bg="#00695C", fg="#FFFFFF",
                  relief="flat", cursor="hand2", padx=12, pady=5,
                  command=load_selected).pack(side="left", padx=6)
        tk.Button(btn_row, text="🗑 Delete" if self.lang == "en" else "🗑 刪除",
                  font=(FONT, 10), bg=C["btn_clear"], fg="#FFFFFF",
                  relief="flat", cursor="hand2", padx=12, pady=5,
                  command=delete_selected).pack(side="left", padx=6)
        tk.Button(btn_row, text="Close" if self.lang == "en" else "關閉",
                  font=(FONT, 10), bg=C["app_bg"], fg=C["text_dark"],
                  relief="flat", cursor="hand2", padx=12, pady=5,
                  command=win.destroy).pack(side="left", padx=6)

    # ──────────────────────────────────────────────────────────
    # 狀態更新輔助
    # ──────────────────────────────────────────────────────────

    def _set_status(self, text: str, color: str):
        """更新標題列右側的狀態燈號文字與顏色"""
        self.status_lbl.config(text=text, fg=color)

    def _update_count(self):
        """更新底部工具列的對話輪數計數"""
        n = sum(1 for m in self.conversation_history if m["role"] == "user")
        self.count_lbl.config(text=UI[self.lang]["count"].format(n=n))


# ══════════════════════════════════════════════════════════════
# 程式進入點
# ══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    root = tk.Tk()
    app  = TriageBotApp(root)
    root.mainloop()
