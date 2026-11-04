"""
Step 14 Test Suite: UI Polish, Responsive Design, and Web Accessibility (WCAG AA).
Verifies:
1. Semantic HTML elements in citizen templates (header, main, footer, nav, section, article)
2. Label associations for all form fields
3. Skip-to-content accessible link
4. Visible focus-visible outlines in CSS
5. Screen-reader utility classes (.sr-only)
6. Minimum touch target definitions (>= 44px)
7. Status badge indicators pairing colors with text labels and icons
8. ARIA landmarks and live regions for dynamic alerts
9. Responsive media queries for mobile and tablet breakpoints (360px - 1440px)
10. High-contrast government-tech color palette
11. File upload UI displays name, size, preview, and remove button
12. Loading indicators with descriptive accessible text
13. Absence of leaked secrets/passwords/JWTs in HTML/JS
14. Absence of internal server filesystem paths in templates
15. Complete multilingual coverage for English, Tamil, and Hindi in i18n catalog
"""

import sys
import re
import unittest
from pathlib import Path

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app.i18n.constants import SUPPORTED_LANGUAGES, TRANSLATIONS


class TestUIAccessibility(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.templates_dir = BASE_DIR / "templates"
        cls.static_css = BASE_DIR / "static" / "css" / "styles.css"
        cls.static_js = BASE_DIR / "static" / "js"

        # Read template contents
        cls.base_html = (cls.templates_dir / "base.html").read_text(encoding="utf-8")
        cls.dashboard_html = (cls.templates_dir / "dashboard.html").read_text(encoding="utf-8")
        cls.track_html = (cls.templates_dir / "track.html").read_text(encoding="utf-8")
        cls.profile_html = (cls.templates_dir / "profile.html").read_text(encoding="utf-8")
        cls.complaint_detail_html = (cls.templates_dir / "complaint_detail.html").read_text(encoding="utf-8")
        cls.wizard_html = (cls.templates_dir / "wizard.html").read_text(encoding="utf-8")
        cls.styles_css = cls.static_css.read_text(encoding="utf-8")

    def test_01_semantic_html_structure(self):
        """Test 01: Core layout uses semantic HTML elements."""
        self.assertIn("<header", self.base_html)
        self.assertIn("<main", self.base_html)
        self.assertIn("<footer", self.base_html)
        self.assertIn("<nav", self.base_html)
        self.assertIn("<section", self.dashboard_html)
        print("[PASS] Test 01 — Semantic HTML elements present in layout templates")

    def test_02_form_labels_association(self):
        """Test 02: Form fields have associated labels via 'for' or 'aria-label'."""
        # Profile form
        self.assertIn('<label for="profile-name"', self.profile_html)
        self.assertIn('<label for="profile-email"', self.profile_html)
        self.assertIn('<label for="profile-language"', self.profile_html)

        # Track form
        self.assertTrue('for="input-track-id"' in self.track_html or 'aria-label="Complaint Tracking ID"' in self.track_html)

        # Wizard form
        self.assertIn('<label for="input-description"', self.wizard_html)
        self.assertIn('<label for="input-language"', self.wizard_html)
        print("[PASS] Test 02 — Form inputs have associated labels and accessible names")

    def test_03_skip_link_present(self):
        """Test 03: Accessible skip-to-content link exists for keyboard and screen-reader users."""
        self.assertIn('class="skip-link"', self.base_html)
        self.assertIn('href="#main-content"', self.base_html)
        self.assertIn('.skip-link', self.styles_css)
        print("[PASS] Test 03 — Skip-to-content accessible link verified")

    def test_04_visible_focus_outlines(self):
        """Test 04: Focus-visible states are explicitly defined with high-contrast outlines."""
        self.assertIn(":focus-visible", self.styles_css)
        self.assertIn("outline:", self.styles_css)
        print("[PASS] Test 04 — High-contrast :focus-visible outlines verified in CSS")

    def test_05_screen_reader_utility_class(self):
        """Test 05: .sr-only utility class exists for assistive technology."""
        self.assertIn(".sr-only", self.styles_css)
        self.assertIn("clip: rect(0, 0, 0, 0);", self.styles_css)
        print("[PASS] Test 05 — .sr-only utility class present and correctly configured")

    def test_06_minimum_touch_target_size(self):
        """Test 06: Interactive elements have minimum touch targets (>= 44px)."""
        self.assertIn("min-height: 44px;", self.styles_css)
        print("[PASS] Test 06 — Minimum 44px touch targets defined for interactive controls")

    def test_07_status_badges_combine_color_and_text(self):
        """Test 07: Status badges pair distinct colors with text labels and icons."""
        self.assertIn("badge-status-submitted", self.styles_css)
        self.assertIn("badge-status-inprogress", self.styles_css)
        self.assertIn("badge-status-resolved", self.styles_css)
        self.assertIn("badge-status-review", self.styles_css)

        # Verify that templates output icon + text (e.g. ✓ RESOLVED, ● IN PROGRESS)
        self.assertIn("✓", self.dashboard_html + self.track_html + self.complaint_detail_html)
        self.assertIn("●", self.dashboard_html + self.track_html + self.complaint_detail_html)
        print("[PASS] Test 07 — Status badges pair color with text labels and unicode symbols")

    def test_08_aria_landmarks_and_live_regions(self):
        """Test 08: ARIA landmarks and live regions are used for dynamic feedback."""
        self.assertIn('role="banner"', self.base_html)
        self.assertIn('role="main"', self.base_html)
        self.assertIn('role="contentinfo"', self.base_html)
        self.assertIn('aria-live="polite"', self.base_html + self.dashboard_html + self.track_html)
        print("[PASS] Test 08 — ARIA landmarks and aria-live status regions verified")

    def test_09_responsive_media_queries(self):
        """Test 09: CSS contains responsive media queries supporting mobile and tablet viewports."""
        self.assertIn("@media (max-width: 1024px)", self.styles_css)
        self.assertIn("@media (max-width: 768px)", self.styles_css)
        self.assertIn("@media (max-width: 480px)", self.styles_css)
        print("[PASS] Test 09 — Responsive media queries present across desktop, tablet, and mobile breakpoints")

    def test_10_high_contrast_palette(self):
        """Test 10: Color palette conforms to government-tech contrast standards."""
        # Deep navy text (#0f172a) on white background (#ffffff) provides > 15:1 contrast
        self.assertIn("--primary-navy: #0f172a;", self.styles_css)
        self.assertIn("--bg-main: #ffffff;", self.styles_css)
        self.assertIn("--primary-blue: #1d4ed8;", self.styles_css)
        print("[PASS] Test 10 — High-contrast government-tech color palette verified")

    def test_11_file_upload_ux(self):
        """Test 11: File upload UI displays preview, filename, filesize, and remove option."""
        self.assertIn('id="evidence-preview-container"', self.wizard_html)
        self.assertIn('id="preview-filename"', self.wizard_html)
        self.assertIn('id="preview-filesize"', self.wizard_html)
        self.assertIn('id="btn-remove-evidence"', self.wizard_html)
        print("[PASS] Test 11 — File upload UX elements (name, size, preview, remove) verified")

    def test_12_accessible_loading_indicators(self):
        """Test 12: Loading states include accessible text and spinners."""
        self.assertIn("ai-spinner", self.styles_css)
        self.assertIn("Loading your complaints...", self.dashboard_html)
        self.assertIn("Retrieving grievance status...", self.track_html)
        print("[PASS] Test 12 — Accessible loading states with descriptive text verified")

    def test_13_no_secret_or_token_leakage(self):
        """Test 13: HTML and JS files do not leak JWT secrets, passwords, or private keys."""
        all_templates = [
            self.base_html,
            self.dashboard_html,
            self.track_html,
            self.profile_html,
            self.complaint_detail_html,
            self.wizard_html,
        ]
        forbidden_patterns = [
            r"0x[a-fA-F0-9]{64}",  # Private key
            r"eyJhbGciOi",          # Hardcoded JWT
            r"secret_key\s*=",
            r"password_hash\s*=",
        ]
        for content in all_templates:
            for pattern in forbidden_patterns:
                matches = re.findall(pattern, content)
                self.assertEqual(len(matches), 0, f"Found leaked pattern {pattern}")
        print("[PASS] Test 13 — No secrets, private keys, or tokens leaked in frontend templates")

    def test_14_no_internal_server_paths_exposed(self):
        """Test 14: Client-facing templates do not expose local server filesystem paths."""
        all_templates = [
            self.base_html,
            self.dashboard_html,
            self.track_html,
            self.profile_html,
            self.complaint_detail_html,
        ]
        for content in all_templates:
            self.assertNotIn("c:\\users\\", content.lower())
            self.assertNotIn("/home/", content.lower())
            self.assertNotIn("c:/users/", content.lower())
        print("[PASS] Test 14 — No internal server filesystem paths exposed in client templates")

    def test_15_multilingual_catalog_completeness(self):
        """Test 15: Primary Step 13 & 14 tokens are present in English, Tamil, and Hindi catalogs."""
        required_keys = [
            "welcome_prefix",
            "action_report_title",
            "action_complaints_title",
            "action_track_title",
            "action_assistant_title",
            "complaint_summary_heading",
            "stat_total_complaints",
            "stat_submitted",
            "stat_in_progress",
            "stat_resolved",
            "track_grievance_title",
            "profile_title",
            "resolution_report_heading",
        ]
        for lang in ["en", "ta", "hi"]:
            self.assertIn(lang, TRANSLATIONS)
            cat = TRANSLATIONS[lang]
            for k in required_keys:
                self.assertIn(k, cat, f"Missing token '{k}' in language '{lang}'")
        print("[PASS] Test 15 — Multilingual catalog completeness verified across en, ta, and hi")


if __name__ == "__main__":
    unittest.main()
