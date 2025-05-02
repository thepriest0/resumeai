from flask import Flask, render_template, request, redirect, url_for, send_file, Response
import requests
import io
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.colors import HexColor
from reportlab.graphics.shapes import Drawing, Line
from reportlab.graphics import renderPDF
from datetime import datetime
from dotenv import load_dotenv
load_dotenv()
import re
import os
import time

app = Flask(__name__)

# ----------------- GPT API CALL ------------------

def call_gpt41(prompt, system_message, variation_seed=None):
    try:
        api_url = "https://models.github.ai/inference/chat/completions"  # REPLACE WITH VALID API URL
        api_key = os.getenv("GPT_API_KEY")

        headers = {
            "Authorization": f"{api_key}",
            "Content-Type": "application/json"
        }

        # Add a variation mechanism to the prompt to ensure different outputs on refresh
        if variation_seed is None:
            variation_seed = str(time.time())  # Use timestamp as a seed for variation
        modified_prompt = f"{prompt}\n\n[Variation Seed: {variation_seed}] To ensure a fresh and unique response, use this seed to vary your wording, style, and examples while maintaining the core meaning and intent."

        payload = {
            "model": "openai/gpt-4.1",  # REPLACE WITH VALID MODEL NAME
            "messages": [
                {"role": "system", "content": system_message},
                {"role": "user", "content": modified_prompt}
            ],
            "temperature": 0.85,  # Slightly increase temperature for more creativity
            "max_tokens": 1500    # Allow longer responses for richer content
        }

        response = requests.post(api_url, json=payload, headers=headers)
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"].strip()
        return content
    except Exception as e:
        print(f"API call failed: {e}")
        return None

def enhance_job_description(description, variation_seed=None):
    system_message = (
        "You are a master copywriter specializing in resume writing. Convert the given job description into 3-5 concise, achievement-based resume bullet points starting with the Unicode bullet character '•' (U+2022). "
        "Use powerful action verbs, quantify achievements where possible (e.g., 'increased sales by 20%'), and incorporate industry-specific keywords to make the points stand out to recruiters. "
        "Ensure the tone is professional, persuasive, and tailored to a high-impact resume. "
        "When refreshing, generate a completely different set of bullet points with varied wording, metrics, and focus areas while maintaining the core responsibilities and achievements. "
        "Do not include any introductory text, explanations, or phrases like 'Certainly! Here are...'—only provide the bullet points, with each bullet point on a new line."
    )
    # Remove any existing bullet points or special characters to ensure clean input for the API
    clean_description = re.sub(r'^[•\-\*]\s*', '', description, flags=re.MULTILINE)
    clean_description = clean_description.strip()
    prompt = f"Convert this job description into achievement-based resume bullet points: {clean_description}"
    content = call_gpt41(prompt, system_message, variation_seed)

    if not content:
        return description if description and description.strip() not in ["hatchnil", "latecharl"] else "Description not provided."

    # Post-process to remove unwanted introductory phrases and ensure proper bullet formatting
    unwanted_phrases = [
        r"^(Certainly|Here are|Below are|Following are|These are)[\s\S]*?:\s*",
        r"^(.*?bullet points for a Product Designer role:)\s*"
    ]
    for phrase in unwanted_phrases:
        content = re.sub(phrase, "", content, flags=re.IGNORECASE)

    # Replace any hyphens or other bullet-like characters with Unicode bullet '•'
    content = re.sub(r"^[-\*]\s*", "• ", content, flags=re.MULTILINE)
    content = content.strip()

    # Ensure each line starts with a bullet point
    lines = content.split("\n")
    content = "\n".join("• " + line.lstrip("• ").strip() for line in lines if line.strip())

    return content

def generate_cover_letter(resume_data, job_title, company, variation_seed=None):
    system_message = (
        "You are a master copywriter specializing in cover letter writing. Write a concise, professional, and highly persuasive cover letter tailored to the given job title and company, using the candidate's resume data. "
        "Address the letter to 'Hiring Manager'. Include a greeting, an engaging introduction, 2-3 paragraphs highlighting the candidate’s most relevant skills, experiences, and achievements, and a strong closing with a call to action. "
        "Optionally mention the candidate's location (state and country) in the introduction if relevant to the role. Use eloquent, professional language with a touch of personality to make the letter memorable. "
        "When refreshing, generate a completely different letter with varied structure, examples, and tone (e.g., enthusiastic, confident, or empathetic) while maintaining the core message and professionalism. "
        "Do not include any introductory text like 'Here is a cover letter...'—only provide the letter content."
    )
    location = f"{resume_data['state']}, {resume_data['country']}" if resume_data.get('state') and resume_data.get('country') else "unspecified location"
    prompt = (
        f"Write a cover letter for {resume_data['name']} applying for the position of {job_title} at {company}. "
        f"The candidate is based in {location}. "
        f"Here is the candidate's resume data: "
        f"Name: {resume_data['name']}, "
        f"Job Title: {resume_data['job_title']}, "
        f"Skills: {', '.join(resume_data['skills'])}, "
        f"Experience: {resume_data['experience']}, "
        f"Education: {resume_data['education']}."
    )
    content = call_gpt41(prompt, system_message, variation_seed)

    if not content:
        return "Unable to generate cover letter at this time."

    return content

