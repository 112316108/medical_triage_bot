# ============================================================
# evaluate.py  ─  分診準確度評估
# 說明：以 TTAS 標註的測試情境呼叫 AI，比較不同提示詞設定的分診表現
# 用法：python evaluation/evaluate.py            （跑全部設定）
#       python evaluation/evaluate.py --limit 5  （先試跑 5 題）
# 結果：evaluation/results/  （原始回應 jsonl、metrics.json、report.md）
# ============================================================

import argparse
import json
import os
import re
import sys
import time

from dotenv import load_dotenv
from groq import Groq

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
from prompts import SYSTEM_PROMPT, SYSTEM_PROMPT_SIMPLE, TTAS_ADDON  # noqa: E402

load_dotenv(os.path.join(ROOT, ".env"))

RESULTS_DIR = os.path.join(HERE, "results")
MODELS = ["openai/gpt-oss-120b", "qwen/qwen3.8-27b"]

# 實驗設定：名稱 → (系統提示詞, 是否要求輸出 TTAS 級數)
CONDITIONS = {
    "pro":    (SYSTEM_PROMPT, False),               # 原始專業模式（三色燈號）
    "simple": (SYSTEM_PROMPT_SIMPLE, False),        # 簡易白話模式（三色燈號）
    "ttas":   (SYSTEM_PROMPT + TTAS_ADDON, True),   # 加入 TTAS 五級標準
}

LIGHTS = ["red", "yellow", "green"]           # 由急到緩
LIGHT_RANK = {l: i for i, l in enumerate(LIGHTS)}
TTAS_TO_LIGHT = {1: "red", 2: "red", 3: "yellow", 4: "green", 5: "green"}
LIGHT_PATTERNS = {"red": ("🔴", "紅燈"), "yellow": ("🟡", "黃燈"), "green": ("🟢", "綠燈")}


# ── 回應解析 ─────────────────────────────────────────────────

def _lights_in(text: str):
    """依出現順序回傳文字中出現的不重複燈號"""
    found = []
    for light, keys in LIGHT_PATTERNS.items():
        pos = [text.find(k) for k in keys if k in text]
        if pos:
            found.append((min(pos), light))
    return [l for _, l in sorted(found)]


def parse_light(reply: str):
    """
    取出回應中的燈號，無法明確判定時回傳 None（未判定）。
    模型有時會照抄格式範本（「🔴 紅燈 / 🟡 黃燈 / 🟢 綠燈：🟢 綠燈」），
    因此同一行出現多個燈號時只看最後一個冒號後的文字，仍有多個則略過該行。
    優先序：「緊急程度」那一行 → 粗體標示的行 → 全文唯一出現的燈號。
    """
    cands = []
    for line in reply.splitlines():
        lights = _lights_in(line)
        if len(lights) > 1:
            lights = _lights_in(re.split(r"[:：]", line)[-1])
        if len(lights) != 1:
            continue
        cands.append({"light": lights[0], "urgency": "緊急程度" in line, "bold": "**" in line})
    for key in ("urgency", "bold"):
        picked = [c["light"] for c in cands if c[key]]
        if picked:
            return picked[0]
    distinct = {c["light"] for c in cands}
    return distinct.pop() if len(distinct) == 1 else None


def parse_ttas(reply: str):
    """取出【TTAS 級數】第 X 級，找不到回傳 None"""
    m = re.search(r"TTAS\s*級數[】:：\s]*第?\s*([1-5１-５])", reply)
    if not m:
        return None
    return int(m.group(1).translate(str.maketrans("１２３４５", "12345")))


# ── 指標計算 ─────────────────────────────────────────────────

def quadratic_kappa(truth, pred, k):
    """二次加權 Cohen's kappa；類別以 0..k-1 表示"""
    n = len(truth)
    if n == 0:
        return None
    obs = [[0] * k for _ in range(k)]
    for t, p in zip(truth, pred):
        obs[t][p] += 1
    row = [sum(r) for r in obs]
    col = [sum(obs[i][j] for i in range(k)) for j in range(k)]
    num = den = 0.0
    for i in range(k):
        for j in range(k):
            w = (i - j) ** 2 / (k - 1) ** 2
            num += w * obs[i][j]
            den += w * row[i] * col[j] / n
    return 1 - num / den if den else None


