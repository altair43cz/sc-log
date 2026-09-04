from flask import Flask, render_template
import os
import re

app = Flask(__name__)

@app.route('/')
def index():
    # Get all files in current directory with numeric names
    files = []
    for filename in os.listdir('dat'):
        if os.path.isfile(filename) and re.match(r'^\d+$', filename):
            try:
                with open(filename, 'r') as f:
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