# Helper function to generate PDF (used for both preview and download)
def generate_pdf(name, job_title, email, phone, state, country, linkedin, skills, education, experience, template):
    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter

    y_position = height - 0.75 * inch

    def draw_text(text, x, y, font_size, font="Helvetica", bold=False, color=colors.black):
        nonlocal y_position
        if font == "Times-Roman" and bold:
            p.setFont("Times-Bold", font_size)
        elif font == "Helvetica" and bold:
            p.setFont("Helvetica-Bold", font_size)
        else:
            p.setFont(font, font_size)
        p.setFillColor(color)
        p.drawString(x, y, text)
        y_position = y

    def draw_bullet(x, y, color=colors.black):
        p.setFillColor(color)
        p.circle(x, y + 3, 2, fill=1)

    def draw_bullet_text(text, font_size, indent=0.2 * inch, max_width=width - 2 * inch, x_start=inch, y_start=None, font="Helvetica", color=colors.black):
        nonlocal y_position
        if y_start is not None:
            y_position = y_start
        if font == "Times-Roman" and color == colors.black:
            p.setFont("Times-Roman", font_size)
        else:
            p.setFont(font, font_size)
        p.setFillColor(color)
        lines = []
        words = text.split()
        current_line = ""
        for word in words:
            test_line = f"{current_line} {word}".strip()
            if p.stringWidth(test_line, font, font_size) <= max_width:
                current_line = test_line
            else:
                lines.append(current_line)
                current_line = word
        if current_line:
            lines.append(current_line)

        for line in lines:
            draw_bullet(x_start, y_position, color)
            p.drawString(x_start + indent, y_position, line)
            y_position -= 14
            if y_position < inch:
                p.showPage()
                y_position = height - inch

    def draw_wrapped_text(text, font_size, x_start, y_start, max_width=width - 2 * inch, font="Helvetica", color=colors.black):
        nonlocal y_position
        y_position = y_start
        if font == "Times-Roman" and color == colors.black:
            p.setFont("Times-Roman", font_size)
        else:
            p.setFont(font, font_size)
        p.setFillColor(color)
        lines = []
        words = text.split()
        current_line = ""
        for word in words:
            test_line = f"{current_line} {word}".strip()
            if p.stringWidth(test_line, font, font_size) <= max_width:
                current_line = test_line
            else:
                lines.append(current_line)
                current_line = word
        if current_line:
            lines.append(current_line)

        for line in lines:
            p.drawString(x_start, y_position, line)
            y_position -= 14
            if y_position < inch:
                p.showPage()
                y_position = height - inch

    def draw_section_divider(start_x, end_x, y, color1, color2=None):
        nonlocal y_position
        d = Drawing(width, 20)
        if color2:
            line = Line(start_x, 0, end_x, 0)
            line.strokeColor = color1
            line.strokeWidth = 2
            d.add(line)
            line = Line(start_x, 0, end_x, 0)
            line.strokeColor = color2
            line.strokeWidth = 1
            d.add(line)
        else:
            line = Line(start_x, 0, end_x, 0)
            line.strokeColor = color1
            line.strokeWidth = 2
            d.add(line)
        renderPDF.draw(d, p, 0, y)
        y_position = y - 20

    if template == "modern":
        p.setFillColor(HexColor("#4B0082"))
        p.rect(0, height - 1.5 * inch, width, 1.5 * inch, fill=1, stroke=0)
        draw_text(name, inch, height - 1.2 * inch, 20, bold=True, color=colors.white)
        if job_title:
            draw_text(job_title, inch, y_position - 20, 12, color=colors.white)
        y_position = height - 1.7 * inch
        location = f"{state}, {country}" if state and country else (state or country or '')
        if location:
            draw_text(location, inch, y_position, 10, color=colors.grey)
            y_position -= 14
        draw_text(email, inch, y_position, 10, color=colors.grey)
        y_position -= 14
        if phone:
            draw_text(phone, inch, y_position, 10, color=colors.grey)
            y_position -= 14
        if linkedin:
            draw_text(linkedin, inch, y_position, 10, color=colors.grey)
            y_position -= 20
        if skills:
            draw_text("Skills", inch, y_position, 14, bold=True, color=HexColor("#4B0082"))
            y_position -= 10
            draw_section_divider(inch, width - inch, y_position, HexColor("#4B0082"), HexColor("#00CED1"))
            y_position -= 10
            skills_text = ", ".join(skills)
            draw_wrapped_text(skills_text, 10, inch, y_position)
            y_position -= 20
        if education:
            draw_text("Education", inch, y_position, 14, bold=True, color=HexColor("#4B0082"))
            y_position -= 10
            draw_section_divider(inch, width - inch, y_position, HexColor("#4B0082"), HexColor("#00CED1"))
            y_position -= 10
            for edu in education:
                draw_text(f"{edu['degree']} - {edu['institution']}", inch, y_position, 12, bold=True)
                y_position -= 14
                draw_text(f"{edu['start_year']} - {edu['end_year']}", inch, y_position, 10, color=colors.grey)
                y_position -= 20
        if experience:
            draw_text("Work Experience", inch, y_position, 14, bold=True, color=HexColor("#4B0082"))
            y_position -= 10
            draw_section_divider(inch, width - inch, y_position, HexColor("#4B0082"), HexColor("#00CED1"))
            y_position -= 10
            for exp in experience:
                draw_text(f"{exp['job_title']} - {exp['company']}", inch, y_position, 12, bold=True)
                y_position -= 14
                draw_text(f"{exp['start_date']} - {exp['end_date']}", inch, y_position, 10, color=colors.grey)
                y_position -= 14
                bullet_points = exp['description'].split("\n")
                for point in bullet_points:
                    if point.strip():
                        draw_bullet_text(point.strip(), 10, y_start=y_position)
                y_position -= 20

    elif template == "classic":
        draw_text(name, inch, y_position, 18, "Times-Roman", bold=True)
        y_position -= 20
        if job_title:
            draw_text(job_title, inch, y_position, 12, "Times-Roman")
        y_position -= 20
        location = f"{state}, {country}" if state and country else (state or country or '')
        if location:
            draw_text(location, inch, y_position, 10, "Times-Roman")
            y_position -= 14
        draw_text(email, inch, y_position, 10, "Times-Roman")
        y_position -= 14
        if phone:
            draw_text(phone, inch, y_position, 10, "Times-Roman")
            y_position -= 14
        if linkedin:
            draw_text(linkedin, inch, y_position, 10, "Times-Roman")
            y_position -= 20
        if skills:
            draw_text("Skills", inch, y_position, 14, "Times-Roman", bold=True)
            y_position -= 10
            draw_section_divider(inch, width - inch, y_position, colors.black)
            y_position -= 10
            skills_text = ", ".join(skills)
            draw_wrapped_text(skills_text, 10, inch, y_position, "Times-Roman")
            y_position -= 20
        if education:
            draw_text("Education", inch, y_position, 14, "Times-Roman", bold=True)
            y_position -= 10
            draw_section_divider(inch, width - inch, y_position, colors.black)
            y_position -= 10
            for edu in education:
                draw_text(f"{edu['degree']} - {edu['institution']}", inch, y_position, 12, "Times-Roman", bold=True)
                y_position -= 14
                draw_text(f"{edu['start_year']} - {edu['end_year']}", inch, y_position, 10, "Times-Roman")
                y_position -= 20
        if experience:
            draw_text("Work Experience", inch, y_position, 14, "Times-Roman", bold=True)
            y_position -= 10
            draw_section_divider(inch, width - inch, y_position, colors.black)
            y_position -= 10
            for exp in experience:
                draw_text(f"{exp['job_title']} - {exp['company']}", inch, y_position, 12, "Times-Roman", bold=True)
                y_position -= 14
                draw_text(f"{exp['start_date']} - {exp['end_date']}", inch, y_position, 10, "Times-Roman")
                y_position -= 14
                bullet_points = exp['description'].split("\n")
                for point in bullet_points:
                    if point.strip():
                        draw_bullet_text(point.strip(), 10, y_start=y_position, font="Times-Roman")
                y_position -= 20

    elif template == "minimalist":
        draw_text(name, inch, y_position, 16, bold=True)
        y_position -= 20
        if job_title:
            draw_text(job_title, inch, y_position, 11)
        y_position -= 20
        location = f"{state}, {country}" if state and country else (state or country or '')
        if location:
            draw_text(location, inch, y_position, 10, color=colors.grey)
            y_position -= 14
        draw_text(email, inch, y_position, 10, color=colors.grey)
        y_position -= 14
        if phone:
            draw_text(phone, inch, y_position, 10, color=colors.grey)
            y_position -= 14
        if linkedin:
            draw_text(linkedin, inch, y_position, 10, color=colors.grey)
            y_position -= 20
        if skills:
            draw_text("Skills", inch, y_position, 12, bold=True)
            y_position -= 10
            skills_text = ", ".join(skills)
            draw_wrapped_text(skills_text, 10, inch, y_position)
            y_position -= 20
        if education:
            draw_text("Education", inch, y_position, 12, bold=True)
            y_position -= 10
            for edu in education:
                draw_text(f"{edu['degree']} - {edu['institution']}", inch, y_position, 11, bold=True)
                y_position -= 14
                draw_text(f"{edu['start_year']} - {edu['end_year']}", inch, y_position, 10, color=colors.grey)
                y_position -= 20
        if experience:
            draw_text("Work Experience", inch, y_position, 12, bold=True)
            y_position -= 10
            for exp in experience:
                draw_text(f"{exp['job_title']} - {exp['company']}", inch, y_position, 11, bold=True)
                y_position -= 14
                draw_text(f"{exp['start_date']} - {exp['end_date']}", inch, y_position, 10, color=colors.grey)
                y_position -= 14
                bullet_points = exp['description'].split("\n")
                for point in bullet_points:
                    if point.strip():
                        draw_bullet_text(point.strip(), 10, y_start=y_position)
                y_position -= 20

    elif template == "creative":
        sidebar_width = 2.5 * inch
        main_content_x = sidebar_width + 0.5 * inch
        main_content_width = width - main_content_x - inch
        p.setFillColor(HexColor("#FF4500"))
        p.rect(0, 0, sidebar_width, height, fill=1, stroke=0)
        sidebar_y = height - 1.2 * inch
        draw_text(name, 0.5 * inch, sidebar_y, 16, bold=True, color=colors.white)
        sidebar_y -= 20
        if job_title:
            draw_wrapped_text(job_title, 11, 0.5 * inch, sidebar_y, max_width=sidebar_width - inch, color=colors.white)
            sidebar_y = y_position - 20
        location = f"{state}, {country}" if state and country else (state or country or '')
        if location:
            draw_wrapped_text(location, 9, 0.5 * inch, sidebar_y, max_width=sidebar_width - inch, color=colors.white)
            sidebar_y = y_position - 14
        draw_wrapped_text(email, 9, 0.5 * inch, sidebar_y, max_width=sidebar_width - inch, color=colors.white)
        sidebar_y = y_position - 14
        if phone:
            draw_wrapped_text(phone, 9, 0.5 * inch, sidebar_y, max_width=sidebar_width - inch, color=colors.white)
            sidebar_y = y_position - 14
        if linkedin:
            draw_wrapped_text(linkedin, 9, 0.5 * inch, sidebar_y, max_width=sidebar_width - inch, color=colors.white)
            sidebar_y = y_position - 20
        if skills:
            draw_text("Skills", 0.5 * inch, sidebar_y, 12, bold=True, color=colors.white)
            sidebar_y = y_position - 10
            skills_text = ", ".join(skills)
            draw_wrapped_text(skills_text, 9, 0.5 * inch, sidebar_y, max_width=sidebar_width - inch, color=colors.white)
            sidebar_y = y_position - 20
        y_position = height - 1.2 * inch
        if education:
            draw_text("Education", main_content_x, y_position, 14, bold=True, color=HexColor("#008080"))
            y_position -= 10
            draw_section_divider(main_content_x, width - inch, y_position, HexColor("#008080"))
            y_position -= 10
            for edu in education:
                draw_text(f"{edu['degree']} - {edu['institution']}", main_content_x, y_position, 12, bold=True)
                y_position -= 14
                draw_text(f"{edu['start_year']} - {edu['end_year']}", main_content_x, y_position, 10, color=colors.grey)
                y_position -= 20
        if experience:
            draw_text("Work Experience", main_content_x, y_position, 14, bold=True, color=HexColor("#008080"))
            y_position -= 10
            draw_section_divider(main_content_x, width - inch, y_position, HexColor("#008080"))
            y_position -= 10
            for exp in experience:
                draw_text(f"{exp['job_title']} - {exp['company']}", main_content_x, y_position, 12, bold=True)
                y_position -= 14
                draw_text(f"{exp['start_date']} - {exp['end_date']}", main_content_x, y_position, 10, color=colors.grey)
                y_position -= 14
                bullet_points = exp['description'].split("\n")
                for point in bullet_points:
                    if point.strip():
                        draw_bullet_text(point.strip(), 10, x_start=main_content_x, y_start=y_position, max_width=main_content_width)
                y_position -= 20

    elif template == "professional":
        sidebar_width = 2.5 * inch
        main_content_x = sidebar_width + 0.5 * inch
        main_content_width = width - main_content_x - inch
        p.setFillColor(HexColor("#F5F5F5"))
        p.rect(0, 0, sidebar_width, height, fill=1, stroke=0)
        sidebar_y = height - 1.2 * inch
        draw_text("Contact", 0.5 * inch, sidebar_y, 12, bold=True, color=HexColor("#4682B4"))
        sidebar_y -= 20
        location = f"{state}, {country}" if state and country else (state or country or '')
        if location:
            draw_wrapped_text(location, 9, 0.5 * inch, sidebar_y, max_width=sidebar_width - inch)
            sidebar_y = y_position - 14
        draw_wrapped_text(email, 9, 0.5 * inch, sidebar_y, max_width=sidebar_width - inch)
        sidebar_y = y_position - 14
        if phone:
            draw_wrapped_text(phone, 9, 0.5 * inch, sidebar_y, max_width=sidebar_width - inch)
            sidebar_y = y_position - 14
        if linkedin:
            draw_wrapped_text(linkedin, 9, 0.5 * inch, sidebar_y, max_width=sidebar_width - inch)
            sidebar_y = y_position - 20
        if skills:
            draw_text("Skills", 0.5 * inch, sidebar_y, 12, bold=True, color=HexColor("#4682B4"))
            sidebar_y = y_position - 20
            for skill in skills:
                draw_bullet_text(skill, 9, x_start=0.5 * inch, y_start=sidebar_y, max_width=sidebar_width - inch)
                sidebar_y = y_position - 10
        y_position = height - 1.2 * inch
        draw_text(name, main_content_x, y_position, 18, bold=True, color=HexColor("#4682B4"))
        y_position -= 20
        if job_title:
            draw_text(job_title, main_content_x, y_position, 12, color=HexColor("#4682B4"))
        y_position -= 30
        if education:
            draw_text("Education", main_content_x, y_position, 14, bold=True, color=HexColor("#4682B4"))
            y_position -= 10
            draw_section_divider(main_content_x, width - inch, y_position, HexColor("#4682B4"))
            y_position -= 10
            for edu in education:
                draw_text(f"{edu['degree']} - {edu['institution']}", main_content_x, y_position, 12, bold=True)
                y_position -= 14
                draw_text(f"{edu['start_year']} - {edu['end_year']}", main_content_x, y_position, 10, color=colors.grey)
                y_position -= 20
        if experience:
            draw_text("Work Experience", main_content_x, y_position, 14, bold=True, color=HexColor("#4682B4"))
            y_position -= 10
            draw_section_divider(main_content_x, width - inch, y_position, HexColor("#4682B4"))
            y_position -= 10
            for exp in experience:
                draw_text(f"{exp['job_title']} - {exp['company']}", main_content_x, y_position, 12, bold=True)
                y_position -= 14
                draw_text(f"{exp['start_date']} - {exp['end_date']}", main_content_x, y_position, 10, color=colors.grey)
                y_position -= 14
                bullet_points = exp['description'].split("\n")
                for point in bullet_points:
                    if point.strip():
                        draw_bullet_text(point.strip(), 10, x_start=main_content_x, y_start=y_position, max_width=main_content_width)
                y_position -= 20

    p.showPage()
    p.save()
    buffer.seek(0)
    return buffer

