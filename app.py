import json
import os
import random
import re
from json import JSONDecodeError

import requests
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request
from flask_cors import CORS
from PyPDF2 import PdfReader

load_dotenv()

app = Flask(__name__)
CORS(app)

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "openai/gpt-4o-mini")


def extract_text_from_pdf(file_storage):
    reader = PdfReader(file_storage)
    text = []
    for page in reader.pages:
        text.append(page.extract_text() or "")
    return "\n".join(text).strip()


def chunk_text(text, max_length=600):
    words = text.split()
    chunks = []
    current = []
    current_len = 0
    for word in words:
        if current_len + len(word) + 1 > max_length and current:
            chunks.append(" ".join(current))
            current = [word]
            current_len = len(word)
        else:
            current.append(word)
            current_len += len(word) + 1
    if current:
        chunks.append(" ".join(current))
    return chunks


def build_mcq(question_text, answer, distractors, explanation):
    options = [answer] + distractors[:3]
    while len(options) < 4:
        options.append(f"Option {len(options) + 1}")
    random.shuffle(options)
    letters = ["A", "B", "C", "D"]
    return {
        "type": "mcq",
        "question": question_text,
        "options": options,
        "answer": letters[options.index(answer)],
        "explanation": explanation,
    }


def build_fill_blank(question_text, answer, explanation):
    return {
        "type": "fill_in_the_blank",
        "question": question_text,
        "answer": answer,
        "explanation": explanation,
    }


def normalize_questions(raw_questions, question_type, num_questions):
    questions = []
    for index, item in enumerate(raw_questions[:num_questions]):
        base_question = item.get("question") or f"Question {index + 1}"
        answer = item.get("answer") or "Answer"
        explanation = item.get("explanation") or "Explanation unavailable."
        distractors = item.get("options") or []

        if question_type == "fill_in_the_blank":
            questions.append(build_fill_blank(base_question, answer, explanation))
        elif question_type == "mixed":
            if index % 2 == 0:
                questions.append(
                    build_mcq(base_question, answer, distractors, explanation)
                )
            else:
                questions.append(build_fill_blank(base_question, answer, explanation))
        else:
            questions.append(build_mcq(base_question, answer, distractors, explanation))
    return questions


def generate_demo_questions(text, question_type, num_questions, difficulty):
    chunks = chunk_text(text) or ["Sample content"]
    raw_questions = []
    for index in range(num_questions):
        chunk = chunks[index % len(chunks)]
        words = re.findall(r"[A-Za-z0-9']+", chunk)
        answer = words[0] if words else f"Answer {index + 1}"
        raw_questions.append(
            {
                "question": f"According to the source, what is highlighted in section {index + 1}?",
                "answer": answer,
                "options": [
                    answer,
                    f"{answer} alt 1",
                    f"{answer} alt 2",
                    f"{answer} alt 3",
                ],
                "explanation": f"This answer is derived from the extracted PDF content for {difficulty} difficulty.",
            }
        )
    return normalize_questions(raw_questions, question_type, num_questions)


def generate_openrouter_questions(text, question_type, num_questions, difficulty):
    prompt = f"""
You generate quiz questions from PDF content.
Return ONLY valid JSON with this schema:
{{
  "questions": [
    {{
      "question": "...",
      "answer": "...",
      "options": ["...", "...", "...", "..."],
      "explanation": "..."
    }}
  ]
}}

Rules:
- Generate {num_questions} questions.
- Difficulty: {difficulty}.
- Question type: {question_type}.
- For fill_in_the_blank questions, omit the options field.
- For mixed quizzes, alternate between multiple-choice and fill-in-the-blank.
- Keep answers concise and directly supported by the source.

Source text:
{text[:12000]}
""".strip()

    response = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "http://localhost:5000",
            "X-Title": "quizTool",
        },
        json={
            "model": OPENROUTER_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.7,
        },
        timeout=90,
    )
    response.raise_for_status()
    content = response.json()["choices"][0]["message"]["content"]
    data = parse_json_payload(content)
    questions = data.get("questions", []) if isinstance(data, dict) else []
    if not questions:
        raise ValueError("OpenRouter returned no questions")
    return normalize_questions(questions, question_type, num_questions)


def parse_json_payload(content):
    try:
        return json.loads(content)
    except JSONDecodeError:
        pass

    fenced = re.search(
        r"```(?:json)?\s*(\{.*?\})\s*```", content, re.DOTALL | re.IGNORECASE
    )
    if fenced:
        try:
            return json.loads(fenced.group(1))
        except JSONDecodeError:
            pass

    start = content.find("{")
    end = content.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(content[start : end + 1])
        except JSONDecodeError:
            pass

    raise ValueError("Unable to parse OpenRouter JSON response")


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/generate-quiz", methods=["POST"])
def generate_quiz():
    question_type = request.form.get("question_type", "mcq").lower()
    if question_type not in ["mcq", "fill_in_the_blank", "mixed"]:
        return jsonify({"error": "Invalid question type"}), 400

    try:
        num_questions = max(1, int(request.form.get("num_questions", 10)))
    except ValueError:
        return jsonify({"error": "Invalid number of questions"}), 400
    difficulty = request.form.get("difficulty", "medium")
    pdf = request.files.get("pdf")
    if not pdf:
        return jsonify({"error": "PDF file is required"}), 400

    text = extract_text_from_pdf(pdf)
    if not text:
        return jsonify({"error": "Could not extract text from the uploaded PDF"}), 400

    try:
        if OPENROUTER_API_KEY:
            questions = generate_openrouter_questions(
                text, question_type, num_questions, difficulty
            )
            demo_mode = False
        else:
            questions = generate_demo_questions(
                text, question_type, num_questions, difficulty
            )
            demo_mode = True
    except Exception:
        questions = generate_demo_questions(
            text, question_type, num_questions, difficulty
        )
        demo_mode = True

    if len(questions) < num_questions:
        fallback = generate_demo_questions(
            text, question_type, num_questions, difficulty
        )
        while len(questions) < num_questions and fallback:
            questions.append(fallback[len(questions) % len(fallback)])

    questions = questions[:num_questions]

    return jsonify(
        {
            "demo_mode": demo_mode,
            "question_type": question_type,
            "questions": questions,
        }
    )


if __name__ == "__main__":
    app.run(debug=True)
