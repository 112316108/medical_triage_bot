# ============================================================
# utils.py  ─  工具函式
# 負責人：C 同學
# 說明：提供 PDF 匯出等共用功能，供主程式呼叫
# ============================================================

import os
import json
import platform
from datetime import datetime
from tkinter import filedialog


# ── 字型搜尋 ─────────────────────────────────────────────────

def find_cjk_font() -> str | None:
    """
    在系統中尋找可用的繁體中文字型檔案。
    Windows 依序嘗試微軟正黑體、微軟雅黑；找不到則回傳 None。
    """
    if platform.system() != "Windows":
        return None

    candidates = [
        r"C:\Windows\Fonts\msjhbd.ttc",  # 微軟正黑體 Bold（繁體）
        r"C:\Windows\Fonts\msjh.ttc",    # 微軟正黑體 Regular（繁體）
        r"C:\Windows\Fonts\msyh.ttc",    # 微軟雅黑（簡體備用）
        r"C:\Windows\Fonts\mingliu.ttc", # 細明體（舊版 Windows）
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    return None


# ── PDF 匯出 ─────────────────────────────────────────────────

def export_to_pdf(chat_history: list) -> tuple:
    """
    將對話紀錄匯出為 PDF 檔案，含中文字型支援。

    參數：
        chat_history: list of dict
            [{"role": "user" | "assistant", "content": "訊息內容"}, ...]

    回傳：
        (True,  檔案完整路徑)  → 匯出成功
        (False, 錯誤說明文字)  → 匯出失敗
    """
    # 確認 fpdf2 已安裝
    try:
        from fpdf import FPDF
    except ImportError:
        return False, "找不到 fpdf2 套件，請執行：pip install fpdf2"

    # ── 選擇儲存位置 ─────────────────────────────────────────
    default_name = f"triage_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    filepath = filedialog.asksaveasfilename(
        defaultextension=".pdf",
        filetypes=[("PDF 文件", "*.pdf"), ("所有檔案", "*.*")],
        title="儲存分診對話紀錄",
        initialfile=default_name,
    )
    if not filepath:
        return False, "使用者取消儲存。"

    # ── 初始化 PDF ───────────────────────────────────────────
    font_path = find_cjk_font()

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    # 嘗試載入中文字型
    cjk_ok = False
    if font_path:
        try:
            pdf.add_font("CJK", fname=font_path)
            cjk_ok = True
        except Exception:
            pass  # 字型載入失敗時退回 Helvetica

    def use_font(size: int):
        """統一字型設定：有中文字型就用 CJK，否則用 Helvetica"""
        if cjk_ok:
            pdf.set_font("CJK", size=size)
        else:
            pdf.set_font("Helvetica", size=size)

    def safe(text: str) -> str:
        """無中文字型時，將中文替換為 ? 以避免 PDF 崩潰"""
        if cjk_ok:
            return text
        return text.encode("latin-1", errors="replace").decode("latin-1")

    # ── 頁首標題 ─────────────────────────────────────────────
    # 深青色標題背景矩形
    pdf.set_fill_color(0, 131, 143)    # #00838F 深青綠
    pdf.rect(10, 8, 190, 26, style="F")

    pdf.set_text_color(255, 255, 255)
    use_font(17)
    pdf.set_xy(10, 10)
    pdf.cell(190, 10, safe("醫療分診對話紀錄"), align="C", ln=True)

    use_font(9)
    pdf.set_xy(10, 21)
    now_str = datetime.now().strftime("%Y 年 %m 月 %d 日  %H:%M")
    count    = len(chat_history)
    pdf.cell(190, 8, safe(f"匯出時間：{now_str}　　共 {count} 則訊息"), align="C", ln=True)

    # 免責聲明小字
    pdf.set_text_color(140, 140, 140)
    use_font(7)
    pdf.set_xy(10, 35)
    pdf.cell(190, 5,
             safe("⚕ 本紀錄僅供參考，不能替代正式醫療診斷。緊急狀況請撥 119。"),
             align="C", ln=True)

    pdf.ln(4)

    # ── 逐則輸出訊息 ─────────────────────────────────────────
    for msg in chat_history:
        role    = msg.get("role", "")
        content = msg.get("content", "").strip()
        if not content:
            continue

        if role == "user":
            # 使用者：淺青藍背景
            pdf.set_fill_color(178, 235, 242)  # #B2EBF2
            pdf.set_text_color(0,   54,  58)   # #00363A
            label = safe("  您（患者）")
        else:
            # AI 護理師：淺綠背景
            pdf.set_fill_color(232, 245, 233)  # #E8F5E9
            pdf.set_text_color(27,  94,  32)   # #1B5E20
            label = safe("  分診護理師 AI")

        # 角色標籤列
        use_font(10)
        pdf.set_x(10)
        pdf.cell(190, 8, label, border=0, ln=True, fill=True)

        # 訊息內容（支援自動換行）
        pdf.set_text_color(30, 30, 30)
        use_font(10)
        pdf.set_x(14)
        pdf.multi_cell(182, 6, txt=safe(content), border=0, align="L", fill=False)

        # 細分隔線
        pdf.set_draw_color(200, 200, 200)
        pdf.set_x(10)
        pdf.cell(190, 2, "", border="B", ln=True)
        pdf.ln(1)

    # ── 寫出檔案 ─────────────────────────────────────────────
    try:
        pdf.output(filepath)
        return True, filepath
    except Exception as e:
        return False, f"寫入 PDF 時發生錯誤：{e}"


# ── 對話 JSON 儲存 / 載入 ────────────────────────────────────

def save_conversation(history: list) -> tuple:
    """
    將對話紀錄儲存為 JSON 檔案，方便下次載入繼續。

    回傳：
        (True,  檔案路徑)  → 成功
        (False, 錯誤訊息)  → 失敗
    """
    default_name = f"triage_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    filepath = filedialog.asksaveasfilename(
        defaultextension=".json",
        filetypes=[("JSON 對話檔", "*.json"), ("所有檔案", "*.*")],
        title="儲存對話紀錄",
        initialfile=default_name,
    )
    if not filepath:
        return False, "使用者取消儲存。"

    data = {
        "saved_at": datetime.now().isoformat(),
        "messages":  history,
    }
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True, filepath
    except Exception as e:
        return False, f"儲存失敗：{e}"


def load_conversation() -> tuple:
    """
    從 JSON 檔案載入先前儲存的對話紀錄。

    回傳：
        (True,  檔案路徑, messages list)  → 成功
        (False, 錯誤訊息, [])             → 失敗
    """
    filepath = filedialog.askopenfilename(
        filetypes=[("JSON 對話檔", "*.json"), ("所有檔案", "*.*")],
        title="載入對話紀錄",
    )
    if not filepath:
        return False, "使用者取消載入。", []

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        messages = data.get("messages", [])
        if not messages:
            return False, "JSON 檔案中找不到對話紀錄。", []
        return True, filepath, messages
    except Exception as e:
        return False, f"載入失敗：{e}", []
