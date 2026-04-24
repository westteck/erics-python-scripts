"""
MMF to SQLite/MySQL Converter (Verbose Version)
----------------------------------------------
Description: Parses a consolidated Meal-Master (.mmf) file and exports 
data into a local SQLite database (recipes.db) and a MySQL-ready 
SQL dump (mysql_import.sql). Includes debug logging to track progress.
Author: Gemini AI
Date: 2026
"""

import re
import sqlite3
import os

# --- Configuration ---
INPUT_FILE = 'recipes-fixed.mmf'
SQLITE_DB = 'recipes.db'
MYSQL_EXPORT = 'mysql_import.sql'

def clean_line(line):
    """Filters out internal MMF markers and sub-headers."""
    l = line.strip()
    if not l: return ""
    # Skip lines that are just MMMMM or dashes
    if re.match(r'^M{3,}-*|^-{3,}|M{5,}', l):
        return ""
    return l

def parse_mmf(file_path):
    if not os.path.exists(file_path):
        print(f"[-] ERROR: '{file_path}' not found. Please run the bulk cleaner first!")
        return []

    print(f"[*] Opening '{file_path}'...")
    with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
        content = f.read()

    # The cleaner script uses this exact string as the header:
    delimiter = r'MMMMM----- Recipe via Meal-Master'
    
    print(f"[*] Splitting file into blocks using delimiter...")
    blocks = re.split(delimiter, content, flags=re.IGNORECASE)
    
    # The first element of the split is usually empty text before the first recipe
    blocks = [b for b in blocks if len(b.strip()) > 50]
    print(f"[*] Found {len(blocks)} potential recipe blocks.")
    
    parsed_recipes = []

    for idx, block in enumerate(blocks):
        lines = block.split('\n')
        recipe = {'title': '', 'categories': '', 'yield': '', 'ingredients': [], 'directions': []}
        
        # Metadata Extraction
        title_m = re.search(r'Title:\s*(.*)', block, re.IGNORECASE)
        cat_m = re.search(r'Categories:\s*(.*)', block, re.IGNORECASE)
        yield_m = re.search(r'(?:Yield|Servings):\s*(.*)', block, re.IGNORECASE)

        recipe['title'] = title_m.group(1).strip() if title_m else f"Untitled Recipe {idx+1}"
        recipe['categories'] = cat_m.group(1).strip() if cat_m else ""
        recipe['yield'] = yield_m.group(1).strip() if yield_m else ""

        # Find where the ingredients start
        body_start_idx = 0
        for i, line in enumerate(lines):
            if any(k in line for k in ['Title:', 'Categories:', 'Yield:', 'Servings:']):
                body_start_idx = i + 1

        current_section = 'ingredients'
        for line in lines[body_start_idx:]:
            text = clean_line(line)
            if not text: continue
            
            # Identify ingredients: lines starting with digits, fractions, or 'x'
            is_ingr_line = re.match(r'^(\d+|x|1/2|1/3|1/4|2/3|3/4|1/8|3/8)\s+', text, re.IGNORECASE)
            
            if is_ingr_line and current_section == 'ingredients':
                recipe['ingredients'].append(text)
            else:
                current_section = 'directions'
                recipe['directions'].append(text)

        parsed_recipes.append({
            'title': recipe['title'],
            'categories': recipe['categories'],
            'yield': recipe['yield'],
            'ingredients': "\n".join(recipe['ingredients']).strip(),
            'directions': "\n".join(recipe['directions']).strip()
        })
        
        if (idx + 1) % 50 == 0:
            print(f"[*] Parsed {idx + 1} recipes...")

    return parsed_recipes

def save_to_databases(recipes):
    if not recipes:
        print("[-] No recipes were parsed. Converter stopping.")
        return

    print(f"[*] Writing to SQLite ({SQLITE_DB}) and MySQL export ({MYSQL_EXPORT})...")
    conn = sqlite3.connect(SQLITE_DB)
    cursor = conn.cursor()
    cursor.execute("DROP TABLE IF EXISTS recipes")
    cursor.execute("CREATE TABLE recipes (id INTEGER PRIMARY KEY, title TEXT, categories TEXT, yield_info TEXT, ingredients TEXT, directions TEXT)")
    
    with open(MYSQL_EXPORT, 'w', encoding='utf-8') as sql_file:
        sql_file.write("CREATE TABLE IF NOT EXISTS recipes (id INT AUTO_INCREMENT PRIMARY KEY, title VARCHAR(255), categories TEXT, yield_info TEXT, ingredients TEXT, directions TEXT) ENGINE=InnoDB;\n\n")

        for r in recipes:
            data = (r['title'], r['categories'], r['yield'], r['ingredients'], r['directions'])
            cursor.execute("INSERT INTO recipes (title, categories, yield_info, ingredients, directions) VALUES (?, ?, ?, ?, ?)", data)
            
            v = [str(i).replace("'", "''") for i in data]
            sql_file.write(f"INSERT INTO recipes (title, categories, yield_info, ingredients, directions) VALUES ('{v[0]}', '{v[1]}', '{v[2]}', '{v[3]}', '{v[4]}');\n")

    conn.commit()
    conn.close()
    print(f"[+] SUCCESS: {len(recipes)} recipes are now in your databases.")

if __name__ == "__main__":
    recipe_list = parse_mmf(INPUT_FILE)
    save_to_databases(recipe_list)
