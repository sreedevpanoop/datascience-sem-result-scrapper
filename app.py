from flask import Flask, render_template, request, jsonify, send_from_directory
import requests
from bs4 import BeautifulSoup
import time
import io
import os
import tempfile
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER

app = Flask(__name__)

URL = "https://pareeksha.mgu.ac.in/Pareeksha/index.php/Public/PareekshaResultView_ctrl/index/3/428"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Referer": URL,
}

CS_ID = "428"  

# ── Semester configuration ──────────────────────────────────────────────────
SEMESTERS = {
    "sem1": {
        "label": "1st Semester",
        "exam_name": "First Semester Integrated MSc/MA Degree Examination – February 2024",
        "exam_date": "February 2024",
        "exam_id": "339",
        "cs_id": CS_ID,
    },
    "sem2": {
        "label": "2nd Semester",
        "exam_name": "Second Semester Integrated MSc/MA Degree Examination – June 2024",
        "exam_date": "June 2024",
        "exam_id": "407",
        "cs_id": CS_ID,
    },
    "sem3": {
        "label": "3rd Semester",
        "exam_name": "Third Semester Integrated MSc/MA Degree Examination – October 2024",
        "exam_date": "October 2024",
        "exam_id": "447",
        "cs_id": CS_ID,
    },
    "sem4": {
        "label": "4th Semester",
        "exam_name": "Fourth Semester Integrated MSc/MA Degree Examination – May 2025",
        "exam_date": "May 2025",
        "exam_id": "547",
        "cs_id": CS_ID,
    },
    "sem5": {
        "label": "5th Semester",
        "exam_name": "Fifth Semester Integrated MSc/MA Degree Examination – October 2025",
        "exam_date": "October 2025",
        "exam_id": "605",
        "cs_id": CS_ID,
    },
    "sem6": {
        "label": "6th Semester",
        "exam_name": "Sixth Semester Integrated MSc/MA Degree Examination – March 2026",
        "exam_date": "March 2026",
        "exam_id": "691",
        "cs_id": CS_ID,
    },
}


def get_label_value(soup, label_text):
    tag = soup.find(string=lambda t: t and label_text in t)
    if tag:
        parent = tag.find_parent(["td", "tr"])
        if parent:
            row = parent.find_parent("tr") or parent
            cells = [c.get_text(strip=True) for c in row.find_all("td")]
            cells = [c for c in cells if c and c != ":"]
            if len(cells) >= 2:
                return cells[-1]
    return None


def generate_prn_range(start, end):
    prefix = start[:-4]
    start_num = int(start[-4:])
    end_num = int(end[-4:])
    return [f"{prefix}{num:04d}" for num in range(start_num, end_num + 1)]


def fetch_student(session, prn, cs_id, exam_id):
    payload = {
        "cs_id": cs_id,
        "exam_id": exam_id,
        "prn": prn,
        "btnresult": "Get Result"
    }
    resp = session.post(URL, data=payload, headers=HEADERS, timeout=15)
    soup = BeautifulSoup(resp.text, "html.parser")

    name = get_label_value(soup, "Name of Student")
    reg_no = get_label_value(soup, "Permanent Register Number")

    if not name:
        return None

    subject_rows = []
    for row in soup.find_all("tr"):
        cols = [c.get_text(strip=True) for c in row.find_all("td")]
        if len(cols) == 7 and cols[0][:3].isalpha() and any(ch.isdigit() for ch in cols[0]):
            code, subject, external, internal, gpa, grade, result = cols
            subject_rows.append({
                "course_code": code,
                "subject": subject,
                "external": external,
                "internal": internal,
                "gpa": gpa,
                "grade": grade,
                "result": result
            })

    return {"name": name, "prn": reg_no or prn, "subjects": subject_rows}


@app.route("/")
def index():
    return render_template("index.html", semesters=SEMESTERS)