# Helper function to generate cover letter PDF
def generate_cover_letter_pdf(name, state, country, cover_letter):
    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter

    y_position = height - 0.75 * inch

    def draw_text(text, x, y, font_size, font="Helvetica", bold=False, color=colors.black):
        nonlocal y_position
        if bold:
            p.setFont(f"{font}-Bold", font_size)
        else:
            p.setFont(font, font_size)
        p.setFillColor(color)
        p.drawString(x, y, text)
        y_position = y

    def draw_wrapped_text(text, font_size, x_start, y_start, max_width=width - 2 * inch, font="Helvetica", color=colors.black):
        nonlocal y_position
        y_position = y_start
        p.setFont(font, font_size)
        p.setFillColor(color)
        lines = []
        words = text.split()
        current_line = ""
        for word in words:
            test_line = f"{current_line} {word}".strip()
            if p.stringWidth(test_line, font, font_size) <= max_width:
                current_line = test_line
            else:
                lines.append(current_line)
                current_line = word
        if current_line:
            lines.append(current_line)

        for line in lines:
            p.drawString(x_start, y_position, line)
            y_position -= 14
            if y_position < inch:
                p.showPage()
                y_position = height - inch

    # Header: Name and Contact Info
    draw_text(name, inch, y_position, 16, bold=True)
    y_position -= 20
    location = f"{state}, {country}" if state and country else (state or country or '')
    if location:
        draw_text(location, inch, y_position, 10, color=colors.grey)
        y_position -= 14
    y_position -= 20

    # Current Date
    current_date = datetime.now().strftime("%B %d, %Y")
    draw_text(current_date, inch, y_position, 10)
    y_position -= 30

    # Recipient
    draw_text("Hiring Manager", inch, y_position, 10)
    y_position -= 30

    # Cover Letter Content
    draw_wrapped_text(cover_letter, 10, inch, y_position)

    p.showPage()
    p.save()
    buffer.seek(0)
    return buffer

