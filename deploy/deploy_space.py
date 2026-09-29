# ============================================================
# deploy_space.py  ─  部署網頁版到 Hugging Face Spaces
# 負責人：112316108
# 用法：先執行 hf auth login（貼上有 write 權限的 token），再執行
#       python deploy/deploy_space.py <你的HF帳號>/medical-triage-bot
# 會把 .env 裡的 GROQ_API_KEY 設成 Space 的 Secret（不會出現在公開檔案中）
# ============================================================

import os
import sys

from dotenv import dotenv_values
from huggingface_hub import HfApi

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 本機路徑 → Space 內的路徑
FILES = {
    "web_app.py": "web_app.py",
    "prompts.py": "prompts.py",
    "knowledge_base.json": "knowledge_base.json",
    "evaluation/evaluate.py": "evaluation/evaluate.py",
    "deploy/huggingface/requirements.txt": "requirements.txt",
    "deploy/huggingface/README.md": "README.md",
}


def main():
    if len(sys.argv) != 2 or "/" not in sys.argv[1]:
        sys.exit("用法：python deploy/deploy_space.py <HF帳號>/<space名稱>")
    repo_id = sys.argv[1]
    key = dotenv_values(os.path.join(ROOT, ".env")).get("GROQ_API_KEY")
    if not key:
        sys.exit(".env 裡找不到 GROQ_API_KEY")

    api = HfApi()
    api.create_repo(repo_id, repo_type="space", space_sdk="gradio", exist_ok=True)
    api.add_space_secret(repo_id, "GROQ_API_KEY", key)
    for local, remote in FILES.items():
        api.upload_file(path_or_fileobj=os.path.join(ROOT, local), path_in_repo=remote,
                        repo_id=repo_id, repo_type="space")
        print(f"已上傳 {local} → {remote}")
    print(f"完成！約 1–3 分鐘建置後可開啟：https://huggingface.co/spaces/{repo_id}")


if __name__ == "__main__":
    main()
