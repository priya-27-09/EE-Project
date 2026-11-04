"""
AI Civic Guardian — Step 7 Real Multilingual System Test Suite
Covers supported languages (en, ta, hi), translation lookups, native scripts,
original text and language preservation, canonical identifiers integrity,
duplicate detection compatibility on Indic scripts, and regression verification.
"""

import sys
import time
from pathlib import Path
from typing import Dict, Any

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from fastapi_app import app as fastapi_app
from app.db.session import SessionLocal
from app.models.user import User, UserRole
from app.models.complaint import Complaint
from app.core.auth import hash_password, create_access_token
from app.i18n.constants import (
    LANG_EN,
    LANG_TA,
    LANG_HI,
    DEFAULT_LANGUAGE,
    SUPPORTED_LANGUAGES,
    LANGUAGE_METADATA,
    TRANSLATIONS,
    ISSUE_TRANSLATIONS,
    DEPARTMENT_TRANSLATIONS,
    STATUS_TRANSLATIONS,
    SEVERITY_TRANSLATIONS,
)
from app.i18n.translation_service import (
    TranslationService,
    BaseTranslationProvider,
    NullTranslationProvider,
)
from app.services.duplicate_service import (
    DuplicateService,
    compute_text_similarity,
    normalize_complaint_text,
)


