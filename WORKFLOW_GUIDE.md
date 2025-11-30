# NeuroSynth Complete Workflow Guide

## 🎯 Overview

The NeuroSynth system consists of **two integrated applications** that work together:

1. **Reference Library** (Desktop GUI) - Research & content discovery
2. **NeuroSynth CLI/API** - AI-powered synthesis engine

### The Proper Workflow

```
┌─────────────────────────────────────────────────────────────────┐
│                    STEP 1: RESEARCH PHASE                        │
│                  (Reference Library Desktop App)                 │
│                                                                   │
│  • Search your neurosurgical reference library                   │
│  • Browse textbooks, papers, guidelines                          │
│  • Filter by surgical vs clinical content                        │
│  • Select relevant pages/sections                               │
│  • Export selection to synthesis project                         │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         │ Automatic handoff via bridge
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                   STEP 2: SYNTHESIS PHASE                        │
│                    (NeuroSynth CLI/API)                          │
│                                                                   │
│  • Parse extracted sources                                       │
│  • Deduplicate similar content                                  │
│  • Generate structured outline                                   │
│  • Synthesize comprehensive chapter                             │
│  • Output LaTeX/PDF with citations                              │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🚀 Quick Start Guide

### 1. Start the Reference Library (Desktop GUI)

```bash
cd /Users/ramihatoum/neurosynth/reference-library

# Activate virtual environment
source venv/bin/activate

# Start the desktop application
python main.py
```

**What this does:**
- Opens a desktop GUI for searching your reference library
- Allows you to browse and search neurosurgical textbooks
- Categorizes content as surgical/clinical using AI
- Lets you select specific pages for synthesis

### 2. Research Your Topic

In the Reference Library GUI:

1. **Enter your search query** (e.g., "vestibular schwannoma surgical approach")
2. **Filter by content type:**
   - 🔴 Surgical - operative techniques, procedures
   - 🔵 Clinical - diagnosis, imaging, outcomes
   - ⚪ Both
3. **Review results** with AI-categorized badges
4. **Select relevant pages** from multiple sources
5. **Click "Synthesize"** to create a chapter

### 3. Synthesis Happens Automatically

The Reference Library bridge will:
1. Extract selected pages into a project directory
2. Call NeuroSynth CLI with your sources
3. Show real-time progress
4. Open the final PDF when complete

**Output location:** `~/Documents/NeuroSynth/projects/{your_topic}/`

---

## 📁 Project Structure

After synthesis, you'll have:

```
~/Documents/NeuroSynth/projects/vestibular_schwannoma_20251130/
├── sources/              # Extracted mini-PDFs with relevant pages
│   ├── youmans_ch26.pdf
│   └── greenberg_ch18.pdf
├── images/               # Filtered anatomical figures
│   ├── youmans_ch26_p15_fig1.png
│   └── greenberg_ch18_p42_fig3.png
├── output/              # Generated chapter
│   ├── vestibular_schwannoma.pdf   ← YOUR FINAL OUTPUT
│   └── vestibular_schwannoma.tex
├── manifest.json        # Metadata linking sources to content
└── project.json         # Project settings and search context
```

---

## 🔧 Advanced: Using the API (Optional)

If you want to use the API instead of desktop GUI:

### Start the API Services

```bash
cd /Users/ramihatoum/neurosynth

# Start all services (API + Worker + Redis)
docker-compose up -d

# Check status
docker-compose ps
```

**API Endpoint:** http://localhost:8000
**Documentation:** http://localhost:8000/docs

### Submit a Synthesis Job

```bash
# Create a job
curl -X POST "http://localhost:8000/jobs" \
  -H "Content-Type: application/json" \
  -d '{
    "topic": "Vestibular Schwannoma",
    "sources": ["./sources/youmans.pdf", "./sources/greenberg.pdf"]
  }'

# Check job status
curl "http://localhost:8000/jobs/{job_id}"
```

---

## 🎓 Typical Use Cases

### Use Case 1: Creating a Chapter for Grand Rounds

1. **Open Reference Library** → Search "carotid endarterectomy technique"
2. **Filter to Surgical content** (🔴)
3. **Select 5-10 key pages** from Youmans, Schmidek, etc.
4. **Click Synthesize** → Enter topic "Carotid Endarterectomy: Surgical Technique"
5. **Wait 3-5 minutes** → Get comprehensive PDF chapter

### Use Case 2: Literature Review for Research

1. **Open Reference Library** → Search "glioblastoma immunotherapy"
2. **Filter to Clinical content** (🔵)
3. **Select evidence** from multiple papers
4. **Synthesize** → Get deduplicated literature summary

### Use Case 3: Preparing for Case Presentation

1. **Search** → "chiari malformation decompression complications"
2. **Filter Both** (⚪) surgical + clinical
3. **Select** operative techniques + outcome studies
4. **Synthesize** → Complete case preparation guide

---

## 📊 System Requirements

### Reference Library (Desktop App)
- **Python:** 3.10+ (has Python 3.12)
- **OS:** macOS (you're on Darwin 25.1.0)
- **Display:** Desktop GUI required
- **Dependencies:** customtkinter, PyMuPDF, anthropic

### NeuroSynth Synthesis
- **Python:** 3.11+ (has Python 3.14)
- **LaTeX:** Installed (/Library/TeX/texbin/pdflatex)
- **API Keys:**
  - Anthropic Claude (synthesis)
  - Google Gemini (extraction)
  - Voyage AI (embeddings)

---

## 🔍 Troubleshooting

### "Reference Library won't start"

```bash
cd reference-library
source venv/bin/activate
pip install -r requirements.txt
python main.py
```

### "Synthesis fails with API key error"

Check your `.env` file has all three keys:
```bash
grep -E "^(ANTHROPIC|GOOGLE|VOYAGE)" .env
```

### "LaTeX compilation fails"

NeuroSynth will fallback to .tex output if pdflatex fails:
```bash
# Check LaTeX installation
/Library/TeX/texbin/pdflatex --version
```

### "Can't find NeuroSynth CLI"

Ensure it's in your PATH or specify location in Reference Library settings.

---

## 🎯 Key Integration Points

The Reference Library bridges to NeuroSynth via:

**File:** `reference-library/src/integration/neurosynth_bridge.py`

**What it does:**
1. Extracts selected pages from PDFs
2. Filters medical images (6-rule filter)
3. Generates manifest with search context
4. Calls NeuroSynth CLI with `neurosynth run`
5. Streams progress back to GUI
6. Opens output when complete

**NeuroSynth receives:**
- Project directory with sources
- Filtered images
- Manifest JSON with categorization metadata
- Search query context for better synthesis

---

## 📚 Additional Resources

- **NeuroSynth CLI docs:** See `README.md` in project root
- **Reference Library docs:** See `reference-library/docs/`
- **API documentation:** http://localhost:8000/docs (when running)

---

## ✅ Deployment Status

**Reference Library:**
- ✅ Desktop app ready to run
- ✅ Virtual environment configured
- ✅ AI categorization enabled

**NeuroSynth API/CLI:**
- ✅ Docker images built
- ✅ Services running (API, Worker, Redis)
- ✅ Health check passing
- ✅ API keys configured

**Integration:**
- ✅ Bridge module ready
- ✅ CLI accessible from GUI
- ✅ Project directories configured
- ✅ LaTeX toolchain available

---

## 🎉 You're Ready!

Start with the Reference Library GUI:

```bash
cd /Users/ramihatoum/neurosynth/reference-library
source venv/bin/activate
python main.py
```

Happy synthesizing! 🧠🔬
