import re
import sqlite3
import os
import glob

# --- Configuration ---
DB_NAME = 'recipes.db'
CLEAN_FILE = 'recipes-fixed.mmf'

def smart_parse_ingredient(text):
    """Splits line into Qty/Unit, Item, Prep, and Options based on semicolons."""
    units_pattern = r'(c|t|ts|tb|tbsp|oz|lb|pkg|can|lg|sm|clove|x|cup|teaspoon|tablespoon|ounce|pound)'
    
    qty_match = re.match(r'^([\d\s\/\.]+)\s*({u})?\b'.format(u=units_pattern), text, re.I)
    
    qty, unit, remainder = "", "", text
    if qty_match:
        qty = qty_match.group(1).strip()
        unit = qty_match.group(2).strip() if qty_match.group(2) else ""
        remainder = text[qty_match.end():].strip()

    # Split by semicolon: Item ; Prep ; Options
    parts = [p.strip() for p in remainder.split(';')]
    
    item_name = parts[0].title() if len(parts) > 0 else ""
    preparation = parts[1] if len(parts) > 1 else ""
    options = parts[2] if len(parts) > 2 else ""
    
    # Fallback for comma-separated prep
    if not preparation and ',' in item_name:
        sub_parts = item_name.split(',', 1)
        item_name = sub_parts[0].strip().title()
        preparation = sub_parts[1].strip()

    return {'qty': qty, 'unit': unit, 'item': item_name, 'prep': preparation, 'opt': options}

def run_import():
    print("[*] Step 1: Cleaning and Merging Files...")
    all_files = glob.glob("*.mmf")
    if not all_files:
        print("[-] No .mmf files found.")
        return

    seen_titles = set()
    with open(CLEAN_FILE, 'w', encoding='utf-8') as outfile:
        for filename in all_files:
            if filename == CLEAN_FILE: continue
            with open(filename, 'r', encoding='utf-8', errors='replace') as infile:
                content = infile.read()
                blocks = re.split(r'MMMMM----- Recipe via Meal-Master', content, flags=re.I)
                for block in blocks:
                    title_match = re.search(r'Title:\s*(.*)', block, re.I)
                    if title_match:
                        title = title_match.group(1).strip().upper()
                        if title not in seen_titles:
                            seen_titles.add(title)
                            outfile.write(f"\nMMMMM----- Recipe via Meal-Master (tm) v8.02\n{block.strip()}\n")

    # Part 2: Database Build
    print("[*] Step 2: Building Relational Database...")
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("DROP TABLE IF EXISTS ingredients")
    cursor.execute("DROP TABLE IF EXISTS recipes")
    cursor.execute("CREATE TABLE recipes (id INTEGER PRIMARY KEY, title TEXT, categories TEXT, yield_info TEXT, directions TEXT)")
    cursor.execute("CREATE TABLE ingredients (id INTEGER PRIMARY KEY, recipe_id INTEGER, quantity TEXT, unit TEXT, item_name TEXT, preparation TEXT, options TEXT, FOREIGN KEY(recipe_id) REFERENCES recipes(id))")

    with open(CLEAN_FILE, 'r', encoding='utf-8') as f:
        content = f.read()

    blocks = re.split(r'MMMMM----- Recipe via Meal-Master', content, flags=re.I)
    count = 0
    for block in blocks:
        if len(block.strip()) < 50: continue
        
        title_m = re.search(r'Title:\s*(.*)', block, re.I)
        cat_m = re.search(r'Categories:\s*(.*)', block, re.I)
        yield_m = re.search(r'(?:Yield|Servings):\s*(.*)', block, re.I)

        lines = block.split('\n')
        ingr_lines, dir_lines = [], []
        in_directions = False

        for line in lines:
            clean = line.strip()
            # STRIP VERSION STRINGS AND HEADERS
            if not clean or any(x in clean for x in ['Title:', 'Categories:', 'Yield:', 'Servings:', 'MMMMM']) or "(tm) v8." in clean:
                continue
            
            is_ingr = re.match(r'^(\d+|x|1/2|1/3|1/4|2/3|3/4|1/8)', clean)
            if is_ingr and not in_directions:
                ingr_lines.append(clean)
            else:
                if ingr_lines: in_directions = True
                dir_lines.append(clean)

        cursor.execute("INSERT INTO recipes (title, categories, yield_info, directions) VALUES (?,?,?,?)",
                       (title_m.group(1).strip() if title_m else "Untitled", 
                        cat_m.group(1).strip() if cat_m else "", 
                        yield_m.group(1).strip() if yield_m else "", 
                        "\n".join(dir_lines).strip()))
        rid = cursor.lastrowid
        
        for iline in ingr_lines:
            p = smart_parse_ingredient(iline)
            cursor.execute("INSERT INTO ingredients (recipe_id, quantity, unit, item_name, preparation, options) VALUES (?,?,?,?,?,?)", 
                           (rid, p['qty'], p['unit'], p['item'], p['prep'], p['opt']))
        count += 1

    conn.commit()
    conn.close()
    print(f"[+] Success: {count} recipes imported. Version strings removed.")

if __name__ == "__main__":
    run_import()
