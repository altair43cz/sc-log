from flask import Flask, render_template, Response, request
import os
import re
import time
import json

app = Flask(__name__)


def get_stack_mode():
    mode = request.args.get('stacking', request.args.get('st', 'consolidated'))
    mode = (mode or 'consolidated').strip().lower()
    if mode in ('con', 'consolidated'):
        return 'consolidated'
    if mode in ('aln', 'aligned'):
        return 'aligned'
    return 'consolidated'


def get_data_rows(data_dir):
    rows = []
    if not os.path.exists(data_dir):
        return rows

    row_names = []
    for name in os.listdir(data_dir):
        path = os.path.join(data_dir, name)
        if os.path.isdir(path) and re.match(r'^\d+$', name):
            row_names.append(name)

    for row_name in sorted(row_names, key=lambda value: int(value)):
        dir_path = os.path.join(data_dir, row_name)
        cells = []
        for filename in sorted(os.listdir(dir_path)):
            filepath = os.path.join(dir_path, filename)
            if os.path.isfile(filepath):
                try:
                    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
                        content = f.read().strip()
                except Exception:
                    content = ''
                cells.append({'name': filename, 'content': content})

        rows.append({
            'name': row_name,
            'cells': cells,
            'cells_by_name': {cell['name']: cell for cell in cells}
        })

    return rows


@app.route('/')
def index():
    data_dir = os.getenv('XDG_RUNTIME_DIR', '/run/user/1000') + '/sc-log'
    rows = get_data_rows(data_dir)
    file_names = []
    for row in rows:
        for cell in row['cells']:
            if cell['name'] not in file_names:
                file_names.append(cell['name'])

    return render_template('table.html', rows=rows, file_names=file_names, stacking=get_stack_mode())


@app.route('/stream')
def stream():
    """Server-Sent Events endpoint for streaming file updates"""
    def generate():
        data_dir = os.getenv('XDG_RUNTIME_DIR', '/run/user/1000') + '/sc-log'

        def snapshot():
            state = {}
            for row in get_data_rows(data_dir):
                for cell in row['cells']:
                    state[f"{row['name']}::{cell['name']}"] = cell['content']
            return state

        local_cache = snapshot()

        yield f"data: {json.dumps({'type': 'init'})}\n\n"

        while True:
            try:
                current = snapshot()

                for key, content in current.items():
                    if key not in local_cache or local_cache[key] != content:
                        local_cache[key] = content
                        row_name, cell_name = key.split('::', 1)
                        yield f"data: {json.dumps({'type': 'update', 'row': row_name, 'file': cell_name, 'content': content})}\n\n"

                for key in list(local_cache.keys()):
                    if key not in current:
                        local_cache.pop(key, None)
                        row_name, cell_name = key.split('::', 1)
                        yield f"data: {json.dumps({'type': 'delete', 'row': row_name, 'file': cell_name, 'content': ''})}\n\n"

                time.sleep(0.5)
            except Exception as e:
                print(f"Stream error: {e}")
                break

    response = Response(generate(), mimetype='text/event-stream')
    response.headers['Cache-Control'] = 'no-cache'
    response.headers['X-Accel-Buffering'] = 'no'
    return response


if __name__ == '__main__':
    app.run(debug=True)
