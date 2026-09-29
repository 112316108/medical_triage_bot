# 🏥 醫療分診機器人 Medical Triage Bot

> 醫學資訊學系期末專題 | 2026 年 5 月

AI 分診助理，根據使用者描述的症狀，評估緊急程度（🔴🟡🟢）並建議就診科別。

---

## ✨ 功能特色

| 功能 | 說明 |
|------|------|
| 🤖 AI 分診建議 | 由 Groq Llama-3.3-70b 扮演分診護理師，給出緊急程度與建議科別 |
| 🟢🟡🔴 燈號顯示 | 綠燈（一般）、黃燈（優先）、紅燈（立即就醫）自動顯色 |
| 💬 對話記憶 | 完整保留歷史對話，AI 可整合前後症狀資訊 |
| 📄 PDF 匯出 | 一鍵將對話紀錄匯出為 PDF，支援繁體中文 |
| ⚕️ 免責聲明 | 啟動時強制顯示，使用者同意後方可使用 |
| 🎨 醫療藍綠色系介面 | tkinter 原生 UI，專業醫療視覺風格 |

---

## 📁 專案結構

```
medical_triage_bot/
├── triage_bot.py      ← 主程式（A 同學）
├── prompts.py         ← AI Prompt 設定（B 同學）
├── utils.py           ← PDF 匯出工具（C 同學）
├── .env               ← API Key（請勿上傳 Git！）
├── .gitignore
├── requirements.txt
└── README.md
```

---

## 🚀 安裝與執行步驟

### 1. 環境需求

- Python **3.10** 以上
- Windows 10 / 11（PDF 中文字型需 Windows 內建微軟正黑體）

### 2. 安裝套件

開啟終端機（cmd 或 PowerShell），切換到專案資料夾後執行：

```bash
pip install -r requirements.txt
```

### 3. 設定 API Key

編輯 `.env` 檔案，將 `gsk_xxxxx` 替換成你的 Groq API Key：

```
GROQ_API_KEY=gsk_你的真實金鑰
```

> 取得 Groq API Key：前往 https://console.groq.com → 登入 → 建立 API Key

### 4. 執行程式

```bash
python triage_bot.py
```

---

## 📖 使用說明

1. 程式啟動後，先閱讀並同意**免責聲明**
2. 在下方輸入框描述您的症狀
3. 按 **Enter** 傳送（**Shift + Enter** 可換行）
4. AI 會回覆包含緊急程度燈號、建議科別與行動建議
5. 對話結束後，點選 **📄 匯出 PDF** 儲存紀錄

### 🔴 緊急狀況提醒
若出現**胸痛、呼吸困難、意識不清**等症狀，請立即撥打 **119**，勿等候 AI 回應。

---

## 👤 開發者

本專案由單人獨立完成，涵蓋以下所有模組：

| 模組 | 檔案 | 工作內容 |
|------|------|----------|
| 主介面 | `triage_bot.py` | tkinter UI 設計、執行緒管理、Groq API 整合、對話流程控制 |
| Prompt 設計 | `prompts.py` | 系統 Prompt 撰寫、緊急程度格式定義、免責聲明文案 |
| 工具函式 | `utils.py` | PDF 匯出、中文字型處理 |
| 文件 | `README.md` | 環境設定、使用說明 |

---

## 🛠 常見問題

**Q：執行後出現「API Key 錯誤」？**
A：請確認 `.env` 中的 `GROQ_API_KEY` 已填入正確金鑰，且不包含多餘空格。

**Q：PDF 匯出後中文顯示為問號「?」？**
A：代表找不到系統中文字型。請確認 Windows 已安裝「微軟正黑體」（一般 Windows 10/11 預設已安裝）。

**Q：按傳送沒有反應？**
A：請確認網路連線正常，且 Groq API 服務可使用。

**Q：想更換 AI 模型？**
A：在 `triage_bot.py` 第 155 行修改 `model=` 的值，其他可用模型見 Groq 文件。

---

## ⚠️ 免責聲明

本系統為學術練習用途，**不具備醫療診斷資格**。任何 AI 建議均不能替代合格醫師的專業判斷。
