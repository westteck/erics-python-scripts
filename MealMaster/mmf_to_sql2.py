import re
import sqlite3
import os
import glob

# --- Configuration ---
DB_NAME = 'recipes.db'
CLEAN_FILE = 'recipes-fixed.mmf'

def smart_parse_ingredient(text):
    """Splits line into Qty/Unit, Item, Prep, and Options."""
    units_pattern = r'(c|t|ts|tb|tbsp|oz|lb|pkg|can|lg|sm|clove|x|cup|teaspoon|tablespoon|ounce|pound)'
    
    qty_match = re.match(r'^([\d\s\/\.]+)\s*({u})?\b'.format(u=units_pattern), text, re.I)
    
    qty, unit, remainder = "", "", text
    if qty_match:
        qty = qty_match.group(1).strip()
        unit = qty_match.group(2).strip() if qty_match.group(2) else ""
        remainder = text[qty_match.end():].strip()

    parts = [p.strip() for p in remainder.split(';')]
    
    item_name = parts[0].title() if len(parts) > 0 else ""
    preparation = parts[1] if len(parts) > 1 else ""
    options = parts[2] if len(parts) > 2 else ""
    
    if not preparation and ',' in item_name:
        sub_parts = item_name.split(',', 1)
        item_name = sub_parts[0].strip().title()
        preparation = sub_parts[1].strip()

    return {'qty': qty, 'unit': unit, 'item': item_name, 'prep': preparation, 'opt': options}

def run_import():
    print(f"[*] Step 1: Searching for .mmf files...")
    all_files = glob.glob("*.mmf")
    
    if not all_files:
        print("[-] ERROR: No .mmf files found!")
        return

    seen_titles = set()
    total_found = 0

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
                            total_found += 1
    
    print(f"[+] Merged {total_found} unique recipes.")

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("DROP TABLE IF EXISTS ingredients")
    cursor.execute("DROP TABLE IF EXISTS recipes")
    cursor.execute("CREATE TABLE recipes (id INTEGER PRIMARY KEY, title TEXT, categories TEXT, yield_info TEXT, directions TEXT)")
    cursor.execute("CREATE TABLE ingredients (id INTEGER PRIMARY KEY, recipe_id INTEGER, quantity TEXT, unit TEXT, item_name TEXT, preparation TEXT, options TEXT, FOREIGN KEY(recipe_id) REFERENCES recipes(id))")

    with open(CLEAN_FILE, 'r', encoding='utf-8') as f:
        content = f.read()

    blocks = re.split(r'MMMMM----- Recipe via Meal-Master', content, flags=re.I)
    recipes_added = 0

    for block in blocks:
        if len(block.strip()) < 50: continue
        
        title_m = re.search(r'Title:\s*(.*)', block, re.I)
        cat_m = re.search(r'Categories:\s*(.*)', block, re.I)
        yield_m = re.search(r'(?:Yield|Servings):\s*(.*)', block, re.I)

        title = title_m.group(1).strip() if title_m else "Untitled"
        cats = cat_m.group(1).strip() if cat_m else ""
        y_val = yield_m.group(1).strip() if yield_m else ""

        lines = block.split('\n')
        ingr_lines = []
        dir_lines = []
        in_directions = False

        for line in lines:
            clean = line.strip()
            # NEW: Explicitly skip version strings and MMF markers
            if not clean or any(x in clean for x in ['Title:', 'Categories:', 'Yield:', 'Servings:', 'MMMMM']):
                continue
            
            # Additional check to strip the (tm) version line if it sneaked in
            if "(tm) v8." in clean:
                continue

            is_ingr = re.match(r'^(\d+|x|1/2|1/3|1/4|2/3|3/4|1/8)', clean)
            
            if is_ingr and not in_directions:
                ingr_lines.append(clean)
            else:
                if len(ingr_lines) > 0: in_directions = True
                dir_lines.append(clean)

        cursor.execute("INSERT INTO recipes (title, categories, yield_info, directions) VALUES (?,?,?,?)",
                       (title, cats, y_val, "\n".join(dir_lines).strip()))
        recipe_id = cursor.lastrowid
        
        for line in ingr_lines:
            p = smart_parse_ingredient(line)
            cursor.execute("INSERT INTO ingredients (recipe_id, quantity, unit, item_name, preparation, options) VALUES (?,?,?,?,?,?)", 
                           (recipe_id, p['qty'], p['unit'], p['item'], p['prep'], p['opt']))
        
        recipes_added += 1

    conn.commit()
    conn.close()
    print(f"[+] SUCCESS: {recipes_added} recipes imported. Version strings removed.")

if __name__ == "__main__":
    run_import()
