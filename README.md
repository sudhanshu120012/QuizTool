# quizTool

quizTool is a Flask web app that generates quizzes from uploaded PDF files. It supports multiple-choice, fill-in-the-blank, and mixed question types. It uses OpenRouter for AI-generated questions when configured and falls back to locally generated demo questions when no API key is available.

## Features

- Upload a PDF and generate a quiz from its content
- Choose question count, difficulty level, and question type
- AI-powered generation with OpenRouter
- Demo mode fallback when no API key is available
- PDF text extraction with PyPDF2
- Quiz review with scoring and explanations
- Mixed quizzes that include both multiple-choice and fill-in-the-blank questions

## Tech Stack

- Python
- Flask
- Flask-CORS
- PyPDF2
- Requests
- HTML, CSS, and JavaScript

## Getting Started

### Prerequisites

- Python 3.10+
- An OpenRouter API key if you want live AI-generated questions

### Install

```bash
pip install -r requirements.txt
```

### Configure Environment

Create a `.env` file in the project root:

```env
OPENROUTER_API_KEY=your_openrouter_api_key_here
```

If no key is provided, the app runs in demo mode with sample questions.

### Run the App

```bash
python app.py
```

Then open:

```text
http://localhost:5000
```

## Project Structure

```text
quizTool/
├── app.py
├── requirements.txt
├── static/
│   ├── script.js
│   └── style.css
└── templates/
    └── index.html
```

## Notes

- Uploaded PDFs are processed locally by the Flask app.
- The OpenRouter API is only used when an API key is configured.
- Large or text-light PDFs may not generate good results.
