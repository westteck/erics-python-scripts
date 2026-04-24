"""
MMF Bulk Sanitizer and De-duplicator
-----------------------------------
Description: Scans the current directory for all .mmf files, removes 
non-printable characters, standardizes headers, and merges them into one 
master file. Removes duplicates based on a Title + Category match.
Author: Gemini AI
Date: 2026
"""

import os
import re

# --- Configuration ---
OUTPUT_FILE = 'recipes-fixed.mmf'

def get_unique_key(title, categories):
    """Creates a unique identifier for each recipe to detect duplicates."""
    t = re.sub(r'\W+', '', title.lower())
    c = re.sub(r'\W+', '', categories.lower())
    return f"{t}_{c}"

def process_all_mmf():
    all_recipes = {} # Key: title+cat, Value: Full text block
    duplicate_count = 0
    total_found = 0

    mmf_files = [f for f in os.listdir('.') if f.lower().endswith('.mmf') and f != OUTPUT_FILE]
    
    if not mmf_files:
        print("[-] No .mmf files found in the current directory.")
        return

    print(f"[*] Found {len(mmf_files)} files. Cleaning and merging...")

    for filename in mmf_files:
        try:
            with open(filename, 'r', encoding='latin-1', errors='replace') as f:
                content = f.read()
        except Exception as e:
            print(f"[-] Could not read {filename}: {e}")
            continue

        delimiter = r'(?:MMMMM----- Recipe via Meal-Master|--+ Recipe Extracted from Meal-Master)'
        blocks = re.split(delimiter, content, flags=re.IGNORECASE)

        for block in blocks:
            if len(block.strip()) < 50:
                continue

            total_found += 1
            
            title_m = re.search(r'Title:\s*(.*)', block, re.IGNORECASE)
            cat_m = re.search(r'Categories:\s*(.*)', block, re.IGNORECASE)
            
            title = title_m.group(1).strip() if title_m else "Unknown Title"
            categories = cat_m.group(1).strip() if cat_m else "Uncategorized"
            
            unique_id = get_unique_key(title, categories)

            if unique_id not in all_recipes:
                # Sanitize: Remove non-printable control chars and fix markers
                sanitized_block = "".join(ch for ch in block if ch.isprintable() or ch in '\n\r\t')
                clean_block = "MMMMM----- Recipe via Meal-Master (tm) v8.02\n" + sanitized_block.strip() + "\nMMMMM\n\n"
                all_recipes[unique_id] = clean_block
            else:
                duplicate_count += 1

    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        for recipe_text in all_recipes.values():
            f.write(recipe_text)

    print("-" * 30)
    print(f"[+] Total recipes found: {total_found}")
    print(f"[+] Duplicates removed:  {duplicate_count}")
    print(f"[+] Unique recipes saved: {len(all_recipes)}")
    print(f"[+] Final file created:  {OUTPUT_FILE}")

if __name__ == "__main__":
    process_all_mmf()