def light_metrics(rows):
    """三色燈號層級指標；未判定的題目算錯，並單獨統計"""
    n = len(rows)
    decided = [r for r in rows if r["pred_light"]]
    correct = sum(r["pred_light"] == r["true_light"] for r in decided)
    under = sum(LIGHT_RANK[r["pred_light"]] > LIGHT_RANK[r["true_light"]] for r in decided)
    over = sum(LIGHT_RANK[r["pred_light"]] < LIGHT_RANK[r["true_light"]] for r in decided)
    critical = [r for r in rows if r["ttas"] <= 2]
    crit_hit = sum(r["pred_light"] == "red" for r in critical)
    confusion = {t: {p: 0 for p in LIGHTS + ["none"]} for t in LIGHTS}
    for r in rows:
        confusion[r["true_light"]][r["pred_light"] or "none"] += 1
    return {
        "n": n,
        "accuracy": correct / n,
        "decided_accuracy": correct / len(decided) if decided else None,
        "under_triage_rate": under / n,
        "over_triage_rate": over / n,
        "undecided_rate": (n - len(decided)) / n,
        "critical_sensitivity": crit_hit / len(critical) if critical else None,
        "kappa_quadratic": quadratic_kappa(
            [LIGHT_RANK[r["true_light"]] for r in decided],
            [LIGHT_RANK[r["pred_light"]] for r in decided], 3),
        "confusion": confusion,
    }


def ttas_metrics(rows):
    """TTAS 五級層級指標"""
    n = len(rows)
    decided = [r for r in rows if r["pred_ttas"]]
    exact = sum(r["pred_ttas"] == r["ttas"] for r in decided)
    within1 = sum(abs(r["pred_ttas"] - r["ttas"]) <= 1 for r in decided)
    under = sum(r["pred_ttas"] > r["ttas"] for r in decided)
    over = sum(r["pred_ttas"] < r["ttas"] for r in decided)
    confusion = {t: {p: 0 for p in ["1", "2", "3", "4", "5", "none"]} for t in "12345"}
    for r in rows:
        confusion[str(r["ttas"])][str(r["pred_ttas"]) if r["pred_ttas"] else "none"] += 1
    return {
        "n": n,
        "exact_accuracy": exact / n,
        "within_one_accuracy": within1 / n,
        "under_triage_rate": under / n,
        "over_triage_rate": over / n,
        "undecided_rate": (n - len(decided)) / n,
        "light_consistency": (sum(TTAS_TO_LIGHT[r["pred_ttas"]] == r["pred_light"] for r in decided)
                              / len(decided)) if decided else None,
        "kappa_quadratic": quadratic_kappa([r["ttas"] - 1 for r in decided],
                                           [r["pred_ttas"] - 1 for r in decided], 5),
        "confusion": confusion,
    }


# ── API 呼叫 ─────────────────────────────────────────────────

def ask(client, model, system_prompt, text, temperature):
    resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "system", "content": system_prompt},
                  {"role": "user", "content": text}],
        max_tokens=1024,
        temperature=temperature,
    )
    return resp.choices[0].message.content or ""


def run_condition(client, model, name, cases, temperature):
    """逐題呼叫；已完成的題目從 jsonl 讀回，中斷後可續跑"""
    system_prompt, _ = CONDITIONS[name]
    path = os.path.join(RESULTS_DIR, f"raw_{model.split('/')[-1]}_{name}.jsonl")
    done = {}
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            for line in f:
                rec = json.loads(line)
                done[rec["id"]] = rec
    with open(path, "a", encoding="utf-8") as f:
        for c in cases:
            if c["id"] in done:
                continue
            for attempt in range(6):
                try:
                    reply = ask(client, model, system_prompt, c["text"], temperature)
                    break
                except Exception as e:  # 速率限制等暫時性錯誤：等待後重試
                    wait = 20 * (attempt + 1)
                    print(f"  [{model} {name}#{c['id']}] {type(e).__name__}，{wait}s 後重試")
                    time.sleep(wait)
            else:
                raise RuntimeError(f"{name}#{c['id']} 重試失敗")
            rec = {"id": c["id"], "reply": reply}
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            f.flush()
            done[c["id"]] = rec
            print(f"  [{model} {name}] {len(done)}/{len(cases)}")
    rows = []
    for c in cases:
        reply = done[c["id"]]["reply"]
        rows.append({
            "id": c["id"], "ttas": c["ttas"], "text": c["text"],
            "true_light": TTAS_TO_LIGHT[c["ttas"]],
            "pred_light": parse_light(reply),
            "pred_ttas": parse_ttas(reply),
        })
    return rows


# ── 報告輸出 ─────────────────────────────────────────────────

def pct(x):
    return "—" if x is None else f"{x * 100:.1f}%"


def num(x):
    return "—" if x is None else f"{x:.3f}"


