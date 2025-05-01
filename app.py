from flask import Flask, render_template, request, redirect, url_for, send_file
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

app = Flask(__name__)

# ----------------- GPT API CALL ------------------

def call_gpt41(prompt, system_message):
    try:
        api_url = "https://models.github.ai/inference/chat/completions"  # REPLACE WITH VALID API URL
        api_key = os.getenv("GPT_API_KEY")

        headers = {
         "Authorization": f"{api_key}",
        "Content-Type": "application/json"
        }

        payload = {
            "model": "openai/gpt-4.1",  # REPLACE WITH VALID MODEL NAME
            "messages": [
                {"role": "system", "content": system_message},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.7
        }

        response = requests.post(api_url, json=payload, headers=headers)
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"].strip()
        return content
    except Exception as e:
        print(f"API call failed: {e}")
        return None

def enhance_job_description(description):
    system_message = "You are a professional resume writing assistant. Convert the given job description into concise, achievement-based resume bullet points starting with the Unicode bullet character '•' (U+2022). Do not include any introductory text, explanations, or phrases like 'Certainly! Here are...'—only provide the bullet points, with each bullet point on a new line."
    prompt = f"Convert this job description into achievement-based resume bullet points: {description}"
    content = call_gpt41(prompt, system_message)

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

def generate_cover_letter(resume_data, job_title, company):
    system_message = "You are a professional cover letter writing assistant. Write a concise, professional cover letter tailored to the given job title and company, using the candidate's resume data. Address the letter to 'Hiring Manager'. Include a greeting, introduction, 2-3 paragraphs highlighting relevant skills and experiences, and a closing. Optionally mention the candidate's location (state and country) in the introduction if relevant to the role. Do not include any introductory text like 'Here is a cover letter...'—only provide the letter content."
    location = f"{resume_data['state']}, {resume_data['country']}" if resume_data.get('state') and resume_data.get('country') else "unspecified location"
    prompt = f"Write a cover letter for {resume_data['name']} applying for the position of {job_title} at {company}. The candidate is based in {location}. Here is the candidate's resume data: Name: {resume_data['name']}, Skills: {', '.join(resume_data['skills'])}, Experience: {resume_data['experience']}, Education: {resume_data['education']}."
    content = call_gpt41(prompt, system_message)

    if not content:
        return "Unable to generate cover letter at this time."

    return content

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
                    desc = desc.strip()
                    improved_desc = enhance_job_description(desc) if desc and desc.lower() not in ["hatchnil", "latecharl"] else "Description not provided."
                    experience.append({
                        'job_title': title.strip(),
                        'company': company.strip(),
                        'start_date': start.strip() or 'N/A',
                        'end_date': end.strip() or 'Present',
                        'description': improved_desc
                    })

            # Store data in session-like variable for download
            resume_data = {
                'name': name,
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
            return render_template('form.html', error=f"An error occurred: {str(e)}")

    return render_template('form.html')

@app.route('/download_resume', methods=['POST'])
def download_resume():
    education = []  # Initialize education as an empty list
    experience = []  # Initialize experience as an empty list
    try:
        # Retrieve data from the form
        name = request.form.get('name', 'N/A')
        email = request.form.get('email', 'N/A')
        phone = request.form.get('phone', '')
        state = request.form.get('state', '')
        country = request.form.get('country', '')
        linkedin = request.form.get('linkedin', '')
        skills = request.form.getlist('skills[]')
        template = request.form.get('template', 'modern')  # Default to 'modern' if not specified

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

        # Create a PDF using reportlab
        buffer = io.BytesIO()
        p = canvas.Canvas(buffer, pagesize=letter)
        width, height = letter

        # Set initial Y position
        y_position = height - 0.75 * inch

        # Helper function to draw text and update Y position
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

        # Helper function to draw a bullet point
        def draw_bullet(x, y, color=colors.black):
            p.setFillColor(color)
            p.circle(x, y + 3, 2, fill=1)

        # Helper function to wrap text with bullet points
        def draw_bullet_text(text, font_size, indent=0.2 * inch, max_width=width - 2 * inch, x_start=inch, y_start=None, font="Helvetica", color=colors.black):
            nonlocal y_position
            if y_start is not None:
                y_position = y_start
            if font == "Times-Roman" and color == colors.black:  # Only for Classic template
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

        # Helper function to wrap plain text (no bullets)
        def draw_wrapped_text(text, font_size, x_start, y_start, max_width=width - 2 * inch, font="Helvetica", color=colors.black):
            nonlocal y_position
            y_position = y_start
            if font == "Times-Roman" and color == colors.black:  # Only for Classic template
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

        # Helper function to draw a section divider
        def draw_section_divider(start_x, end_x, y, color1, color2=None):
            nonlocal y_position
            d = Drawing(width, 20)
            if color2:  # Gradient line (simulated with two lines)
                line = Line(start_x, 0, end_x, 0)
                line.strokeColor = color1
                line.strokeWidth = 2
                d.add(line)
                line = Line(start_x, 0, end_x, 0)
                line.strokeColor = color2
                line.strokeWidth = 1
                d.add(line)
            else:  # Solid line
                line = Line(start_x, 0, end_x, 0)
                line.strokeColor = color1
                line.strokeWidth = 2
                d.add(line)
            renderPDF.draw(d, p, 0, y)
            y_position = y - 20

        # Template-specific styling
        if template == "modern":
            # Modern Template: Colored header, gradient dividers, modern typography
            # Draw header background
            p.setFillColor(HexColor("#4B0082"))  # Indigo
            p.rect(0, height - 1.5 * inch, width, 1.5 * inch, fill=1, stroke=0)

            # Name in header
            draw_text(name, inch, height - 1.2 * inch, 20, font="Helvetica", bold=True, color=colors.white)
            y_position = height - 1.7 * inch

            # Contact Information
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

            # Skills
            if skills:
                draw_text("Skills", inch, y_position, 14, bold=True, color=HexColor("#4B0082"))
                y_position -= 10
                draw_section_divider(inch, width - inch, y_position, HexColor("#4B0082"), HexColor("#00CED1"))
                y_position -= 10
                skills_text = ", ".join(skills)
                draw_wrapped_text(skills_text, 10, inch, y_position, font="Helvetica", color=colors.black)
                y_position -= 20

            # Education
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

            # Experience
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
                        point = point.lstrip("• ").strip()
                        if point:
                            draw_bullet_text(point, 10, y_start=y_position)
                    y_position -= 20

        elif template == "classic":
            # Classic Template: Black-and-white, formal typography, simple dividers
            draw_text(name, inch, y_position, 18, font="Times-Roman", bold=True, color=colors.black)
            y_position -= 20

            # Contact Information
            location = f"{state}, {country}" if state and country else (state or country or '')
            if location:
                draw_text(location, inch, y_position, 10, font="Times-Roman", color=colors.black)
                y_position -= 14
            draw_text(email, inch, y_position, 10, font="Times-Roman", color=colors.black)
            y_position -= 14
            if phone:
                draw_text(phone, inch, y_position, 10, font="Times-Roman", color=colors.black)
                y_position -= 14
            if linkedin:
                draw_text(linkedin, inch, y_position, 10, font="Times-Roman", color=colors.black)
                y_position -= 20

            # Skills
            if skills:
                draw_text("Skills", inch, y_position, 14, font="Times-Roman", bold=True, color=colors.black)
                y_position -= 10
                draw_section_divider(inch, width - inch, y_position, colors.black)
                y_position -= 10
                skills_text = ", ".join(skills)
                draw_wrapped_text(skills_text, 10, inch, y_position, font="Times-Roman", color=colors.black)
                y_position -= 20

            # Education
            if education:
                draw_text("Education", inch, y_position, 14, font="Times-Roman", bold=True, color=colors.black)
                y_position -= 10
                draw_section_divider(inch, width - inch, y_position, colors.black)
                y_position -= 10
                for edu in education:
                    draw_text(f"{edu['degree']} - {edu['institution']}", inch, y_position, 12, font="Times-Roman", bold=True)
                    y_position -= 14
                    draw_text(f"{edu['start_year']} - {edu['end_year']}", inch, y_position, 10, font="Times-Roman", color=colors.black)
                    y_position -= 20

            # Experience
            if experience:
                draw_text("Work Experience", inch, y_position, 14, font="Times-Roman", bold=True, color=colors.black)
                y_position -= 10
                draw_section_divider(inch, width - inch, y_position, colors.black)
                y_position -= 10
                for exp in experience:
                    draw_text(f"{exp['job_title']} - {exp['company']}", inch, y_position, 12, font="Times-Roman", bold=True)
                    y_position -= 14
                    draw_text(f"{exp['start_date']} - {exp['end_date']}", inch, y_position, 10, font="Times-Roman", color=colors.black)
                    y_position -= 14
                    bullet_points = exp['description'].split("\n")
                    for point in bullet_points:
                        point = point.lstrip("• ").strip()
                        if point:
                            draw_bullet_text(point, 10, y_start=y_position, font="Times-Roman", color=colors.black)
                    y_position -= 20

        elif template == "minimalist":
            # Minimalist Template: Subtle borders, minimal styling, focus on content
            draw_text(name, inch, y_position, 16, font="Helvetica", bold=True, color=colors.black)
            y_position -= 20

            # Contact Information
            location = f"{state}, {country}" if state and country else (state or country or '')
            if location:
                draw_text(location, inch, y_position, 10, font="Helvetica", color=colors.grey)
                y_position -= 14
            draw_text(email, inch, y_position, 10, font="Helvetica", color=colors.grey)
            y_position -= 14
            if phone:
                draw_text(phone, inch, y_position, 10, font="Helvetica", color=colors.grey)
                y_position -= 14
            if linkedin:
                draw_text(linkedin, inch, y_position, 10, font="Helvetica", color=colors.grey)
                y_position -= 20

            # Skills
            if skills:
                draw_text("Skills", inch, y_position, 12, font="Helvetica", bold=True, color=colors.black)
                y_position -= 10
                skills_text = ", ".join(skills)
                draw_wrapped_text(skills_text, 10, inch, y_position, font="Helvetica", color=colors.black)
                y_position -= 20

            # Education
            if education:
                draw_text("Education", inch, y_position, 12, font="Helvetica", bold=True, color=colors.black)
                y_position -= 10
                for edu in education:
                    draw_text(f"{edu['degree']} - {edu['institution']}", inch, y_position, 11, font="Helvetica", bold=True)
                    y_position -= 14
                    draw_text(f"{edu['start_year']} - {edu['end_year']}", inch, y_position, 10, font="Helvetica", color=colors.grey)
                    y_position -= 20

            # Experience
            if experience:
                draw_text("Work Experience", inch, y_position, 12, font="Helvetica", bold=True, color=colors.black)
                y_position -= 10
                for exp in experience:
                    draw_text(f"{exp['job_title']} - {exp['company']}", inch, y_position, 11, font="Helvetica", bold=True)
                    y_position -= 14
                    draw_text(f"{exp['start_date']} - {exp['end_date']}", inch, y_position, 10, font="Helvetica", color=colors.grey)
                    y_position -= 14
                    bullet_points = exp['description'].split("\n")
                    for point in bullet_points:
                        point = point.lstrip("• ").strip()
                        if point:
                            draw_bullet_text(point, 10, y_start=y_position, font="Helvetica", color=colors.grey)
                    y_position -= 20

        elif template == "creative":
            # Creative Template: Sidebar layout, bold colors, playful typography
            sidebar_width = 2.5 * inch
            main_content_x = sidebar_width + 0.5 * inch
            main_content_width = width - main_content_x - inch

            # Draw sidebar background
            p.setFillColor(HexColor("#FF4500"))  # OrangeRed
            p.rect(0, 0, sidebar_width, height, fill=1, stroke=0)

            # Sidebar content (Contact Info and Skills)
            sidebar_y = height - 1.2 * inch
            draw_text(name, 0.5 * inch, sidebar_y, 16, font="Helvetica", bold=True, color=colors.white)
            sidebar_y -= 30

            # Contact Information in Sidebar
            location = f"{state}, {country}" if state and country else (state or country or '')
            if location:
                draw_wrapped_text(location, 9, 0.5 * inch, sidebar_y, max_width=sidebar_width - inch, font="Helvetica", color=colors.white)
                sidebar_y = y_position - 14
            draw_wrapped_text(email, 9, 0.5 * inch, sidebar_y, max_width=sidebar_width - inch, font="Helvetica", color=colors.white)
            sidebar_y = y_position - 14
            if phone:
                draw_wrapped_text(phone, 9, 0.5 * inch, sidebar_y, max_width=sidebar_width - inch, font="Helvetica", color=colors.white)
                sidebar_y = y_position - 14
            if linkedin:
                draw_wrapped_text(linkedin, 9, 0.5 * inch, sidebar_y, max_width=sidebar_width - inch, font="Helvetica", color=colors.white)
                sidebar_y = y_position - 20

            # Skills in Sidebar
            if skills:
                draw_text("Skills", 0.5 * inch, sidebar_y, 12, font="Helvetica", bold=True, color=colors.white)
                sidebar_y = y_position - 10
                skills_text = ", ".join(skills)
                draw_wrapped_text(skills_text, 9, 0.5 * inch, sidebar_y, max_width=sidebar_width - inch, font="Helvetica", color=colors.white)
                sidebar_y = y_position - 20

            # Main content (Education and Experience)
            y_position = height - 1.2 * inch
            # Education
            if education:
                draw_text("Education", main_content_x, y_position, 14, font="Helvetica", bold=True, color=HexColor("#008080"))  # Teal
                y_position -= 10
                draw_section_divider(main_content_x, width - inch, y_position, HexColor("#008080"))
                y_position -= 10
                for edu in education:
                    draw_text(f"{edu['degree']} - {edu['institution']}", main_content_x, y_position, 12, font="Helvetica", bold=True)
                    y_position -= 14
                    draw_text(f"{edu['start_year']} - {edu['end_year']}", main_content_x, y_position, 10, font="Helvetica", color=colors.grey)
                    y_position -= 20

            # Experience
            if experience:
                draw_text("Work Experience", main_content_x, y_position, 14, font="Helvetica", bold=True, color=HexColor("#008080"))
                y_position -= 10
                draw_section_divider(main_content_x, width - inch, y_position, HexColor("#008080"))
                y_position -= 10
                for exp in experience:
                    draw_text(f"{exp['job_title']} - {exp['company']}", main_content_x, y_position, 12, font="Helvetica", bold=True)
                    y_position -= 14
                    draw_text(f"{exp['start_date']} - {exp['end_date']}", main_content_x, y_position, 10, font="Helvetica", color=colors.grey)
                    y_position -= 14
                    bullet_points = exp['description'].split("\n")
                    for point in bullet_points:
                        point = point.lstrip("• ").strip()
                        if point:
                            draw_bullet_text(point, 10, x_start=main_content_x, y_start=y_position, max_width=main_content_width)
                    y_position -= 20

        elif template == "professional":
            # Professional Template: Two-column layout, subtle blue accents, structured design
            sidebar_width = 2.5 * inch
            main_content_x = sidebar_width + 0.5 * inch
            main_content_width = width - main_content_x - inch

            # Draw sidebar background (light gray)
            p.setFillColor(HexColor("#F5F5F5"))
            p.rect(0, 0, sidebar_width, height, fill=1, stroke=0)

            # Sidebar content (Contact Info and Skills)
            sidebar_y = height - 1.2 * inch
            draw_text("Contact", 0.5 * inch, sidebar_y, 12, font="Helvetica", bold=True, color=HexColor("#4682B4"))  # SteelBlue
            sidebar_y -= 20

            # Contact Information in Sidebar
            location = f"{state}, {country}" if state and country else (state or country or '')
            if location:
                draw_wrapped_text(location, 9, 0.5 * inch, sidebar_y, max_width=sidebar_width - inch, font="Helvetica", color=colors.black)
                sidebar_y = y_position - 14
            draw_wrapped_text(email, 9, 0.5 * inch, sidebar_y, max_width=sidebar_width - inch, font="Helvetica", color=colors.black)
            sidebar_y = y_position - 14
            if phone:
                draw_wrapped_text(phone, 9, 0.5 * inch, sidebar_y, max_width=sidebar_width - inch, font="Helvetica", color=colors.black)
                sidebar_y = y_position - 14
            if linkedin:
                draw_wrapped_text(linkedin, 9, 0.5 * inch, sidebar_y, max_width=sidebar_width - inch, font="Helvetica", color=colors.black)
                sidebar_y = y_position - 20

            # Skills in Sidebar
            if skills:
                draw_text("Skills", 0.5 * inch, sidebar_y, 12, font="Helvetica", bold=True, color=HexColor("#4682B4"))
                sidebar_y = y_position - 20
                for skill in skills:
                    draw_bullet_text(skill, 9, x_start=0.5 * inch, y_start=sidebar_y, max_width=sidebar_width - inch, font="Helvetica", color=colors.black)
                    sidebar_y = y_position - 10

            # Main content (Name, Education, and Experience)
            y_position = height - 1.2 * inch
            draw_text(name, main_content_x, y_position, 18, font="Helvetica", bold=True, color=HexColor("#4682B4"))
            y_position -= 30

            # Education
            if education:
                draw_text("Education", main_content_x, y_position, 14, font="Helvetica", bold=True, color=HexColor("#4682B4"))
                y_position -= 10
                draw_section_divider(main_content_x, width - inch, y_position, HexColor("#4682B4"))
                y_position -= 10
                for edu in education:
                    draw_text(f"{edu['degree']} - {edu['institution']}", main_content_x, y_position, 12, font="Helvetica", bold=True)
                    y_position -= 14
                    draw_text(f"{edu['start_year']} - {edu['end_year']}", main_content_x, y_position, 10, font="Helvetica", color=colors.grey)
                    y_position -= 20

            # Experience
            if experience:
                draw_text("Work Experience", main_content_x, y_position, 14, font="Helvetica", bold=True, color=HexColor("#4682B4"))
                y_position -= 10
                draw_section_divider(main_content_x, width - inch, y_position, HexColor("#4682B4"))
                y_position -= 10
                for exp in experience:
                    draw_text(f"{exp['job_title']} - {exp['company']}", main_content_x, y_position, 12, font="Helvetica", bold=True)
                    y_position -= 14
                    draw_text(f"{exp['start_date']} - {exp['end_date']}", main_content_x, y_position, 10, font="Helvetica", color=colors.grey)
                    y_position -= 14
                    bullet_points = exp['description'].split("\n")
                    for point in bullet_points:
                        point = point.lstrip("• ").strip()
                        if point:
                            draw_bullet_text(point, 10, x_start=main_content_x, y_start=y_position, max_width=main_content_width)
                    y_position -= 20

        # Finalize PDF
        p.showPage()
        p.save()

        # Prepare the PDF for download
        buffer.seek(0)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"resume_{timestamp}.pdf"

        return send_file(
            buffer,
            as_attachment=True,
            download_name=filename,
            mimetype='application/pdf'
        )

    except Exception as e:
        return render_template('result.html', error=f"Failed to generate PDF: {str(e)}",
                              name=request.form.get('name', 'N/A'),
                              email=request.form.get('email', 'N/A'),
                              phone=request.form.get('phone', ''),
                              state=request.form.get('state', ''),
                              country=request.form.get('country', ''),
                              linkedin=request.form.get('linkedin', ''),
                              skills=request.form.getlist('skills[]'),
                              education=education if 'education' in locals() else [],
                              experience=experience if 'experience' in locals() else [])

@app.route('/generate_cover_letter', methods=['POST'])
def generate_cover_letter_route():
    try:
        # Retrieve data from the form
        name = request.form.get('name', 'N/A')
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

        for title, company, start, end, desc in zip(job_titles, companies, start_dates, end_dates, descriptions):
            experience.append({
                'job_title': title,
                'company': company,
                'start_date': start,
                'end_date': end,
                'description': desc
            })

        # Get job title and company for cover letter
        job_title = request.form.get('job_title', 'Job Title')
        company = request.form.get('company', 'Company')

        resume_data = {
            'name': name,
            'email': email,
            'phone': phone,
            'state': state,
            'country': country,
            'linkedin': linkedin,
            'skills': skills,
            'education': education,
            'experience': experience
        }

        # Generate cover letter
        cover_letter = generate_cover_letter(resume_data, job_title, company)

        # Render result page with cover letter
        return render_template('result.html', **resume_data, cover_letter=cover_letter, job_title=job_title, company=company)

    except Exception as e:
        return render_template('result.html', error=f"Failed to generate cover letter: {str(e)}",
                              name=request.form.get('name', 'N/A'),
                              email=request.form.get('email', 'N/A'),
                              phone=request.form.get('phone', ''),
                              state=request.form.get('state', ''),
                              country=request.form.get('country', ''),
                              linkedin=request.form.get('linkedin', ''),
                              skills=request.form.getlist('skills[]'),
                              education=education if 'education' in locals() else [],
                              experience=experience if 'experience' in locals() else [])

@app.route('/download_cover_letter', methods=['POST'])
def download_cover_letter():
    education = []  # Initialize education as an empty list
    experience = []  # Initialize experience as an empty list
    try:
        # Retrieve data from the form
        name = request.form.get('name', 'N/A')
        state = request.form.get('state', '')
        country = request.form.get('country', '')
        cover_letter = request.form.get('cover_letter', 'No cover letter available.')

        # Create a PDF using reportlab
        buffer = io.BytesIO()
        p = canvas.Canvas(buffer, pagesize=letter)
        width, height = letter

        # Set initial Y position
        y_position = height - inch

        # Helper function to draw text and update Y position
        def draw_text(text, font_size, bold=False, y_offset=14):
            nonlocal y_position
            p.setFont("Helvetica-Bold" if bold else "Helvetica", font_size)
            p.drawString(inch, y_position, text)
            y_position -= y_offset

        # Helper function to wrap text
        def draw_wrapped_text(text, font_size, max_width=width - 2 * inch):
            nonlocal y_position
            p.setFont("Helvetica", font_size)
            lines = []
            words = text.split()
            current_line = ""
            for word in words:
                test_line = f"{current_line} {word}".strip()
                if p.stringWidth(test_line, "Helvetica", font_size) <= max_width:
                    current_line = test_line
                else:
                    lines.append(current_line)
                    current_line = word
            if current_line:
                lines.append(current_line)

            for line in lines:
                p.drawString(inch, y_position, line)
                y_position -= 14
                if y_position < inch:
                    p.showPage()
                    y_position = height - inch

        # Draw Header (Name)
        p.setFillColor(colors.black)
        draw_text(name, 16, bold=True, y_offset=20)

        # Draw Location
        location = f"{state}, {country}" if state and country else (state or country or '')
        if location:
            draw_text(location, 12)

        # Draw Cover Letter
        draw_text("Cover Letter", 14, bold=True, y_offset=20)
        for paragraph in cover_letter.split("\n\n"):
            paragraph = paragraph.strip()
            if paragraph:
                draw_wrapped_text(paragraph, 12)
                y_position -= 10

        # Finalize PDF
        p.showPage()
        p.save()

        # Prepare the PDF for download
        buffer.seek(0)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"cover_letter_{timestamp}.pdf"

        return send_file(
            buffer,
            as_attachment=True,
            download_name=filename,
            mimetype='application/pdf'
        )

    except Exception as e:
        return render_template('result.html', error=f"Failed to generate cover letter PDF: {str(e)}",
                              name=request.form.get('name', 'N/A'),
                              email=request.form.get('email', 'N/A'),
                              phone=request.form.get('phone', ''),
                              state=request.form.get('state', ''),
                              country=request.form.get('country', ''),
                              linkedin=request.form.get('linkedin', ''),
                              skills=request.form.getlist('skills[]'),
                              education=education if 'education' in locals() else [],
                              experience=experience if 'experience' in locals() else [])

# ----------------- RUN APP ------------------

if __name__ == '__main__':
    # Get the port from the environment variable, default to 5000 if not set
    port = int(os.getenv('PORT', 5000))
    # Bind to 0.0.0.0 to allow external access (required for Render)
    app.run(host='0.0.0.0', port=port, debug=False)