class MultilingualTestRunner:
    def __init__(self):
        self.client = TestClient(fastapi_app)
        self.db: Session = SessionLocal()
        self.results = []
        self.citizen_user = None
        self.citizen_token = None
        self.created_complaint_ids = []

    def log(self, test_name: str, passed: bool, message: str = ""):
        status_str = "[PASS]" if passed else "[FAIL]"
        self.results.append({
            "test": test_name,
            "passed": passed,
            "message": message,
        })
        print(f"{status_str} {test_name}: {message}")

    def setup(self):
        ts = int(time.time() * 1000)
        self.citizen_user = User(
            name="Tamil Citizen Tester",
            email=f"tamil_citizen_{ts}@example.com",
            password_hash=hash_password("Password@123"),
            role=UserRole.CITIZEN,
            preferred_language=LANG_TA,
        )
        self.db.add(self.citizen_user)
        self.db.commit()
        self.db.refresh(self.citizen_user)

        self.citizen_token = create_access_token({
            "sub": str(self.citizen_user.id),
            "email": self.citizen_user.email,
            "role": self.citizen_user.role,
        })

    def teardown(self):
        try:
            for cid in self.created_complaint_ids:
                complaint = self.db.query(Complaint).filter(Complaint.complaint_id == cid).first()
                if complaint:
                    self.db.delete(complaint)
            if self.citizen_user:
                u = self.db.query(User).filter(User.id == self.citizen_user.id).first()
                if u:
                    self.db.delete(u)
            self.db.commit()
        except Exception as exc:
            self.db.rollback()
            print(f"Teardown warning: {exc}")
        finally:
            self.db.close()

    # -------------------------------------------------------------
    # 1. Supported Language Validation
    # -------------------------------------------------------------
    def test_01_supported_language_validation(self):
        en_valid = TranslationService.is_supported("en")
        ta_valid = TranslationService.is_supported("ta")
        hi_valid = TranslationService.is_supported("hi")
        passed = (en_valid is True and ta_valid is True and hi_valid is True)
        self.log(
            "Test 01 — Supported Language Validation (en, ta, hi)",
            passed,
            f"en={en_valid}, ta={ta_valid}, hi={hi_valid}",
        )

    # -------------------------------------------------------------
    # 2. Unsupported Language Validation & Fallback
    # -------------------------------------------------------------
    def test_02_unsupported_language_fallback(self):
        fr_valid = TranslationService.is_supported("fr")
        fr_fallback = TranslationService.validate_language("fr", strict=False)
        strict_raised = False
        try:
            TranslationService.validate_language("fr", strict=True)
        except ValueError:
            strict_raised = True

        passed = (fr_valid is False and fr_fallback == DEFAULT_LANGUAGE and strict_raised is True)
        self.log(
            "Test 02 — Unsupported Language Fallback (fr -> en)",
            passed,
            f"is_supported(fr)={fr_valid}, fallback={fr_fallback}, strict_raised={strict_raised}",
        )

    # -------------------------------------------------------------
    # 3. English Translation Lookup
    # -------------------------------------------------------------
    def test_03_english_translation_lookup(self):
        val = TranslationService.t("submit_complaint", LANG_EN)
        expected = "Submit Complaint"
        passed = (val == expected)
        self.log(
            "Test 03 — English Translation Lookup",
            passed,
            f"Key 'submit_complaint' -> '{val}' (Expected: '{expected}')",
        )

    # -------------------------------------------------------------
    # 4. Tamil Translation Lookup
    # -------------------------------------------------------------
    def test_04_tamil_translation_lookup(self):
        val = TranslationService.t("submit_complaint", LANG_TA)
        expected = "புகாரைச் சமர்ப்பிக்கவும்"
        passed = (val == expected)
        self.log(
            "Test 04 — Tamil Translation Lookup (Native Script)",
            passed,
            f"Key 'submit_complaint' -> '{val}' (Expected: '{expected}')",
        )

    # -------------------------------------------------------------
    # 5. Hindi Translation Lookup
    # -------------------------------------------------------------
    def test_05_hindi_translation_lookup(self):
        val = TranslationService.t("submit_complaint", LANG_HI)
        expected = "शिकायत दर्ज करें"
        passed = (val == expected)
        self.log(
            "Test 05 — Hindi Translation Lookup (Native Script)",
            passed,
            f"Key 'submit_complaint' -> '{val}' (Expected: '{expected}')",
        )

    # -------------------------------------------------------------
    # 6. Missing Translation Key Fallback Hierarchy
    # -------------------------------------------------------------
    def test_06_missing_translation_fallback(self):
        # Case A: Key missing in Tamil, present in English -> returns English translation
        # Case B: Key totally missing in all catalogs -> safely returns the key without crashing
        val_fallback_en = TranslationService.t("brand_tagline", LANG_TA)
        val_missing_key = TranslationService.t("non_existent_key_xyz123", LANG_TA)

        passed = (val_missing_key == "non_existent_key_xyz123" and len(val_fallback_en) > 0)
        self.log(
            "Test 06 — Missing Translation Key Fallback",
            passed,
            f"Totally missing key -> '{val_missing_key}' (Safe key returned without crash)",
        )

    # -------------------------------------------------------------
    # 7. Language Persistence
    # -------------------------------------------------------------
    def test_07_language_persistence(self):
        # Verify user record stored preferred_language in DB
        u = self.db.query(User).filter(User.id == self.citizen_user.id).first()
        passed = (u is not None and u.preferred_language == LANG_TA)
        self.log(
            "Test 07 — User Preferred Language Persistence",
            passed,
            f"User ID {self.citizen_user.id} stored preferred_language='{u.preferred_language}'",
        )

    # -------------------------------------------------------------
    # 8. Original Complaint Text Preservation
    # -------------------------------------------------------------
    def test_08_original_complaint_text_preservation(self):
        tamil_text = "சாலையில் பெரிய பள்ளம் உள்ளது, உடனடியாக சீரமைக்க வேண்டும்."
        payload = {
            "issue_type": "pothole",
            "description": tamil_text,
            "original_language": LANG_TA,
            "latitude": 13.0827,
            "longitude": 80.2707,
        }
        res = self.client.post(
            "/api/v1/complaints",
            json=payload,
            headers={"Authorization": f"Bearer {self.citizen_token}"},
        )
        assert res.status_code == 201, f"Failed creation: {res.text}"
        data = res.json()
        cid = data["complaint_id"]
        self.created_complaint_ids.append(cid)

        # Inspect database record directly
        db_complaint = self.db.query(Complaint).filter(Complaint.complaint_id == cid).first()
        passed = (
            db_complaint is not None
            and db_complaint.original_text == tamil_text
            and db_complaint.description == tamil_text
        )
        self.log(
            "Test 08 — Original Citizen Text Preservation",
            passed,
            f"DB original_text='{db_complaint.original_text}' matches citizen input exactly=True",
        )

    # -------------------------------------------------------------
    # 9. Original Language Preservation & Zero Fake Translation
    # -------------------------------------------------------------
    def test_09_original_language_and_no_fake_translation(self):
        cid = self.created_complaint_ids[-1]
        db_complaint = self.db.query(Complaint).filter(Complaint.complaint_id == cid).first()

        passed = (
            db_complaint is not None
            and db_complaint.original_language == LANG_TA
            and db_complaint.translated_text is None
        )
        self.log(
            "Test 09 — Original Language Preservation & Zero Fake Translation",
            passed,
            f"original_language='{db_complaint.original_language}', translated_text={db_complaint.translated_text} (NULL expected)",
        )

    # -------------------------------------------------------------
    # 10. Canonical Issue Identifier Remains Unchanged
    # -------------------------------------------------------------
    def test_10_canonical_issue_identifier_unchanged(self):
        cid = self.created_complaint_ids[-1]
        db_complaint = self.db.query(Complaint).filter(Complaint.complaint_id == cid).first()

        # Database must strictly store canonical 'pothole', not translated text
        stored_issue = db_complaint.issue_type
        # Display translation helper provides Tamil for UI
        display_issue = TranslationService.translate_issue(stored_issue, LANG_TA)

        passed = (stored_issue == "pothole" and display_issue == "சாலைக் குழி")
        self.log(
            "Test 10 — Canonical Issue Identifier Integrity",
            passed,
            f"DB stored='{stored_issue}', Display translated='{display_issue}'",
        )

    # -------------------------------------------------------------
    # 11. Canonical Status Remains Unchanged
    # -------------------------------------------------------------
    def test_11_canonical_status_unchanged(self):
        cid = self.created_complaint_ids[-1]
        db_complaint = self.db.query(Complaint).filter(Complaint.complaint_id == cid).first()

        stored_status = db_complaint.status
        display_status_ta = TranslationService.translate_status(stored_status, LANG_TA)
        display_status_hi = TranslationService.translate_status(stored_status, LANG_HI)

        passed = (
            stored_status == "SUBMITTED"
            and display_status_ta == "சமர்ப்பிக்கப்பட்டது"
            and display_status_hi == "जमा किया गया"
        )
        self.log(
            "Test 11 — Canonical Status Integrity",
            passed,
            f"DB stored='{stored_status}', Tamil='{display_status_ta}', Hindi='{display_status_hi}'",
        )

    # -------------------------------------------------------------
    # 12. Department Identifiers Remain Unchanged
    # -------------------------------------------------------------
    def test_12_department_identifiers_unchanged(self):
        cid = self.created_complaint_ids[-1]
        db_complaint = self.db.query(Complaint).filter(Complaint.complaint_id == cid).first()

        dept_canonical_name = db_complaint.department.name
        display_dept_ta = TranslationService.translate_department(dept_canonical_name, LANG_TA)
        display_dept_hi = TranslationService.translate_department(dept_canonical_name, LANG_HI)

        passed = (
            dept_canonical_name == "Roads & Highways"
            and display_dept_ta == "சாலைகள் மற்றும் நெடுஞ்சாலைகள்"
            and display_dept_hi == "सड़क और राजमार्ग"
        )
        self.log(
            "Test 12 — Department Identifiers Integrity",
            passed,
            f"DB stored='{dept_canonical_name}', Tamil='{display_dept_ta}', Hindi='{display_dept_hi}'",
        )

    # -------------------------------------------------------------
    # 13. Duplicate Detection Compatibility with Tamil Text
    # -------------------------------------------------------------
    def test_13_duplicate_detection_tamil(self):
        target = "சாலையில் பெரிய பள்ளம் உள்ளது அபாயகரமானது"
        candidates = [
            "சாலையில் பெரிய பள்ளம் உள்ளது",
            "குப்பைகள் தெருவில் குவிந்துள்ளன",
        ]
        scores = compute_text_similarity(target, candidates)

        # High similarity for similar Tamil text, zero for unrelated text
        passed = (len(scores) == 2 and scores[0] >= 0.40 and scores[1] == 0.0)
        self.log(
            "Test 13 — Duplicate Detection with Tamil Text",
            passed,
            f"Similar Tamil score={scores[0]}, Dissimilar Tamil score={scores[1]}",
        )

    # -------------------------------------------------------------
    # 14. Duplicate Detection Compatibility with Hindi Text
    # -------------------------------------------------------------
    def test_14_duplicate_detection_hindi(self):
        target = "मुख्य सड़क पर गहरा गड्ढा है जिससे दुर्घटना का खतरा है"
        candidates = [
            "सड़क पर गहरा गड्ढा है",
            "कचरा पेटी ओवरफ्लो हो गई है",
        ]
        scores = compute_text_similarity(target, candidates)
        # High similarity for similar Hindi text, very low similarity (<0.15) for unrelated text
        passed = (len(scores) == 2 and scores[0] >= 0.40 and scores[1] < 0.15)
        self.log(
            "Test 14 — Duplicate Detection with Hindi Text",
            passed,
            f"Similar Hindi score={scores[0]}, Dissimilar Hindi score={scores[1]}",
        )

    # -------------------------------------------------------------
    # 15. Multilingual API Endpoints & Auth Verification
    # -------------------------------------------------------------
    def test_15_multilingual_api_endpoints(self):
        # 1. Languages endpoint
        res_langs = self.client.get("/api/v1/i18n/languages")
        assert res_langs.status_code == 200, f"Failed languages endpoint: {res_langs.text}"
        langs_data = res_langs.json()
        codes = [item["code"] for item in langs_data.get("languages", [])]
        has_all_codes = {"en", "ta", "hi"}.issubset(set(codes))

        # 2. Translations catalog endpoint for Tamil
        res_trans_ta = self.client.get("/api/v1/i18n/translations/ta")
        assert res_trans_ta.status_code == 200, f"Failed translations endpoint: {res_trans_ta.text}"
        trans_data = res_trans_ta.json()
        ta_dict = trans_data.get("translations", {})
        has_ta_submit = ta_dict.get("submit_complaint") == "புகாரைச் சமர்ப்பிக்கவும்"

        # 3. Auth check: complaint creation without token is rejected
        res_unauth = self.client.post("/api/v1/complaints", json={"issue_type": "pothole"})
        auth_enforced = (res_unauth.status_code == 401)

        passed = (has_all_codes and has_ta_submit and auth_enforced)
        self.log(
            "Test 15 — Multilingual API Endpoints & Auth Enforced",
            passed,
            f"Languages returned={codes}, Tamil catalog valid={has_ta_submit}, Auth enforced={auth_enforced}",
        )

    # -------------------------------------------------------------
    # 16. Unicode Text Preprocessing & Combining Marks
    # -------------------------------------------------------------
    def test_16_unicode_text_preprocessing(self):
        raw_tamil = "சாலைக் குழி!!  (மெட்ரோ தூண் 42 அருகே)..."
        processed = TranslationService.prepare_processed_text(raw_tamil, LANG_TA)
        # Verify letters, combining marks, numbers, and single spaces are preserved, punctuation stripped
        passed = ("சாலைக் குழி" in processed and "!" not in processed and "(" not in processed)
        self.log(
            "Test 16 — Unicode Text Preprocessing (Combining Marks / Matras Preserved)",
            passed,
            f"Raw='{raw_tamil}' -> Processed='{processed}'",
        )

    def run_all(self):
        print("=" * 80)
        print("AI CIVIC GUARDIAN — STEP 7 REAL MULTILINGUAL SYSTEM TEST SUITE")
        print("=" * 80)

        self.setup()
        try:
            self.test_01_supported_language_validation()
            self.test_02_unsupported_language_fallback()
            self.test_03_english_translation_lookup()
            self.test_04_tamil_translation_lookup()
            self.test_05_hindi_translation_lookup()
            self.test_06_missing_translation_fallback()
            self.test_07_language_persistence()
            self.test_08_original_complaint_text_preservation()
            self.test_09_original_language_and_no_fake_translation()
            self.test_10_canonical_issue_identifier_unchanged()
            self.test_11_canonical_status_unchanged()
            self.test_12_department_identifiers_unchanged()
            self.test_13_duplicate_detection_tamil()
            self.test_14_duplicate_detection_hindi()
            self.test_15_multilingual_api_endpoints()
            self.test_16_unicode_text_preprocessing()
        finally:
            self.teardown()

        print("=" * 80)
        total = len(self.results)
        passed = sum(1 for r in self.results if r["passed"])
        failed = total - passed
        print(f"MULTILINGUAL TEST EXECUTION SUMMARY: {passed}/{total} Passed, {failed} Failed")
        print("=" * 80)
        if failed > 0:
            sys.exit(1)


if __name__ == "__main__":
    runner = MultilingualTestRunner()
    runner.run_all()
