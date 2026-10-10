"""Actual text round-trip checks for source and --exe."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import threading

def checks(executable=None):
    command = [str(executable)] if executable else [sys.executable, str(Path(__file__).with_name('text_line_deduplicator.py'))]
    def run(*args, code=0):
        result = subprocess.run(command + list(map(str, args)), capture_output=True, timeout=60)
        assert result.returncode == code, (args, result.returncode, result.stdout, result.stderr)
        return json.loads(result.stdout if code == 0 else result.stderr)
    with tempfile.TemporaryDirectory(prefix='去重-中文-') as folder:
        root = Path(folder)
        text = '中文\r\n重复\n中文\n重复\r结尾'
        kept = '中文\r\n重复\n结尾'
        cases = [('utf8', 'utf-8-sig', text.encode('utf-8'), kept.encode('utf-8')),
            ('bom', 'utf-8-sig', b'\xef\xbb\xbf' + text.encode('utf-8'), b'\xef\xbb\xbf' + kept.encode('utf-8')),
            ('gbk', 'gbk', text.encode('gbk'), kept.encode('gbk')),
            ('gb18030', 'gb18030', text.encode('gb18030'), kept.encode('gb18030')),
            ('utf16le', 'utf-16', b'\xff\xfe' + text.encode('utf-16-le'), b'\xff\xfe' + kept.encode('utf-16-le')),
            ('utf16be', 'utf-16', b'\xfe\xff' + text.encode('utf-16-be'), b'\xfe\xff' + kept.encode('utf-16-be'))]
        for name, encoding, content, expected in cases:
            source, output = root / (name + '.txt'), root / (name + '-结果.txt')
            source.write_bytes(content)
            preview = run(source, '--encoding', encoding)
            assert preview['input_lines'] == 5 and preview['kept_lines'] == 3 and preview['duplicate_lines'] == 2
            assert not output.exists()
            report = run(source, '--output', output, '--encoding', encoding)
            assert report['output_bytes'] == len(expected)
            assert output.read_bytes() == expected and source.read_bytes() == content
            run(source, '--output', output, '--encoding', encoding, code=2)
            assert output.read_bytes() == expected
            run(source, '--output', source, '--encoding', encoding, code=2)
            assert source.read_bytes() == content
        source, output = root / '比较.txt', root / '比较结果.txt'
        source.write_text(' Straße \r\nSTRASSE\n \n\n尾\n尾', encoding='utf-8', newline='')
        result = run(source, '--output', output, '--strip', '--ignore-case', '--drop-blank')
        assert (result['input_lines'], result['kept_lines'], result['duplicate_lines'], result['blank_lines_removed']) == (6, 2, 2, 2)
        assert output.read_bytes() == ' Straße \r\n尾\n'.encode('utf-8')
        for name, content in [('empty', b''), ('onlybom', b'\xef\xbb\xbf')]:
            source, output = root / (name + '.txt'), root / (name + '-out.txt')
            source.write_bytes(content)
            assert run(source, '--output', output)['kept_lines'] == 0
            assert output.read_bytes() == content
        source = root / '坏编码.txt'
        for content in [b'\xffbad', b'a\x00b']:
            source.write_bytes(content)
            run(source, '--output', root / 'bad-out.txt', code=2)
            assert not (root / 'bad-out.txt').exists()
        assert not list(root.glob('.line-dedup-*.tmp'))
        if not executable:
            import text_line_deduplicator as tool
            source.write_bytes(b'a\na\nb')
            event = threading.Event()
            event.set()
            try:
                tool.deduplicate(source, root / 'cancelled.txt', event=event)
            except InterruptedError:
                pass
            else:
                raise AssertionError('Cancellation ignored')
            assert not (root / 'cancelled.txt').exists()
            event.clear()
            original_fsync = tool.os.fsync
            def cancel_after_flush(descriptor):
                original_fsync(descriptor)
                event.set()
            tool.os.fsync = cancel_after_flush
            try:
                try:
                    tool.deduplicate(source, root / 'cancelled-write.txt', event=event)
                except InterruptedError:
                    pass
                else:
                    raise AssertionError('Cancellation before publish ignored')
            finally:
                tool.os.fsync = original_fsync
            assert not (root / 'cancelled-write.txt').exists()
            assert not list(root.glob('.line-dedup-*.tmp'))
            linked_path = root / 'source-link.txt'
            try:
                linked_path.symlink_to(source)
            except OSError:
                print('SKIP: OS does not permit symlink fixture')
            else:
                run(linked_path, code=2)
            old = tool.MAX_BYTES
            tool.MAX_BYTES = 1
            try:
                try:
                    tool.deduplicate(source)
                except ValueError:
                    pass
                else:
                    raise AssertionError('Size limit ignored')
            finally:
                tool.MAX_BYTES = old
        print('PASS: actual mixed-newline UTF8/BOM/GBK/GB18030/UTF16 bytes, ordered Unicode/trim/blank comparison, errors/no overwrite/source changes', flush=True)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--exe', type=Path)
    checks(parser.parse_args().exe)