@app.route("/fetch", methods=["POST"])
def fetch():
    data = request.json
    start_prn = data.get("start_prn", "").strip()
    end_prn = data.get("end_prn", "").strip()
    semester_key = data.get("semester", "").strip()

    if not start_prn:
        return jsonify({"error": "Starting PRN is required."}), 400

    
    if not end_prn:
        end_prn = start_prn

    sem = SEMESTERS.get(semester_key)
    if not sem:
        return jsonify({"error": f"Invalid semester '{semester_key}'. Valid: {', '.join(SEMESTERS.keys())}"}), 400

    try:
        prn_list = generate_prn_range(start_prn, end_prn)
    except Exception as e:
        return jsonify({"error": f"Invalid PRN format: {str(e)}"}), 400

    if len(prn_list) > 100:
        return jsonify({"error": "Range too large. Max 100 PRNs at a time."}), 400

    session = requests.Session()
    results = []
    for prn in prn_list:
        student = fetch_student(session, prn, sem["cs_id"], sem["exam_id"])
        if student:
            results.append(student)
        time.sleep(1)

    return jsonify({"results": results, "total": len(results)})


@app.route("/download-pdf", methods=["POST"])
def download_pdf():
    data = request.json
    results = data.get("results", [])
    semester_key = data.get("semester", "sem6")

    sem = SEMESTERS.get(semester_key, SEMESTERS["sem6"])

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        rightMargin=1.5 * cm,
        leftMargin=1.5 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "Title",
        parent=styles["Title"],
        fontSize=16,
        spaceAfter=6,
        textColor=colors.HexColor("#1a1a2e"),
        alignment=TA_CENTER,
    )
    sub_style = ParagraphStyle(
        "Sub",
        parent=styles["Normal"],
        fontSize=9,
        spaceAfter=4,
        textColor=colors.HexColor("#555"),
        alignment=TA_CENTER,
    )
    student_style = ParagraphStyle(
        "Student",
        parent=styles["Normal"],
        fontSize=11,
        spaceBefore=12,
        spaceAfter=4,
        textColor=colors.HexColor("#16213e"),
        fontName="Helvetica-Bold",
    )

    story = []
    story.append(Paragraph("MG University Exam Results", title_style))
    story.append(Paragraph(sem["exam_name"], sub_style))
    story.append(Spacer(1, 0.4 * cm))

    COL_WIDTHS = [2.5 * cm, 7.5 * cm, 2.3 * cm, 2.3 * cm, 1.8 * cm, 1.8 * cm, 2.5 * cm]
    HEADER = ["Code", "Subject", "External", "Internal", "GPA", "Grade", "Result"]

    header_style = TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#16213e")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 9),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#f0f4ff"), colors.white]),
        ("FONTSIZE", (0, 1), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#c0c8e8")),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ])

    for student in results:
        all_passed = all(
            s.get("result", "").upper().startswith("PASS")
            for s in student["subjects"]
        ) if student["subjects"] else False
        overall_text = "PASSED" if all_passed else "FAILED"

        name_para = Paragraph(
            f"{student['name']}   &nbsp;&nbsp; PRN: {student['prn']}",
            student_style
        )
        status_para = Paragraph(
            f"<font color='{'#1a9c45' if all_passed else '#c0392b'}'><b>{'✔ PASSED' if all_passed else '✘ FAILED'}</b></font>",
            ParagraphStyle("Status", parent=styles["Normal"], fontSize=11,
                           spaceBefore=12, spaceAfter=4, alignment=1)
        )
        name_table = Table([[name_para, status_para]], colWidths=[17*cm, 5*cm])
        name_table.setStyle(TableStyle([
            ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
            ("ALIGN", (1,0), (1,0), "RIGHT"),
            ("LINEBELOW", (0,0), (-1,0), 0.5, colors.HexColor("#c0c8e8")),
        ]))
        story.append(name_table)

        table_data = [HEADER] + [
            [s["course_code"], s["subject"], s["external"], s["internal"], s["gpa"], s["grade"], s["result"]]
            for s in student["subjects"]
        ]
        t = Table(table_data, colWidths=COL_WIDTHS)
        t.setStyle(header_style)
        story.append(t)
        story.append(Spacer(1, 0.3 * cm))

    doc.build(story)

    tmp_dir = tempfile.gettempdir()
    safe_label = semester_key.replace(" ", "_")
    pdf_filename = f"exam_results_{safe_label}.pdf"
    pdf_path = os.path.join(tmp_dir, pdf_filename)
    with open(pdf_path, "wb") as f:
        f.write(buffer.getvalue())

    return send_from_directory(
        tmp_dir,
        pdf_filename,
        as_attachment=True,
        mimetype="application/pdf",
    )


if __name__ == "__main__":
    app.run(debug=True, port=5000)
