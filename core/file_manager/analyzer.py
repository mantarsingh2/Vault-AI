"""Deterministic analyzer for duplicate detection and related file grouping in Vault AI."""

from collections import defaultdict
from pathlib import Path
import re
from typing import Dict, List

from .hasher import calculate_file_hash
from .models import DuplicateGroup, FileInfo, RelatedFileGroup


class FileAnalyzer:
    """Analyzes a collection of FileInfo items deterministically."""

    @staticmethod
    def find_duplicates(files: List[FileInfo]) -> List[DuplicateGroup]:
        """Detect duplicate files using 2-step size-clustering and SHA-256 content hashing.

        Args:
            files: List of FileInfo items.

        Returns:
            List[DuplicateGroup]: Clusters of duplicate files.
        """
        # Step 1: Group by file size
        size_buckets: Dict[int, List[FileInfo]] = defaultdict(list)
        for f in files:
            if f.size_bytes > 0:  # Skip empty 0-byte files for duplicate content hashing
                size_buckets[f.size_bytes].append(f)

        duplicate_groups: List[DuplicateGroup] = []

        # Step 2: Hash only files that share the same byte size
        for size_bytes, candidate_files in size_buckets.items():
            if len(candidate_files) < 2:
                continue

            hash_buckets: Dict[str, List[FileInfo]] = defaultdict(list)
            for f in candidate_files:
                if not f.file_hash:
                    f.file_hash = calculate_file_hash(f.path)

                if f.file_hash:
                    hash_buckets[f.file_hash].append(f)

            for file_hash, matching_files in hash_buckets.items():
                if len(matching_files) > 1:
                    duplicate_groups.append(
                        DuplicateGroup(
                            file_hash=file_hash,
                            size_bytes=size_bytes,
                            files=matching_files,
                        )
                    )

        # Sort duplicates by largest potential savings first
        duplicate_groups.sort(key=lambda d: d.potential_savings_bytes, reverse=True)
        return duplicate_groups

    @staticmethod
    def find_related_groups(files: List[FileInfo]) -> List[RelatedFileGroup]:
        """Detect related file clusters based on filename tokens, common prefixes, and project stems.

        Args:
            files: List of FileInfo items.

        Returns:
            List[RelatedFileGroup]: Identified deterministic clusters.
        """
        stem_map: Dict[str, List[FileInfo]] = defaultdict(list)

        for f in files:
            # Clean filename stem by removing trailing version numbers, dates, copies (e.g., "(1)", "_v2", "_final")
            raw_stem = Path(f.name).stem.lower()
            # Remove common versioning patterns
            cleaned_stem = re.sub(r"[\s_-]*(?:v\d+|\d{4}[-_]\d{2}[-_]\d{2}|\(\d+\)|_final|_draft|_copy)+$", "", raw_stem)
            cleaned_stem = re.sub(r"[\s_-]+", " ", cleaned_stem).strip()

            if len(cleaned_stem) >= 3:
                stem_map[cleaned_stem].append(f)

        related_groups: List[RelatedFileGroup] = []
        for stem_name, matched_files in stem_map.items():
            if len(matched_files) > 1:
                # Check if they have different extensions or slight name variants
                exts = {f.extension for f in matched_files}
                reason = f"Shares common base name '{stem_name}' across {len(exts)} file type(s)"
                related_groups.append(
                    RelatedFileGroup(
                        group_name=stem_name.title(),
                        reason=reason,
                        files=matched_files,
                    )
                )

        # Sort by group size (descending)
        related_groups.sort(key=lambda g: len(g.files), reverse=True)
        return related_groups