# ----------------- ROUTES ------------------

@app.route('/')
def landing():
    return render_template('landingpage.html')

@app.route('/form', methods=['GET', 'POST'])
def form():
    if request.method == 'POST':
        try:
            # ---------- Collect personal info ----------
            name = request.form.get('fullname', '').strip()
            job_title = request.form.get('job_title', '').strip()
            email = request.form.get('email', '').strip()
            phone = request.form.get('phone', '').strip()
            state = request.form.get('state', '').strip()
            country = request.form.get('country', '').strip()
            linkedin = request.form.get('linkedin', '').strip()

            if not name or not email:
                return render_template('form.html', error="Full Name and Email are required.")

            # ---------- Skills ----------
            skills = request.form.getlist('skills[]')
            skills = [skill.strip() for skill in skills if skill.strip()]

            # ---------- Education ----------
            education = []
            degrees = request.form.getlist('degree[]')
            institutions = request.form.getlist('institution[]')
            start_years = request.form.getlist('start_year[]')
            end_years = request.form.getlist('end_year[]')

            for degree, institution, start, end in zip(degrees, institutions, start_years, end_years):
                if degree.strip() and institution.strip():
                    education.append({
                        'degree': degree.strip(),
                        'institution': institution.strip(),
                        'start_year': start.strip() or 'N/A',
                        'end_year': end.strip() or 'N/A'
                    })

            # ---------- Experience ----------
            experience = []
            job_titles = request.form.getlist('job_title[]')
            companies = request.form.getlist('company[]')
            start_dates = request.form.getlist('start_date[]')
            end_dates = request.form.getlist('end_date[]')
            descriptions = request.form.getlist('description[]')

            for title, company, start, end, desc in zip(job_titles, companies, start_dates, end_dates, descriptions):
                if title.strip() and company.strip():
                    raw_desc = desc.strip() or "Description not provided."
                    # Clean description by removing bullet points before processing
                    clean_desc = re.sub(r'^[•\-\*]\s*', '', raw_desc, flags=re.MULTILINE).strip()
                    improved_desc = enhance_job_description(clean_desc) if clean_desc and clean_desc.lower() not in ["hatchnil", "latecharl"] else "Description not provided."
                    experience.append({
                        'job_title': title.strip(),
                        'company': company.strip(),
                        'start_date': start.strip() or 'N/A',
                        'end_date': end.strip() or 'Present',
                        'raw_description': raw_desc,  # Store the raw description
                        'description': improved_desc  # Store the AI-enhanced description
                    })

            resume_data = {
                'name': name,
                'job_title': job_title,
                'email': email,
                'phone': phone,
                'state': state,
                'country': country,
                'linkedin': linkedin,
                'skills': skills,
                'education': education,
                'experience': experience
            }

            return render_template('result.html', **resume_data)

        except Exception as e:
            return render_template('form.html', error=f"An error occurred while processing the form: {str(e)}")

    # Handle edit case
    elif request.args.get('edit') == '1':
        try:
            name = request.args.get('name', '')
            job_title = request.args.get('job_title', '')
            email = request.args.get('email', '')
            phone = request.args.get('phone', '')
            state = request.args.get('state', '')
            country = request.args.get('country', '')
            linkedin = request.args.get('linkedin', '')

            # Ensure skills is a list
            skills = request.args.getlist('skills[]')
            if not isinstance(skills, list):
                skills = []

            # Ensure education is a list of dictionaries
            education = []
            degrees = request.args.getlist('education_degree[]')
            institutions = request.args.getlist('education_institution[]')
            start_years = request.args.getlist('education_start_year[]')
            end_years = request.args.getlist('education_end_year[]')

            for degree, institution, start, end in zip(degrees, institutions, start_years, end_years):
                education.append({
                    'degree': degree or '',
                    'institution': institution or '',
                    'start_year': start or '',
                    'end_year': end or ''
                })

            # Ensure experience is a list of dictionaries
            experience = []
            job_titles = request.args.getlist('experience_job_title[]')
            companies = request.args.getlist('experience_company[]')
            start_dates = request.args.getlist('experience_start_date[]')
            end_dates = request.args.getlist('experience_end_date[]')
            raw_descriptions = request.args.getlist('experience_raw_description[]')

            for title, company, start, end, raw_desc in zip(
                job_titles, companies, start_dates, end_dates, raw_descriptions
            ):
                experience.append({
                    'job_title': title or '',
                    'company': company or '',
                    'start_date': start or '',
                    'end_date': end or '',
                    'description': raw_desc or ''  # Use raw_description for editing
                })

            return render_template('form.html', 
                                 name=name, 
                                 job_title=job_title, 
                                 email=email, 
                                 phone=phone, 
                                 state=state, 
                                 country=country, 
                                 linkedin=linkedin, 
                                 skills=skills, 
                                 education=education, 
                                 experience=experience)

        except Exception as e:
            return render_template('form.html', error=f"Failed to load edit form: {str(e)}")

    return render_template('form.html')

