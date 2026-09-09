import requests
from bs4 import BeautifulSoup
import time

session = requests.Session()

url = "https://pareeksha.mgu.ac.in/Pareeksha/index.php/Public/PareekshaResultView_ctrl/index/3/428"

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Referer": url,
}

# --- Set your PRN range here ---
start_prn = "233142810015"
end_prn = "233142810017"

cs_id = "428"    # course id — same for all, since same programme
exam_id = "691"  # examination id — same for all, since same exam

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
    """Generate all PRNs between start and end (inclusive)"""
    prefix = start[:-4]
    start_num = int(start[-4:])
    end_num = int(end[-4:])
    
    prn_list = []
    for num in range(start_num, end_num + 1):
        prn_list.append(f"{prefix}{num:04d}")
    return prn_list

def print_student_result(prn, name, subject_rows):
    """Print formatted result for a single student"""
    print(f"\nName : {name}")
    print(f"PRN  : {prn}")
    print()
    print(f"{'Code':<10} {'Subject':<50} {'External':<9} {'Internal':<9} {'GPA':<7} {'Grade':<7} {'Result':<10}")
    print("-" * 110)
    
    for row in subject_rows:
        print(f"{row['course_code']:<10} {row['subject']:<50} {row['external']:<9} {row['internal']:<9} {row['gpa']:<7} {row['grade']:<7} {row['result']:<10}")
    
    print("-" * 110)
    
    

# Generate PRNs from the range
prn_list = generate_prn_range(start_prn, end_prn)
print(f"Fetching results for {len(prn_list)} students...")

for prn in prn_list:
    payload = {
        "cs_id": cs_id,
        "exam_id": exam_id,
        "prn": prn,
        "btnresult": "Get Result"
    }

    resp = session.post(url, data=payload, headers=headers)
    soup = BeautifulSoup(resp.text, "html.parser")

    name = get_label_value(soup, "Name of Student")
    reg_no = get_label_value(soup, "Permanent Register Number")

    if not name:
        print(f"[!] No result found for PRN {prn} — skipping")
        continue
    
    # Collect subject rows for this student
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
    
    # Print formatted result for this student
    print_student_result(reg_no, name, subject_rows)
    
    print(f"\n✓ Done: {name} ({reg_no})")
    print("=" * 110)
    time.sleep(2)  # be polite to the server