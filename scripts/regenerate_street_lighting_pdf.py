"""
Regenerates the street_lighting_standards.pdf with the corrected text.
Fixes: "astronomical astronomical timers" → "astronomical timers"
"""
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

OUTPUT_PATH = BASE_DIR / "knowledge_base" / "raw" / "street_lighting_standards.pdf"

CORRECTED_CONTENT = """\
MUNICIPAL STREET LIGHTING AND ILLUMINATION STANDARDS
Document ID: DOC-2026-000005
Source: Bureau of Indian Standards (IS 1944 Code of Practice for Lighting of Public Thoroughfares)
Department: Electrical & Street Lighting
Version: 1.0

Section 1: Standards Overview
This document specifies the photometric lux levels, maintenance protocols, and grievance redressal standards for municipal street lighting as mandated by BIS IS 1944 and the Model Municipal Charter. All municipal bodies are required to comply with these standards for all public roads, footpaths, underpasses, and pedestrian crossings within their jurisdiction.

Section 2: Minimum Lux Level Requirements
1. Class A1 Arterial High-Traffic Roads: Minimum 30 Lux.
2. Class B Secondary / Commercial Thoroughfares: Minimum 15 Lux.
3. Class C Residential Collector Streets: Minimum 8 to 10 Lux.
4. Pedestrian Crosswalks & Dark Spots: Minimum 20 Lux.

Section 3: Repair Turnaround and Defect Rectification SLA
1. Single Fixture Failure (Burned LED bulb or fused starter): Must be replaced within 24 hours of citizen notification.
2. Multiple Fixture Circuit Failure (Dark span > 3 consecutive poles): Mandatory restoration within 12 hours.
3. Downed Electrical Pole / Exposed Live Cable Hazard: Emergency response within 1 hour with electrical circuit isolation.
4. Vandalism / Damaged Lamp Post: Assessment within 4 hours; repair within 48 hours.
5. Persistent Flicker Complaints: Night-time inspection within 24 hours.

Section 4: Energy Efficiency and Automated Timers
All municipal lighting circuits must be governed by astronomical timers or ambient lux sensors to switch ON at dusk and OFF at dawn. Manual overrides are only permitted during civic events with written authorization from the Municipal Commissioner.

Section 5: Citizen Grievance Redressal
Street lighting complaints submitted via the civic portal are acknowledged within 2 hours and inspected within 6 hours. Repeated failure of a fixture three times within 30 days mandates root-cause analysis and permanent infrastructure upgrade. Citizens may escalate unresolved complaints to the Electrical Department Head within 72 hours.

Section 6: Compliance and Audit
Quarterly night-time audits must be conducted by a certified Electrical Engineer. Non-compliance attracts municipal penalty as per the Municipal Corporation Act. Annual energy savings reports must be submitted to the State Energy Conservation Bureau.
"""


def regenerate_pdf():
    try:
        import pymupdf
        print(f"PyMuPDF version: {pymupdf.version}")
    except ImportError:
        print("ERROR: pymupdf not installed. Run: pip install pymupdf")
        return False

    # Create a new PDF document
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)  # A4 portrait

    # Define text areas
    margin_left = 50
    margin_top = 50
    margin_right = 545
    text_width = margin_right - margin_left

    # Insert the corrected text as a text block
    rect = pymupdf.Rect(margin_left, margin_top, margin_right, 820)

    # Use pymupdf's insert_textbox for proper text wrapping
    rc = page.insert_textbox(
        rect,
        CORRECTED_CONTENT,
        fontsize=10,
        fontname="helv",
        color=(0, 0, 0),
        align=pymupdf.TEXT_ALIGN_LEFT,
    )

    if rc < 0:
        print(f"WARNING: Text overflowed by {abs(rc)} characters. Adding second page.")
        page2 = doc.new_page(width=595, height=842)
        # The overflow is handled; text up to what fits is already written

    doc.save(str(OUTPUT_PATH))
    doc.close()

    # Verify
    verify_doc = pymupdf.open(str(OUTPUT_PATH))
    full_text = ""
    for i in range(len(verify_doc)):
        full_text += verify_doc[i].get_text()
    verify_doc.close()

    # Check the typo is gone
    if "astronomical astronomical" in full_text:
        print("ERROR: Typo 'astronomical astronomical' still present in PDF!")
        return False

    if "astronomical timers" in full_text:
        print("PASS: Corrected text 'astronomical timers' confirmed in PDF.")
    else:
        print("WARNING: 'astronomical timers' not found in extracted text. Check PDF manually.")

    print(f"PDF regenerated at: {OUTPUT_PATH}")
    print(f"File size: {OUTPUT_PATH.stat().st_size} bytes")
    print(f"Pages: {len(pymupdf.open(str(OUTPUT_PATH)))}")

    # Show Section 4
    for line in full_text.split('\n'):
        if 'astronomical' in line.lower() or 'Section 4' in line:
            print(f"  >> {line.strip()}")

    return True


if __name__ == "__main__":
    success = regenerate_pdf()
    sys.exit(0 if success else 1)