@app.route('/preview_resume', methods=['POST'])
def preview_resume():
    try:
        name = request.form.get('name', 'N/A')
        job_title = request.form.get('job_title', '')
        email = request.form.get('email', 'N/A')
        phone = request.form.get('phone', '')
        state = request.form.get('state', '')
        country = request.form.get('country', '')
        linkedin = request.form.get('linkedin', '')
        skills = request.form.getlist('skills[]')
        template = request.form.get('template', 'modern')

        education = []
        for degree, institution, start, end in zip(
            request.form.getlist('education_degree[]'),
            request.form.getlist('education_institution[]'),
            request.form.getlist('education_start_year[]'),
            request.form.getlist('education_end_year[]')
        ):
            education.append({
                'degree': degree,
                'institution': institution,
                'start_year': start,
                'end_year': end
            })

        experience = []
        for title, company, start, end, desc in zip(
            request.form.getlist('experience_job_title[]'),
            request.form.getlist('experience_company[]'),
            request.form.getlist('experience_start_date[]'),
            request.form.getlist('experience_end_date[]'),
            request.form.getlist('experience_description[]')
        ):
            experience.append({
                'job_title': title,
                'company': company,
                'start_date': start,
                'end_date': end,
                'description': desc
            })

        buffer = generate_pdf(name, job_title, email, phone, state, country, linkedin, skills, education, experience, template)
        return Response(buffer.getvalue(), mimetype='application/pdf')

    except Exception as e:
        return render_template('result.html', error=f"Failed to generate preview: {str(e)}",
                              name=request.form.get('name', 'N/A'),
                              job_title=request.form.get('job_title', ''),
                              email=request.form.get('email', 'N/A'),
                              phone=request.form.get('phone', ''),
                              state=request.form.get('state', ''),
                              country=request.form.get('country', ''),
                              linkedin=request.form.get('linkedin', ''),
                              skills=request.form.getlist('skills[]'),
                              education=education if 'education' in locals() else [],
                              experience=experience if 'experience' in locals() else [])

