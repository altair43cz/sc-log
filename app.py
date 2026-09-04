from flask import Flask, render_template
import os
import re

app = Flask(__name__)

@app.route('/')
def index():
    # Get all files in current directory with numeric names
    files = []
    # Use the directory where this script is located
    app_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(app_dir, 'dat')
    
    if os.path.exists(data_dir):
        for filename in os.listdir(data_dir):
            filepath = os.path.join(data_dir, filename)
            if os.path.isfile(filepath) and re.match(r'^\d+$', filename):
                try:
                    with open(filepath, 'r') as f:
                        lines = f.readlines()
                        last_line = lines[-1].strip() if lines else ""
                        files.append({
                            'name': filename,
                            'last_line': last_line
                        })
                except:
                    pass
    
    # Sort by numeric value
    files.sort(key=lambda x: int(x['name']))
    
    return render_template('table.html', files=files)

if __name__ == '__main__':
    app.run(debug=True)