def write_report(all_metrics, all_rows, temperature):
    names = list(all_metrics)
    lines = [
        "# 分診評估報告",
        "",
        f"- 模型：{', '.join(f'`{m}`' for m in sorted({k.split(' · ')[0] for k in names}))}，temperature = {temperature}",
        f"- 測試題數：{all_metrics[names[0]]['light']['n']}",
        "- 燈號對照：TTAS 1–2 → 🔴、3 → 🟡、4–5 → 🟢",
        "",
        "## 三色燈號層級",
        "",
        "| 模型 / 設定 | 準確率 | 已判定題準確率 | 低估率 (under) | 高估率 (over) | 危急個案敏感度 | 未判定 | 加權 κ |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for n in names:
        m = all_metrics[n]["light"]
        lines.append(f"| {n} | {pct(m['accuracy'])} | {pct(m['decided_accuracy'])} | {pct(m['under_triage_rate'])} | "
                     f"{pct(m['over_triage_rate'])} | {pct(m['critical_sensitivity'])} | "
                     f"{pct(m['undecided_rate'])} | {num(m['kappa_quadratic'])} |")
    ttas_runs = [n for n in names if "ttas" in all_metrics[n]]
    if ttas_runs:
        lines += [
            "",
            "## TTAS 五級層級（ttas 設定）",
            "",
            "| 模型 / 設定 | 完全正確 | 誤差 ≤1 級 | 低估率 | 高估率 | 未判定 | 燈號與級數一致 | 加權 κ |",
            "|---|---|---|---|---|---|---|---|",
        ]
        for n in ttas_runs:
            m = all_metrics[n]["ttas"]
            lines.append(f"| {n} | {pct(m['exact_accuracy'])} | {pct(m['within_one_accuracy'])} | "
                         f"{pct(m['under_triage_rate'])} | {pct(m['over_triage_rate'])} | "
                         f"{pct(m['undecided_rate'])} | {pct(m['light_consistency'])} | "
                         f"{num(m['kappa_quadratic'])} |")
        for n in ttas_runs:
            lines += ["", f"**{n}** TTAS 混淆矩陣（列 = 標準答案，欄 = AI 判定）", "",
                      "| TTAS | 1 | 2 | 3 | 4 | 5 | 未判定 |", "|---|---|---|---|---|---|---|"]
            for t, row in all_metrics[n]["ttas"]["confusion"].items():
                lines.append(f"| {t} | " + " | ".join(str(v) for v in row.values()) + " |")
    lines += ["", "## 各設定燈號混淆矩陣", ""]
    for n in names:
        lines += [f"**{n}**", "", "| 標準＼AI | 🔴 | 🟡 | 🟢 | 未判定 |", "|---|---|---|---|---|"]
        for t, row in all_metrics[n]["light"]["confusion"].items():
            lines.append(f"| {t} | " + " | ".join(str(v) for v in row.values()) + " |")
        lines.append("")
    lines += ["## 低估個案（安全風險最高）", ""]
    for n in names:
        misses = [r for r in all_rows[n]
                  if r["pred_light"] and LIGHT_RANK[r["pred_light"]] > LIGHT_RANK[r["true_light"]]]
        lines.append(f"**{n}**：" + ("無" if not misses else ""))
        for r in misses:
            lines.append(f"- #{r['id']}（TTAS {r['ttas']} → AI {r['pred_light']}）{r['text']}")
        lines.append("")
    with open(os.path.join(RESULTS_DIR, "report.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def main():
    ap = argparse.ArgumentParser(description="醫療分診機器人準確度評估")
    ap.add_argument("--models", nargs="+", default=MODELS)
    ap.add_argument("--conditions", nargs="+", default=list(CONDITIONS), choices=list(CONDITIONS))
    ap.add_argument("--limit", type=int, help="只跑前 N 題（試跑用）")
    ap.add_argument("--temperature", type=float, default=0.0)
    args = ap.parse_args()

    with open(os.path.join(HERE, "test_cases.json"), encoding="utf-8") as f:
        cases = json.load(f)["cases"]
    if args.limit:
        cases = cases[:args.limit]
    os.makedirs(RESULTS_DIR, exist_ok=True)
    client = Groq(api_key=os.getenv("GROQ_API_KEY"))

    all_rows, all_metrics = {}, {}
    for model in args.models:
        for name in args.conditions:
            key = f"{model.split('/')[-1]} · {name}"
            print(f"▶ {key}")
            rows = run_condition(client, model, name, cases, args.temperature)
            all_rows[key] = rows
            all_metrics[key] = {"light": light_metrics(rows)}
            if CONDITIONS[name][1]:
                all_metrics[key]["ttas"] = ttas_metrics(rows)

    with open(os.path.join(RESULTS_DIR, "metrics.json"), "w", encoding="utf-8") as f:
        json.dump(all_metrics, f, ensure_ascii=False, indent=2)
    write_report(all_metrics, all_rows, args.temperature)
    print(f"完成 → {os.path.join(RESULTS_DIR, 'report.md')}")


if __name__ == "__main__":
    main()