@app.route('/download_resume', methods=['POST'])
def download_resume():
    try:
        name = request.form.get('name', 'N/A')
        job_title = request.form.get('job_title', '')
        email = request.form.get('email', 'N/A')
        phone = request.form.get('phone', '')
        state = request.form.get('state', '')
        country = request.form.get('country', '')
        linkedin = request.form.get('linkedin', '')
        skills = request.form.getlist('skills[]')
        template = request.form.get('template', 'modern')

        education = []
        for degree, institution, start, end in zip(
            request.form.getlist('education_degree[]'),
            request.form.getlist('education_institution[]'),
            request.form.getlist('education_start_year[]'),
            request.form.getlist('education_end_year[]')
        ):
            education.append({
                'degree': degree,
                'institution': institution,
                'start_year': start,
                'end_year': end
            })

        experience = []
        for title, company, start, end, desc in zip(
            request.form.getlist('experience_job_title[]'),
            request.form.getlist('experience_company[]'),
            request.form.getlist('experience_start_date[]'),
            request.form.getlist('experience_end_date[]'),
            request.form.getlist('experience_description[]')
        ):
            experience.append({
                'job_title': title,
                'company': company,
                'start_date': start,
                'end_date': end,
                'description': desc
            })

        buffer = generate_pdf(name, job_title, email, phone, state, country, linkedin, skills, education, experience, template)
        safe_name = re.sub(r'[^a-zA-Z0-9]', '_', name.lower())
        filename = f"{safe_name}_resume.pdf"

        return send_file(
            buffer,
            as_attachment=True,
            download_name=filename,
            mimetype='application/pdf'
        )

    except Exception as e:
        return render_template('result.html', error=f"Failed to generate PDF: {str(e)}",
                              name=request.form.get('name', 'N/A'),
                              job_title=request.form.get('job_title', ''),
                              email=request.form.get('email', 'N/A'),
                              phone=request.form.get('phone', ''),
                              state=request.form.get('state', ''),
                              country=request.form.get('country', ''),
                              linkedin=request.form.get('linkedin', ''),
                              skills=request.form.getlist('skills[]'),
                              education=education if 'education' in locals() else [],
                              experience=experience if 'experience' in locals() else [])

