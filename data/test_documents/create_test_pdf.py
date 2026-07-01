from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
import os

os.makedirs('data/test_documents', exist_ok=True)

c = canvas.Canvas("data/test_documents/sample_report.pdf", pagesize=letter)
width, height = letter

c.setFont("Helvetica-Bold", 24)
c.drawString(100, height - 100, "Sample Project Report")

c.setFont("Helvetica", 12)
y = height - 150

c.setFont("Helvetica-Bold", 16)
c.drawString(100, y, "1. Introduction")
y -= 30
c.setFont("Helvetica", 12)
intro_text = [
    "This is a sample project report created for testing the PDF Chat Assistant application.",
    "The purpose of this document is to provide test data that can be used to evaluate",
    "the system's ability to retrieve information and answer questions accurately."
]
for line in intro_text:
    c.drawString(100, y, line)
    y -= 20

y -= 20
c.setFont("Helvetica-Bold", 16)
c.drawString(100, y, "2. Project Overview")
y -= 30
c.setFont("Helvetica", 12)
overview_text = [
    "Project Title: AI-Powered Document Analysis System",
    "Author: John Doe",
    "Date: July 1, 2026",
    "Version: 1.0"
]
for line in overview_text:
    c.drawString(100, y, line)
    y -= 20

y -= 20
c.setFont("Helvetica-Bold", 16)
c.drawString(100, y, "3. Key Features")
y -= 30
c.setFont("Helvetica", 12)
features = [
    "  • PDF text extraction and processing",
    "  • Text chunking and embedding",
    "  • Vector similarity search using FAISS",
    "  • Local AI model integration via Ollama",
    "  • SQLite for data persistence",
    "  • Desktop UI with tkinter"
]
for line in features:
    c.drawString(100, y, line)
    y -= 20

y -= 20
c.setFont("Helvetica-Bold", 16)
c.drawString(100, y, "4. Technical Details")
y -= 30
c.setFont("Helvetica", 12)
technical = [
    "The system uses the following components:",
    "  - Embedding model: all-minilm:l6-v2",
    "  - Chat model: qwen2.5:3b",
    "  - Vector store: FAISS",
    "  - Database: SQLite",
    "  - GUI framework: tkinter"
]
for line in technical:
    c.drawString(100, y, line)
    y -= 20

y -= 20
c.setFont("Helvetica-Bold", 16)
c.drawString(100, y, "5. Performance Metrics")
y -= 30
c.setFont("Helvetica", 12)
metrics = [
    "Average response time: 2-3 seconds",
    "Accuracy on factual questions: 85%",
    "Chunk size: 500 characters",
    "Overlap: 50 characters"
]
for line in metrics:
    c.drawString(100, y, line)
    y -= 20

y -= 20
c.setFont("Helvetica-Bold", 16)
c.drawString(100, y, "6. Conclusion")
y -= 30
c.setFont("Helvetica", 12)
conclusion = [
    "This project demonstrates a lightweight, local-only solution for document analysis.",
    "All processing happens on the user's machine, ensuring data privacy and sovereignty.",
    "Future improvements could include multi-language support and better PDF image extraction."
]
for line in conclusion:
    c.drawString(100, y, line)
    y -= 20

y -= 20
c.setFont("Helvetica-Bold", 16)
c.drawString(100, y, "7. Recommendations")
y -= 30
c.setFont("Helvetica", 12)
recommendations = [
    "1. Use larger models for improved accuracy",
    "2. Add batch processing for multiple PDFs",
    "3. Implement export functionality for chat history",
    "4. Add support for additional document formats"
]
for line in recommendations:
    c.drawString(100, y, line)
    y -= 20

c.save()
print("Test PDF created at data/test_documents/sample_report.pdf")
