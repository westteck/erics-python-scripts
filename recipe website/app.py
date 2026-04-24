from flask import Flask, render_template, request, url_for
import sqlite3
import os
import re

app = Flask(__name__)

def get_db_connection():
    conn = sqlite3.connect('recipes.db')
    conn.row_factory = sqlite3.Row 
    return conn

@app.route('/')
def index():
    query = request.args.get('query')
    category = request.args.get('category')
    page = int(request.args.get('page', 1))
    per_page = 40
    offset = (page - 1) * per_page
    
    conn = get_db_connection()
    filter_sql = ""
    params = []
    
    if query:
        filter_sql = " WHERE title LIKE ? OR directions LIKE ?"
        params = ['%' + query + '%', '%' + query + '%']
    elif category:
        filter_sql = " WHERE categories LIKE ?"
        params = ['%' + category + '%']

    total_count = conn.execute(f"SELECT COUNT(*) FROM recipes{filter_sql}", params).fetchone()[0]
    total_pages = (total_count + per_page - 1) // per_page if total_count > 0 else 1

    recipes = conn.execute(f"SELECT * FROM recipes{filter_sql} LIMIT ? OFFSET ?", params + [per_page, offset]).fetchall()
    
    # Category List Logic
    all_cats = conn.execute("SELECT DISTINCT categories FROM recipes").fetchall()
    cat_set = set()
    for row in all_cats:
        if row['categories']:
            for p in re.split(r'[;,]', row['categories']):
                if p.strip(): cat_set.add(p.strip())
    
    conn.close()
    return render_template('index.html', recipes=recipes, categories=sorted(list(cat_set)), 
                           page=page, total_pages=total_pages, query=query, category=category)

@app.route('/recipe/<int:recipe_id>')
def recipe(recipe_id):
    conn = get_db_connection()
    recipe_data = conn.execute("SELECT * FROM recipes WHERE id = ?", (recipe_id,)).fetchone()
    ingredients = conn.execute("SELECT * FROM ingredients WHERE recipe_id = ?", (recipe_id,)).fetchall()
    conn.close()
    return render_template('recipe.html', recipe=recipe_data, ingredients=ingredients)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