@app.route('/refresh_resume', methods=['GET'])
def refresh_resume():
    try:
        name = request.args.get('name', 'N/A')
        job_title = request.args.get('job_title', '')
        email = request.args.get('email', 'N/A')
        phone = request.args.get('phone', '')
        state = request.args.get('state', '')
        country = request.args.get('country', '')
        linkedin = request.args.get('linkedin', '')
        skills = request.args.getlist('skills[]')
        education = []
        for degree, institution, start, end in zip(
            request.args.getlist('education_degree[]'),
            request.args.getlist('education_institution[]'),
            request.args.getlist('education_start_year[]'),
            request.args.getlist('education_end_year[]')
        ):
            education.append({'degree': degree, 'institution': institution, 'start_year': start, 'end_year': end})

        # Rebuild experience and regenerate descriptions
        experience = []
        variation_seed = str(time.time())  # Use timestamp for variation
        for title, company, start, end, raw_desc in zip(
            request.args.getlist('experience_job_title[]'),
            request.args.getlist('experience_company[]'),
            request.args.getlist('experience_start_date[]'),
            request.args.getlist('experience_end_date[]'),
            request.args.getlist('experience_raw_description[]')  # Use raw description
        ):
            # Regenerate the description using the raw input with a variation seed
            improved_desc = enhance_job_description(raw_desc, variation_seed=variation_seed) if raw_desc and raw_desc.lower() not in ["hatchnil", "latecharl"] else "Description not provided."
            experience.append({
                'job_title': title,
                'company': company,
                'start_date': start,
                'end_date': end,
                'raw_description': raw_desc,
                'description': improved_desc
            })

        return render_template('result.html', name=name, job_title=job_title, email=email, phone=phone, state=state, country=country, linkedin=linkedin, skills=skills, education=education, experience=experience)

    except Exception as e:
        return render_template('result.html', error=f"Failed to refresh resume: {str(e)}",
                              name=request.args.get('name', 'N/A'),
                              job_title=request.args.get('job_title', ''),
                              email=request.args.get('email', 'N/A'),
                              phone=request.args.get('phone', ''),
                              state=request.args.get('state', ''),
                              country=request.args.get('country', ''),
                              linkedin=request.args.get('linkedin', ''),
                              skills=request.args.getlist('skills[]'),
                              education=education if 'education' in locals() else [],
                              experience=experience if 'experience' in locals() else [])

