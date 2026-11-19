import re

def clean_formatted_text(content: str) -> str:
    if not content:
        return ""

    lines = content.splitlines()
    clean_lines = []
    in_table = False

    for line in lines:
        stripped = line.strip()

        # Handle empty lines
        if not stripped:
            if not in_table:
                clean_lines.append("")
            continue

        # Skip markdown table divider lines like | :--- | or | :-- | or | --- |
        if stripped.startswith("|") and re.match(r"^\|?[\s:\-]+(\|[\s:\-]+)+\|?$", stripped):
            in_table = True
            continue

        # Format markdown table rows
        if stripped.startswith("|") and stripped.endswith("|"):
            raw_cells = [c.strip() for c in stripped.split("|")[1:-1]]
            cells = [re.sub(r"[`*]", "", c).strip() for c in raw_cells if c.strip()]
            if not in_table:
                # Table header row
                in_table = True
                header_text = " | ".join(cells)
                clean_lines.append(f"  {header_text}")
                clean_lines.append("  " + "─" * min(60, max(20, len(header_text))))
                continue
            else:
                if cells:
                    first = cells[0]
                    rest = cells[1:]
                    if rest:
                        clean_lines.append(f"  • {first} — {' | '.join(rest)}")
                    else:
                        clean_lines.append(f"  • {first}")
                continue
        else:
            in_table = False

        # Clean leading markdown headers like '### '
        line_clean = re.sub(r"^#{1,6}\s*", "", line)
        # Clean markdown bold/italic markers
        line_clean = re.sub(r"\*\*(.*?)\*\*", r"\1", line_clean)
        line_clean = re.sub(r"\*(.*?)\*", r"\1", line_clean)
        line_clean = re.sub(r"`(.*?)`", r"\1", line_clean)
        # Convert markdown bullets '* ' or '- ' to clean bullet point '• '
        line_clean = re.sub(r"^\s*[\*\-]\s+", "• ", line_clean)
        # Clean blockquotes
        line_clean = re.sub(r"^>\s*", "", line_clean)
        clean_lines.append(line_clean)

    # Collapse excessive blank lines
    result = re.sub(r"\n{3,}", "\n\n", "\n".join(clean_lines)).strip()
    return result

test_folder = """### 📁 **Folder Created Successfully**

* **Folder Name:** `vs`
* **Location:** `Vault-AI`
* **Full Path:** `E:\\Vault-AI\\vs`
* **Status:** ✅ Active and ready for use

The folder is created and available in your filesystem."""

test_table = """### 📄 **Discovered Files (2 items):**

| File Name | Category | Size | Path |
| :-- | :-- | :-- | :-- |
| `archive.zip` | **Archive** | 2.72 MB | `C:\\Users\\Downloads\\archive.zip` |
| `photo.jpg` | **Image** | 100 KB | `C:\\Users\\Downloads\\photo.jpg` |
"""

print("=== FOLDER MSG ===")
print(clean_formatted_text(test_folder))
print("\n=== TABLE MSG ===")
print(clean_formatted_text(test_table))

