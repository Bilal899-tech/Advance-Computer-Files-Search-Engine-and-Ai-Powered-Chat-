# 🚀 GitHub Upload Guide

Follow these steps to upload your project to GitHub:

## Step 1: Initialize Git Repository
1. Open Command Prompt or PowerShell
2. Navigate to your project folder:
   ```powershell
   cd "c:\Users\david\OneDrive\Desktop\new skills\a professional Ai works\Spuric\intro ai assignment\Third Try"
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

## Step 3: Add Files (Respecting .gitignore)
```bash
git add .
```

## Step 4: Create Initial Commit
```bash
git commit -m "Initial commit - Cognitive AI Local Knowledge Workspace"
```

## Step 5: Create a GitHub Repository
1. Go to https://github.com
2. Log in or create an account
3. Click **+** → **New repository**
4. Name it something like `cognitive-ai-workspace`
5. Make it Public/Private as you wish
6. **DO NOT** check "Initialize with README" - we already have one!
7. Click **Create repository**

## Step 6: Link and Push to GitHub
Follow the instructions on GitHub, they will look like:
```bash
git remote add origin https://github.com/YOUR-USERNAME/YOUR-REPO-NAME.git
git branch -M main
git push -u origin main
```

## Step 7: Verify on GitHub
Go to your repository on GitHub - you should see all your files!

---

## 📝 What's Included (and what's not)

### ✅ Included in GitHub
- All Python source code (app.py, core.py, etc.)
- requirements.txt and strict.requrements.txt
- Configuration files (config.yaml)
- Batch files (run_app.bat, run_eval.bat)
- Evaluation dataset (evals/dataset.json)
- Frontend design files
- README.md

### ❌ NOT Included (thanks to .gitignore)
- All .txt files (strictly ignored)
- __pycache__ and compiled Python files
- Database files (*.db)
- FAISS index files (*.index, metadata.json)
- Log files (*.log)
- Personal/secret data
- Test documents (optional - you can remove from .gitignore if you want to share)

---

## 🎯 Next Steps After Uploading

1. **Add a License**: 
   - On GitHub, go to your repo → **Add file** → **Create new file**
   - Name it `LICENSE`
   - Click **Choose a license template** and pick one (MIT recommended)
2. **Add Topics**: Go to repo settings → Manage topics (add tags like "ai", "rag", "local-llm", "pdf-chat")
3. **Enable Issues**: Let users report bugs or request features!

---

## 📦 Updating Your Repo Later

When you make changes, just run:
```bash
git add .
git commit -m "Describe your changes"
git push
```
