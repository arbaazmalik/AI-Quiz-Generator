from flask import Flask, render_template, request, session, redirect, url_for
from groq import Groq
from dotenv import load_dotenv
import os
import json

# ----------------- Flask Setup -----------------
app = Flask(__name__)
app.secret_key = "change_this_to_any_random_secret"

# ----------------- Env & Groq Client -----------------
load_dotenv()  # loads .env file
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

client = Groq(api_key=GROQ_API_KEY)

QUIZ_TIMER_SECONDS = 120  # 2 minutes


# ----------------- Helper: Generate MCQs -----------------
def generate_mcqs_from_paragraph(paragraph):
    """
    Uses Groq (llama-3.1-8b-instant) to generate 5 MCQs from the paragraph.
    Returns a list of dicts: [{question, options, answer}, ...]
    """
    prompt = f"""
You are a quiz generator.

From the paragraph below, create exactly 5 multiple-choice questions.
Each question must have:
- "question": question text
- "options": an array of 4 options (strings)
- "answer": exactly one of the options (the correct one)

Return ONLY valid JSON (no extra text). The JSON must look like:

[
  {{
    "question": "Question text?",
    "options": ["Option A", "Option B", "Option C", "Option D"],
    "answer": "Option B"
  }},
  ...
]

Paragraph:
\"\"\"{paragraph}\"\"\"
"""

    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
        max_tokens=800,
    )

    content = response.choices[0].message.content.strip()

    # Try to parse JSON safely
    try:
        # Sometimes model might add text before/after JSON, so grab between [ ... ]
        start = content.find("[")
        end = content.rfind("]") + 1
        json_text = content[start:end]
        data = json.loads(json_text)
    except Exception as e:
        print("JSON parse error:", e)
        return []

    questions = []
    for item in data:
        q_text = item.get("question", "").strip()
        options = item.get("options", [])
        answer = item.get("answer", "").strip()

        if not q_text or not isinstance(options, list) or len(options) == 0:
            continue

        # Make sure we have at most 4 options, all strings
        clean_options = [str(o).strip() for o in options][:4]

        # If answer is not exactly in options, try to force first option as answer
        if answer not in clean_options and clean_options:
            answer = clean_options[0]

        questions.append({
            "question": q_text,
            "options": clean_options,
            "answer": answer
        })

    # Ensure exactly 5 questions if possible
    if len(questions) > 5:
        questions = questions[:5]

    return questions


# ----------------- Routes -----------------

@app.route("/", methods=["GET", "POST"])
def home():
    """
    Homepage: user pastes paragraph, clicks Generate Quiz.
    """
    if request.method == "POST":
        paragraph = request.form.get("para", "").strip()

        if not paragraph:
            return render_template("home.html", error="Please paste a paragraph first.")

        questions = generate_mcqs_from_paragraph(paragraph)

        if not questions:
            return render_template("home.html", error="Could not generate questions. Try a different paragraph or shorter text.")

        # Store questions and timer in session
        session["questions"] = questions
        session["timer_seconds"] = QUIZ_TIMER_SECONDS

        return redirect(url_for("quiz"))

    return render_template("home.html")


@app.route("/quiz", methods=["GET", "POST"])
def quiz():
    """
    Shows the quiz with timer on GET,
    evaluates answers on POST and shows result.
    """
    questions = session.get("questions")

    if not questions:
        # If no questions in session, go back home
        return redirect(url_for("home"))

    if request.method == "POST":
        score = 0
        for i, q in enumerate(questions):
            selected = request.form.get(f"q{i}")
            if selected and selected.strip() == q["answer"].strip():
                score += 1

        total = len(questions)
        return render_template("result.html", score=score, total=total)

    # GET -> show quiz page
    timer_seconds = session.get("timer_seconds", QUIZ_TIMER_SECONDS)
    return render_template("quiz.html", questions=questions, timer_seconds=timer_seconds)


@app.route("/restart")
def restart():
    """
    Clears session and restarts quiz.
    """
    session.clear()
    return redirect(url_for("home"))


if __name__ == "__main__":
    app.run(debug=True)
