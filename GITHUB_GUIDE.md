# GitHub Upload Guide

Follow these steps to upload your project to GitHub:

## Step 1: Initialize Git Repository
1. Open Command Prompt or PowerShell
2. Navigate to your project folder:
   ```powershell
   cd "path\to\your\project"
   ```
3. Initialize git:
   ```bash
   git init
   ```

## Step 2: Configure Git (First Time Only)
```bash
git config --global user.name "Your Name"
git config --global user.email "your.email@example.com"
```

## Step 3: Protect Your API Key
Make sure `.env` is listed in `.gitignore` so your real SPUR API key is never uploaded.
The `.env.example` file shows the required format without exposing real credentials:
```env
OPENAI_BASE_URL="https://ai.spuric.com/v1"
OPENAI_API_KEY="your_spur_api_key_here"
```

## Step 4: Add Files (Respecting .gitignore)
```bash
git add .
```

## Step 5: Create Initial Commit
```bash
git commit -m "Initial commit - Cognitive AI SPUR Knowledge Workspace"
```

## Step 6: Create a GitHub Repository
1. Go to https://github.com
2. Log in or create an account
3. Click **+** → **New repository**
4. Name it something like `cognitive-ai-workspace`
5. Make it Public/Private as you wish
6. **DO NOT** check "Initialize with README" - we already have one!
7. Click **Create repository**

## Step 7: Link and Push to GitHub
Follow the instructions on GitHub, they will look like:
```bash
git remote add origin https://github.com/YOUR-USERNAME/YOUR-REPO-NAME.git
git branch -M main
git push -u origin main
```

## Step 8: Verify on GitHub
Go to your repository on GitHub - you should see all your files!

---

## What's Included (and what's not)

### Included in GitHub
- All Python source code (app.py, core.py, etc.)
- requirements.txt
- Configuration files (config.yaml)
- `.env.example` (API key template — not your real key)
- Batch files (run_app.bat, run_eval.bat)
- Evaluation dataset (evals/dataset.json)
- Frontend design files
- README.md

### NOT Included (thanks to .gitignore)
- `.env` (your real API key and secrets)
- `__pycache__` and compiled Python files
- Database files (*.db)
- FAISS index files (*.index, metadata.json)
- Log files (*.log)
- Personal/secret data

---

## Next Steps After Uploading

1. **Add a License**: 
   - On GitHub, go to your repo → **Add file** → **Create new file**
   - Name it `LICENSE`
   - Click **Choose a license template** and pick one (MIT recommended)
2. **Add Topics**: Go to repo settings → Manage topics (add tags like "ai", "rag", "spur", "pdf-chat")
3. **Enable Issues**: Let users report bugs or request features!
4. **Paste your GitHub link** into the **Code repository URL** field on the [Capstone Submission Page](https://learn.spuric.com/capstone)

---

## Updating Your Repo Later

When you make changes, just run:
```bash
git add .
git commit -m "Describe your changes"
git push
```
