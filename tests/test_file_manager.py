"""Unit and integration tests for File Management in Vault AI."""

import tempfile
import unittest
from pathlib import Path

from core.file_manager.analyzer import FileAnalyzer
from core.file_manager.hasher import calculate_file_hash
from core.file_manager.models import ScanReport
from core.file_manager.plan_generator import PlanGenerator
from core.file_manager.scanner import FileScanner, get_file_category
from core.file_manager.security import SecurityManager


class TestFileManager(unittest.TestCase):

    def setUp(self):
        # Create a temporary directory structure for testing
        self.test_dir = tempfile.TemporaryDirectory()
        self.root_path = Path(self.test_dir.name)

        # 1. Create duplicate files
        self.dup1 = self.root_path / "invoice_march.pdf"
        self.dup2 = self.root_path / "invoice_march_copy.pdf"
        dup_content = b"PDF-CONTENT-INVOICE-12345-EXACT-MATCH"
        self.dup1.write_bytes(dup_content)
        self.dup2.write_bytes(dup_content)

        # 2. Create related files
        self.rel1 = self.root_path / "quarterly_budget.xlsx"
        self.rel2 = self.root_path / "quarterly_budget.pdf"
        self.rel3 = self.root_path / "quarterly_budget_v2.docx"
        self.rel1.write_text("budget data sheet")
        self.rel2.write_text("budget summary pdf")
        self.rel3.write_text("budget final version doc")

        # 3. Create a unique file
        self.unique = self.root_path / "notes.txt"
        self.unique.write_text("Unique personal notes")

    def tearDown(self):
        self.test_dir.cleanup()

    def test_01_category_detection(self):
        self.assertEqual(get_file_category(".pdf"), "Document")
        self.assertEqual(get_file_category(".xlsx"), "Spreadsheet")
        self.assertEqual(get_file_category(".png"), "Image")
        self.assertEqual(get_file_category(".py"), "Code")
        self.assertEqual(get_file_category(".xyz123"), "Other")

    def test_02_scanner_discovers_all_files(self):
        scanner = FileScanner()
        files = scanner.scan_path(str(self.root_path))
        self.assertEqual(len(files), 6)
        names = {f.name for f in files}
        self.assertIn("invoice_march.pdf", names)
        self.assertIn("notes.txt", names)

    def test_03_chunked_hasher_and_duplicates(self):
        hash1 = calculate_file_hash(str(self.dup1))
        hash2 = calculate_file_hash(str(self.dup2))
        hash_unique = calculate_file_hash(str(self.unique))

        self.assertIsNotNone(hash1)
        self.assertEqual(hash1, hash2, "Identical duplicate files must produce identical SHA-256 hashes.")
        self.assertNotEqual(hash1, hash_unique, "Different files must produce different hashes.")

        scanner = FileScanner()
        files = scanner.scan_path(str(self.root_path))
        duplicates = FileAnalyzer.find_duplicates(files)

        self.assertEqual(len(duplicates), 1)
        self.assertEqual(len(duplicates[0].files), 2)
        dup_names = {f.name for f in duplicates[0].files}
        self.assertEqual(dup_names, {"invoice_march.pdf", "invoice_march_copy.pdf"})

    def test_04_related_group_clustering(self):
        scanner = FileScanner()
        files = scanner.scan_path(str(self.root_path))
        related = FileAnalyzer.find_related_groups(files)

        # Should cluster quarterly_budget files
        group_names = [g.group_name.lower() for g in related]
        self.assertTrue(
            any("quarterly budget" in name for name in group_names),
            f"Expected 'Quarterly Budget' cluster in: {group_names}",
        )

    def test_05_security_sandboxing(self):
        sec = SecurityManager(custom_roots=[str(self.root_path)])
        self.assertTrue(sec.is_path_authorized(str(self.dup1)))

        # Test traversal protection
        outside_path = str(self.root_path / ".." / "something_else.txt")
        self.assertIsNone(sec.sanitize_and_validate(outside_path))

    def test_06_ai_plan_generation_integration(self):
        """Test full pipeline: scan -> analyze -> Qwen3:8b organization plan."""
        scanner = FileScanner()
        files = scanner.scan_path(str(self.root_path))
        duplicates = FileAnalyzer.find_duplicates(files)
        related = FileAnalyzer.find_related_groups(files)

        report = ScanReport(
            scanned_folders=[str(self.root_path)],
            files=files,
            duplicates=duplicates,
            related_groups=related,
            total_size_bytes=sum(f.size_bytes for f in files),
        )

        sec = SecurityManager(custom_roots=[str(self.root_path)])
        plan_gen = PlanGenerator(security_manager=sec)
        plan_result = plan_gen.generate_organization_plan(report)

        self.assertTrue(plan_result["success"], f"Plan generation failed: {plan_result.get('error')}")
        self.assertTrue(len(plan_result["summary"]) > 0)
        self.assertIsInstance(plan_result["suggestions"], list)


if __name__ == "__main__":
    unittest.main()
