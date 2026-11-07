from flask import Flask, render_template, Response, request
import os
import re
import time
import json

app = Flask(__name__)


def normalize_html_fragment(content):
    """Convert invalid HTML fragments like <span color=green> into valid CSS spans."""
    if not content:
        return content

    def replace_span(match):
        attrs = (match.group('prefix') or '') + (match.group('suffix') or '')
        color = match.group('color1') or match.group('color2') or match.group('color3') or ''
        if not color:
            return match.group(0)

        attrs = attrs.rstrip()

        style_match = re.search(
            r'\bstyle\s*=\s*(?:"(?P<css1>[^"]*)"|\'(?P<css2>[^\']*)\'|(?P<css3>[^\s>]+))',
            attrs,
            flags=re.IGNORECASE,
        )

        if style_match:
            css_value = style_match.group('css1') or style_match.group('css2') or style_match.group('css3') or ''
            new_css = css_value.rstrip('; ') + '; color: ' + color + ';'
            attrs = attrs[:style_match.start()] + f' style="{new_css}"' + attrs[style_match.end():]
        else:
            attrs = attrs + f' style="color: {color};"'

        return attrs + '>'

    return re.sub(
        r'(?P<prefix><\s*span\b[^>]*?)\s+color\s*=\s*(?:"(?P<color1>[^"]*)"|\'(?P<color2>[^\']*)\'|(?P<color3>[^\s>]+))(?P<suffix>[^>]*)>',
        replace_span,
        content,
        flags=re.IGNORECASE,
    )


def get_stack_mode():
    mode = request.args.get('stacking', request.args.get('st', 'consolidated'))
    mode = (mode or 'consolidated').strip().lower()
    if mode in ('con', 'consolidated'):
        return 'consolidated'
    if mode in ('aln', 'aligned'):
        return 'aligned'
    return 'consolidated'


def should_ignore_name(name):
    return name.startswith('.') or name.endswith('~')


def scan_row_names(data_dir):
    rows = []
    if not os.path.exists(data_dir):
        return rows

    for entry in sorted(os.scandir(data_dir), key=lambda e: int(e.name) if re.match(r'^\d+$', e.name) else 999999):
        if entry.name.startswith('.') or entry.name.endswith('~'):
            continue
        if entry.is_dir(follow_symlinks=False) and re.match(r'^\d+$', entry.name):
            rows.append(entry.name)
    return rows


def scan_row_files(dir_path):
    files = []
    if not os.path.exists(dir_path):
        return files

    for entry in sorted(os.scandir(dir_path), key=lambda e: e.name):
        if entry.name.startswith('.') or entry.name.endswith('~'):
            continue
        if entry.is_file(follow_symlinks=False):
            files.append(entry.name)
    return files


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
                    content = normalize_html_fragment(content)
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
