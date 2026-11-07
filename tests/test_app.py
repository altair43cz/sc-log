import os
import shutil
import tempfile

from app import (
    get_data_rows,
    normalize_html_fragment,
    scan_row_names,
    should_ignore_name,
)


def setup_temp_tree():
    base = tempfile.mkdtemp(prefix='sc-log-test-')
    return base


def test_should_ignore_hidden_and_backup_names():
    assert should_ignore_name('.hidden') is True
    assert should_ignore_name('backup~') is True
    assert should_ignore_name('visible.txt') is False


def test_scan_row_names_are_sorted_numerically_and_filtered():
    base = setup_temp_tree()
    try:
        for row in ['10', '2', '.skip', '1', 'backup~']:
            os.makedirs(os.path.join(base, row), exist_ok=True)

        os.makedirs(os.path.join(base, '3'), exist_ok=True)

        rows = scan_row_names(base)
        assert rows == ['1', '2', '3', '10']
    finally:
        shutil.rmtree(base)


def test_get_data_rows_reads_only_visible_files_and_keeps_order():
    base = setup_temp_tree()
    try:
        os.makedirs(os.path.join(base, '2'), exist_ok=True)
        os.makedirs(os.path.join(base, '10'), exist_ok=True)

        for row, files in {
            '2': ['b.txt', '.hidden', 'a.txt', 'c~'],
            '10': ['z.txt'],
        }.items():
            for name in files:
                path = os.path.join(base, row, name)
                with open(path, 'w', encoding='utf-8') as handle:
                    handle.write(name)

        rows = get_data_rows(base)
        assert [row['name'] for row in rows] == ['2', '10']
        assert [cell['name'] for cell in rows[0]['cells']] == ['a.txt', 'b.txt']
        assert rows[1]['cells'][0]['name'] == 'z.txt'
    finally:
        shutil.rmtree(base)


def test_normalize_html_fragment_replaces_invalid_span_color():
    source = '<span color=green> c </span>'
    result = normalize_html_fragment(source)
    assert '<span style="color: green;"> c </span>' == result

    source = '<span style="font-weight:bold" color=green> c </span>'
    result = normalize_html_fragment(source)
    assert 'font-weight:bold; color: green' in result
    assert 'color: green' in result
