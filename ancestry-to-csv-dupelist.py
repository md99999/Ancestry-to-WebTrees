#  Author:  W. Mantz and CoPilot
#  July 2026
#
#  Python 3.12
#  Run:  python ancestry-to-csv-dupelist.py
#  It will prompt for input and output path names.
#  Note: Prompt handles spaces for windows users without the use of quotes if in current dir.


import csv
import os
import re
import sys

def parse_gedcom(gedcom_path, csv_path):
    individuals = []
    
    current_indi = None
    current_context = None  # Tracks if we are inside BIRT, DEAT, etc.

    with open(gedcom_path, 'r', encoding='utf-8-sig', errors='replace') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            # GEDCOM line format: LEVEL [TAG/ID] [VALUE]
            parts = line.split(' ', 2)
            level = int(parts[0])
            
            # Check for top-level records (Level 0)
            if level == 0:
                if current_indi and (current_indi['first'] or current_indi['last']):
                    individuals.append(current_indi)
                
                # Check if this Level 0 line marks a new Individual record
                if len(parts) > 2 and parts[2] == 'INDI':
                    current_indi = {
                        'first': '',
                        'last': '',
                        'dob': '',
                        'dod': ''
                    }
                else:
                    current_indi = None
                current_context = None
                continue

            if current_indi is None:
                continue

            tag = parts[1] if len(parts) > 1 else ''
            value = parts[2] if len(parts) > 2 else ''

            # Handle Level 1 Tags
            if level == 1:
                current_context = tag
                if tag == 'NAME':
                    # GEDCOM surnames are enclosed in slashes: First /Last/
                    match = re.search(r'^(.*?)\s*/([^/]*)/(.*)$', value)
                    if match:
                        current_indi['first'] = match.group(1).strip()
                        current_indi['last'] = match.group(2).strip()
                    else:
                        # Fallback if slashes aren't present
                        clean_name = value.replace('/', '').strip()
                        name_parts = clean_name.rsplit(' ', 1)
                        current_indi['first'] = name_parts[0] if len(name_parts) > 1 else clean_name
                        current_indi['last'] = name_parts[1] if len(name_parts) > 1 else ''

            # Handle Level 2 Tags (e.g., DATE under BIRT or DEAT)
            elif level == 2 and tag == 'DATE':
                if current_context == 'BIRT':
                    current_indi['dob'] = value
                elif current_context == 'DEAT':
                    current_indi['dod'] = value

        # Append the last individual if file ends
        if current_indi and (current_indi['first'] or current_indi['last']):
            individuals.append(current_indi)

    # Write results to CSV
    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['First Name', 'Last Name', 'Date of Birth', 'Date of Death'])
        for indi in individuals:
            writer.writerow([indi['first'], indi['last'], indi['dob'], indi['dod']])

    print(f"\nSuccess! Extracted {len(individuals)} records into '{csv_path}'.")

def get_file_paths():
    # Allow command-line args if provided, otherwise prompt interactively
    input_file = sys.argv[1] if len(sys.argv) > 1 else ""
    output_file = sys.argv[2] if len(sys.argv) > 2 else ""

    # Prompt for input file until a valid file is found
    while not input_file or not os.path.isfile(input_file):
        if input_file and not os.path.isfile(input_file):
            print(f"Error: File '{input_file}' not found. Please try again.")
        
        input_file = input("Enter the path to your .ged file: ").strip().strip('"\'')

    # Prompt for output file
    if not output_file:
        output_file = input("Enter the name/path for the output .csv file [default: ancestors.csv]: ").strip().strip('"\'')
        if not output_file:
            output_file = "ancestors.csv"

    # Automatically add .csv extension if user omitted it
    if not output_file.lower().endswith('.csv'):
        output_file += '.csv'

    return input_file, output_file

if __name__ == "__main__":
    input_path, output_path = get_file_paths()
    parse_gedcom(input_path, output_path)