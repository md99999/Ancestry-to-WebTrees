#  Ancestry to WebTrees GED Convert Script
#  Author:  W. Mantz and CoPilot
#  July 2026
#
#  Python 3.12
#  Run:  python ancestry-to-webtrees.py
#  It will prompt for input and output path names.
#  Note: Prompt handles spaces for windows users without the use of quotes if in current dir.


import re
import os
import logging

# ---------------------------------------------------------
#  Logging Setup
# ---------------------------------------------------------
LOGFILE = "./ancestry-convert.log"

logging.basicConfig(
    filename=LOGFILE,
    filemode="a",
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

logging.info("=== Starting Ancestry → WebTrees Conversion ===")

# ---------------------------------------------------------
#  Utility: Remove emoji / non-BMP characters
# ---------------------------------------------------------
def remove_emoji(text):
    logging.debug("Removing emoji / non-BMP characters")
    return ''.join(c for c in text if ord(c) <= 0xFFFF)

# ---------------------------------------------------------
#  Cleanup functions
# ---------------------------------------------------------
CUSTOM_TAGS = ["_APID", "_ENV", "_TREE", "_UID", "_PHOTO", "_EVID", "_TODO"]
EMPTY_RECORD_TYPES = ["NOTE", "OBJE", "SOUR", "REPO"]

def remove_custom_tags(text):
    logging.debug("Removing custom Ancestry tags")
    for tag in CUSTOM_TAGS:
        text = re.sub(rf"^\d+ {tag} .+$", "", text, flags=re.MULTILINE)
    return text

def remove_resn(text):
    logging.debug("Removing RESN tags")
    return re.sub(r"^\d+ RESN .+$", "", text, flags=re.MULTILINE)

def normalize_notes(text):
    logging.debug("Normalizing NOTE/CONC/CONT formatting")
    text = re.sub(r"\n(\d+) CONC +", r"\n\1 CONC ", text)
    text = re.sub(r"\n(\d+) CONT +", r"\n\1 CONT ", text)
    return text

def normalize_dates(text):
    logging.debug("Normalizing DATE formatting")
    text = re.sub(r"\n(\d+) DATE +(.+)", r"\n\1 DATE \2", text)
    text = re.sub(r" {2,}", " ", text)
    return text

# ---------------------------------------------------------
#  SOUR: URL → TITL + HTML NOTE
# ---------------------------------------------------------
def rewrite_source_blocks(text):
    logging.debug("Processing SOUR (source) records")

    def repl(match):
        block = match.group(0)

        # Extract URL from DATA/WWW
        url_match = re.search(r"\n\d+ WWW (.+)", block)
        if not url_match:
            return block

        url = url_match.group(1).strip()

        # Replace or insert TITL with the URL
        if re.search(r"\n1 TITL ", block):
            block = re.sub(r"\n1 TITL .+", f"\n1 TITL {url}", block)
        else:
            block = block.replace("\n1 ", f"\n1 TITL {url}\n1 ", 1)

        # Add clickable HTML NOTE
        html_note = f'\n1 NOTE <a href="{url}">Original Source</a>'

        # Insert NOTE immediately after TITL
        block = block.replace(f"1 TITL {url}", f"1 TITL {url}{html_note}")

        return block

    return re.sub(
        r"0 @[^@]+@ SOUR(?:\n[1-9] .+?)*(?=\n0|\Z)",
        repl,
        text,
        flags=re.DOTALL
    )

# ---------------------------------------------------------
#  OBJE: Add clickable HTML NOTE (FILE untouched)
# ---------------------------------------------------------
def update_media_objects(text):
    logging.debug("Processing OBJE (media) blocks")

    def repl(match):
        block = match.group(0)

        # Extract URL from DATA/WWW inside this OBJE
        url_match = re.search(r"\n\d+ WWW (.+)", block)
        if not url_match:
            return block

        url = url_match.group(1).strip()
        logging.debug(f"Adding plain NOTE to OBJE: {url}")

        # Build NOTE line (plain text, no hyperlink)
        note_line = f"\n2 NOTE Original URL: {url}"

        # Insert NOTE after FORM or FILE
        if "\n2 FORM" in block:
            block = block.replace("\n2 FORM", f"\n2 FORM{note_line}", 1)
        else:
            block = block.replace("\n2 FILE", f"\n2 FILE{note_line}", 1)

        return block

    return re.sub(
        r"1 OBJE(?:\n[2-9] .+?)*(?=\n1 |\n0|\Z)",
        repl,
        text,
        flags=re.DOTALL
    )


# ---------------------------------------------------------
#  Remove empty NOTE/OBJE/SOUR/REPO blocks
# ---------------------------------------------------------
def remove_empty_records(text):
    for rtype in EMPTY_RECORD_TYPES:
        text = re.sub(
            rf"0 @[^@]+@ {rtype}\s*(?=\n0|\Z)",
            "",
            text,
            flags=re.MULTILINE
        )
    return text

# ---------------------------------------------------------
#  Remove unlinked records
# ---------------------------------------------------------
def remove_unlinked_records(text):
    records = re.findall(r"0 @([^@]+)@ (\w+)", text)
    xrefs = {xref: rtype for xref, rtype in records}
    linked = set(re.findall(r"@([^@]+)@", text))

    for xref, rtype in xrefs.items():
        if xref not in linked:
            text = re.sub(
                rf"0 @{re.escape(xref)}@ {rtype}.*?(?=\n0|\Z)",
                "",
                text,
                flags=re.DOTALL
            )
    return text

# ---------------------------------------------------------
#  Deduplicate SOUR records
# ---------------------------------------------------------
def dedupe_sources(text):
    matches = re.findall(
        r"0 @([^@]+)@ SOUR(\n[1-9] .+?)*(?=\n0|\Z)",
        text,
        flags=re.DOTALL
    )
    seen = {}
    for match in matches:
        xref = match[0]
        block = match[0] + (match[1] or "")
        title_match = re.search(r"1 TITL (.+)", block)
        if not title_match:
            continue
        title = title_match.group(1).strip()
        if title in seen:
            original = seen[title]
            text = re.sub(
                rf"0 @{re.escape(xref)}@ SOUR.*?(?=\n0|\Z)",
                "",
                text,
                flags=re.DOTALL
            )
            text = re.sub(
                rf"@{re.escape(xref)}@",
                f"@{original}@",
                text
            )
        else:
            seen[title] = xref
    return text

# ---------------------------------------------------------
#  Convert RESI blocks
# ---------------------------------------------------------
def convert_resi(text):
    def repl(match):
        block = match.group(0)
        if "2 PLAC" not in block:
            block = re.sub(r"2 NOTE (.+)", r"2 ADDR \1", block)
        return block
    return re.sub(
        r"1 RESI(?:\n[2-9] .+?)*(?=\n1 |\n0|\Z)",
        repl,
        text,
        flags=re.DOTALL
    )

# ---------------------------------------------------------
#  Main cleanup pipeline
# ---------------------------------------------------------
def clean_gedcom(text):
    text = remove_emoji(text)
    text = remove_custom_tags(text)
    text = remove_resn(text)
    text = normalize_notes(text)
    text = normalize_dates(text)
    text = rewrite_source_blocks(text)
    text = update_media_objects(text)   # <-- OBJE NOTE added, FILE untouched
    text = remove_empty_records(text)
    text = remove_unlinked_records(text)
    text = dedupe_sources(text)
    text = convert_resi(text)
    return text.strip() + "\n"

# ---------------------------------------------------------
#  User input
# ---------------------------------------------------------
def prompt_paths():
    print("=== Ancestry → Webtrees GEDCOM Converter ===")
    infile = input("Enter path to Ancestry GEDCOM file: ").strip()
    while not os.path.isfile(infile):
        print("File not found. Try again.")
        infile = input("Enter path to Ancestry GEDCOM file: ").strip()

    outfile = input("Enter output GEDCOM filename (e.g., cleaned.ged): ").strip()
    if not outfile.lower().endswith(".ged"):
        outfile += ".ged"

    return infile, outfile

# ---------------------------------------------------------
#  Main
# ---------------------------------------------------------
def main():
    infile, outfile = prompt_paths()

    with open(infile, "r", encoding="utf-8") as f:
        text = f.read()

    cleaned = clean_gedcom(text)

    with open(outfile, "w", encoding="utf-8") as f:
        f.write(cleaned)

    print(f"\nConversion complete!")
    print(f"Cleaned GEDCOM saved to: {outfile}")
    print(f"Log written to: {LOGFILE}")

if __name__ == "__main__":
    main()
