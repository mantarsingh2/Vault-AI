"""Unit tests for VaultAIAgent prompt parsing and routing."""

import unittest
from pathlib import Path

from core.ai.agent import VaultAIAgent


class TestVaultAIAgent(unittest.TestCase):

    def setUp(self):
        self.agent = VaultAIAgent()

    def test_01_target_folder_resolution(self):
        folders_docs = self.agent._resolve_target_folders("Organize my documents and suggest a plan")
        self.assertTrue(len(folders_docs) > 0)
        self.assertTrue(any("Documents" in str(f) for f in folders_docs))

        folders_desktop = self.agent._resolve_target_folders("What files are on my desktop?")
        self.assertTrue(len(folders_desktop) > 0)
        self.assertTrue(any("Desktop" in str(f) for f in folders_desktop))

        folders_vault = self.agent._resolve_target_folders("Find python files in my project")
        self.assertTrue(len(folders_vault) > 0)


if __name__ == "__main__":
    unittest.main()