@app.route('/generate_cover_letter', methods=['POST'])
def generate_cover_letter_route():
    try:
        name = request.form.get('name', 'N/A')
        job_title = request.form.get('job_title', '')
        email = request.form.get('email', 'N/A')
        phone = request.form.get('phone', '')
        state = request.form.get('state', '')
        country = request.form.get('country', '')
        linkedin = request.form.get('linkedin', '')
        skills = request.form.getlist('skills[]')
        education = []
        degrees = request.form.getlist('education_degree[]')
        institutions = request.form.getlist('education_institution[]')
        start_years = request.form.getlist('education_start_year[]')
        end_years = request.form.getlist('education_end_year[]')

        for degree, institution, start, end in zip(degrees, institutions, start_years, end_years):
            education.append({
                'degree': degree,
                'institution': institution,
                'start_year': start,
                'end_year': end
            })

        experience = []
        job_titles = request.form.getlist('experience_job_title[]')
        companies = request.form.getlist('experience_company[]')
        start_dates = request.form.getlist('experience_start_date[]')
        end_dates = request.form.getlist('experience_end_date[]')
        descriptions = request.form.getlist('experience_description[]')
        raw_descriptions = request.form.getlist('experience_raw_description[]')

        for title, company, start, end, desc, raw_desc in zip(job_titles, companies, start_dates, end_dates, descriptions, raw_descriptions or [None] * len(job_titles)):
            experience.append({
                'job_title': title,
                'company': company,
                'start_date': start,
                'end_date': end,
                'raw_description': raw_desc if raw_desc else desc,
                'description': desc
            })

        cover_job_title = request.form.get('job_title', 'Job Title')
        company = request.form.get('company', 'Company')

        resume_data = {
            'name': name,
            'job_title': job_title,
            'email': email,
            'phone': phone,
            'state': state,
            'country': country,
            'linkedin': linkedin,
            'skills': skills,
            'education': education,
            'experience': experience
        }

        cover_letter = generate_cover_letter(resume_data, cover_job_title, company)
        return render_template('result.html', **resume_data, cover_letter=cover_letter, cover_job_title=cover_job_title, company=company)

    except Exception as e:
        return render_template('result.html', error=f"Failed to generate cover letter: {str(e)}",
                              name=request.form.get('name', 'N/A'),
                              job_title=request.form.get('job_title', ''),
                              email=request.form.get('email', 'N/A'),
                              phone=request.form.get('phone', ''),
                              state=request.form.get('state', ''),
                              country=request.form.get('country', ''),
                              linkedin=request.form.get('linkedin', ''),
                              skills=request.form.getlist('skills[]'),
                              education=education if 'education' in locals() else [],
                              experience=experience if 'experience' in locals() else [])

@app.route('/refresh_cover_letter', methods=['GET'])
def refresh_cover_letter():
    try:
        name = request.args.get('name', 'N/A')
        job_title = request.args.get('job_title', '')
        email = request.args.get('email', 'N/A')
        phone = request.args.get('phone', '')
        state = request.args.get('state', '')
        country = request.args.get('country', '')
        linkedin = request.args.get('linkedin', '')
        skills = request.args.getlist('skills[]')
        education = []
        for degree, institution, start, end in zip(
            request.args.getlist('education_degree[]'),
            request.args.getlist('education_institution[]'),
            request.args.getlist('education_start_year[]'),
            request.args.getlist('education_end_year[]')
        ):
            education.append({
                'degree': degree,
                'institution': institution,
                'start_year': start,
                'end_year': end
            })

        experience = []
        job_titles = request.args.getlist('experience_job_title[]')
        companies = request.args.getlist('experience_company[]')
        start_dates = request.args.getlist('experience_start_date[]')
        end_dates = request.args.getlist('experience_end_date[]')
        descriptions = request.args.getlist('experience_description[]')
        raw_descriptions = request.args.getlist('experience_raw_description[]')

        for title, company, start, end, desc, raw_desc in zip(
            job_titles, companies, start_dates, end_dates, descriptions, raw_descriptions
        ):
            experience.append({
                'job_title': title,
                'company': company,
                'start_date': start,
                'end_date': end,
                'raw_description': raw_desc if raw_desc else desc,
                'description': desc
            })

        cover_job_title = request.args.get('cover_job_title', 'Job Title')
        company = request.args.get('company', 'Company')

        resume_data = {
            'name': name,
            'job_title': job_title,
            'email': email,
            'phone': phone,
            'state': state,
            'country': country,
            'linkedin': linkedin,
            'skills': skills,
            'education': education,
            'experience': experience
        }

        variation_seed = str(time.time())  # Use timestamp for variation
        cover_letter = generate_cover_letter(resume_data, cover_job_title, company, variation_seed=variation_seed)
        return render_template('result.html', **resume_data, cover_letter=cover_letter, cover_job_title=cover_job_title, company=company)

    except Exception as e:
        return render_template('result.html', error=f"Failed to refresh cover letter: {str(e)}",
                              name=request.args.get('name', 'N/A'),
                              job_title=request.args.get('job_title', ''),
                              email=request.args.get('email', 'N/A'),
                              phone=request.args.get('phone', ''),
                              state=request.args.get('state', ''),
                              country=request.args.get('country', ''),
                              linkedin=request.args.get('linkedin', ''),
                              skills=request.args.getlist('skills[]'),
                              education=education if 'education' in locals() else [],
                              experience=experience if 'experience' in locals() else [])

@app.route('/download_cover_letter', methods=['POST'])
def download_cover_letter():
    try:
        name = request.form.get('name', 'N/A')
        state = request.form.get('state', '')
        country = request.form.get('country', '')
        cover_letter = request.form.get('cover_letter', '')

        buffer = generate_cover_letter_pdf(name, state, country, cover_letter)
        safe_name = re.sub(r'[^a-zA-Z0-9]', '_', name.lower())
        filename = f"{safe_name}_cover_letter.pdf"

        return send_file(
            buffer,
            as_attachment=True,
            download_name=filename,
            mimetype='application/pdf'
        )

    except Exception as e:
        return render_template('result.html', error=f"Failed to download cover letter: {str(e)}",
                              name=request.form.get('name', 'N/A'),
                              state=request.form.get('state', ''),
                              country=request.form.get('country', ''),
                              cover_letter=request.form.get('cover_letter', ''))

if __name__ == '__main__':
    app.run(debug=True)