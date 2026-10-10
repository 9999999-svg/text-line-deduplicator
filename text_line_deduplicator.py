"""Remove duplicate text lines, preserving the first line and source encoding."""
import argparse
import io
import json
import os
from pathlib import Path
import queue
import stat
import sys
import tempfile
import threading

ENCODINGS = ['utf-8-sig', 'utf-8', 'gb18030', 'gbk', 'utf-16']
MAX_BYTES = 50 * 1024 * 1024

def cancel(event):
    if event is not None and event.is_set():
        raise InterruptedError('已取消，未发布输出文件。')

def linked(info):
    return stat.S_ISLNK(info.st_mode) or bool(getattr(info, 'st_file_attributes', 0) & 0x400)

def identity(info):
    value = info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns
    return value if os.name == 'nt' else value + (info.st_ctime_ns,)

def ordinary_directory(path):
    for parent in (path, *path.parents):
        info = parent.lstat()
        if linked(info) or not stat.S_ISDIR(info.st_mode):
            raise ValueError('路径含链接或非文件夹。')

def deduplicate(source, output=None, *, encoding='utf-8-sig', ignore_case=False, strip=False, drop_blank=False, event=None):
    if encoding not in ENCODINGS:
        raise ValueError('不支持的编码。')
    path = Path(source).absolute()
    ordinary_directory(path.parent)
    before = path.lstat()
    if linked(before) or not stat.S_ISREG(before.st_mode):
        raise ValueError('输入必须是普通文件，不能是链接。')
    if before.st_size > MAX_BYTES:
        raise ValueError('输入上限 50 MiB；大量不同短行可能占用数百 MiB 内存。')
    target = Path(output).absolute() if output is not None else None
    if target is not None:
        ordinary_directory(target.parent)
        if os.path.lexists(target) or target.resolve() == path.resolve():
            raise FileExistsError('输出必须是尚不存在的新文件，不能覆盖输入。')
    cancel(event)
    with path.open('rb') as stream:
        if identity(os.fstat(stream.fileno())) != identity(before):
            raise OSError('输入在打开时发生变化。')
        raw = stream.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES or identity(os.fstat(stream.fileno())) != identity(before):
            raise OSError('输入在读取时变化或增长超过限制。')
    if identity(path.lstat()) != identity(before):
        raise OSError('输入在读取后发生变化。')
    cancel(event)
    text = raw.decode(encoding, errors='strict')
    if '\x00' in text:
        raise ValueError('文本含 NUL；请检查输入编码。')
    # Keep the original BOM and byte order instead of adding a BOM to plain UTF-8.
    codec, prefix = encoding, b''
    if encoding == 'utf-8-sig':
        codec = 'utf-8'
        prefix = b'\xef\xbb\xbf' if raw.startswith(b'\xef\xbb\xbf') else b''
    elif encoding == 'utf-16':
        if raw.startswith(b'\xff\xfe'):
            codec, prefix = 'utf-16-le', b'\xff\xfe'
        elif raw.startswith(b'\xfe\xff'):
            codec, prefix = 'utf-16-be', b'\xfe\xff'
        elif raw:
            raise ValueError('UTF-16 输入需要 BOM。')
        else:
            codec = 'utf-16-le'
    seen, kept, count, duplicates, blanks = set(), [], 0, 0, 0
    for line in io.StringIO(text, newline=''):
        cancel(event)
        count += 1
        content = line[:-2] if line.endswith('\r\n') else line[:-1] if line.endswith(('\r', '\n')) else line
        key = content.strip() if strip else content
        if drop_blank and not content.strip():
            blanks += 1
        else:
            if ignore_case:
                key = key.casefold()
            if key in seen:
                duplicates += 1
            else:
                seen.add(key)
                kept.append(line)
    result = {'input_lines': count, 'kept_lines': len(kept), 'duplicate_lines': duplicates,
        'blank_lines_removed': blanks, 'encoding': encoding, 'preview': ''.join(kept[:100])[:20000]}
    if target is not None:
        payload = prefix + ''.join(kept).encode(codec, errors='strict')
        cancel(event)
        fd, name = tempfile.mkstemp(prefix='.line-dedup-', suffix='.tmp', dir=target.parent)
        temporary = Path(name)
        try:
            with os.fdopen(fd, 'wb') as destination:
                for start in range(0, len(payload), 1024 * 1024):
                    cancel(event)
                    destination.write(payload[start:start + 1024 * 1024])
                destination.flush()
                os.fsync(destination.fileno())
            cancel(event)
            if os.name == 'nt':
                os.rename(temporary, target)
            else:
                os.link(temporary, target)
                temporary.unlink()
            result['output'] = str(target)
            result['output_bytes'] = len(payload)
        finally:
            if temporary.exists():
                temporary.unlink()
    cancel(event) if target is None else None
    return result

def gui():
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk
    root = tk.Tk()
    root.title('文本行去重器')
    root.geometry('850x620')
    frame = ttk.Frame(root, padding=16)
    frame.pack(fill='both', expand=True)
    ttk.Label(frame, text='按首次出现顺序保留行；比较选项只改变判重规则，保留原行内容和换行。').pack(anchor='w')
    source, output = tk.StringVar(), tk.StringVar()
    controls = []
    def row(label, variable, browse):
        bar = ttk.Frame(frame)
        bar.pack(fill='x', pady=8)
        ttk.Label(bar, text=label, width=10).pack(side='left')
        entry = ttk.Entry(bar, textvariable=variable)
        entry.pack(side='left', fill='x', expand=True)
        button = ttk.Button(bar, text='选择', command=browse)
        button.pack(side='left', padx=8)
        controls.extend([entry, button])
    def choose_source():
        value = filedialog.askopenfilename(filetypes=[('文本文件', '*.txt *.log *.csv *.md'), ('所有文件', '*.*')])
        if value:
            source.set(value)
            path = Path(value)
            output.set(str(path.with_name(path.stem + '-去重' + path.suffix)))
    def choose_output():
        value = filedialog.asksaveasfilename(title='选择尚不存在的新文件', defaultextension='.txt')
        if value:
            output.set(value)
    row('输入文本', source, choose_source)
    row('新输出文件', output, choose_output)
    bar = ttk.Frame(frame)
    bar.pack(fill='x', pady=8)
    ttk.Label(bar, text='输入编码').pack(side='left')
    encoding = tk.StringVar(value='utf-8-sig')
    box = ttk.Combobox(bar, textvariable=encoding, values=ENCODINGS, state='readonly', width=14)
    box.pack(side='left', padx=8)
    controls.append(box)
    flags = [tk.BooleanVar(value=False) for _ in range(3)]
    for label, flag in zip(['忽略大小写', '比较时忽略首尾空白', '移除空白行'], flags):
        button = ttk.Checkbutton(bar, text=label, variable=flag)
        button.pack(side='left', padx=6)
        controls.append(button)
    preview = tk.Text(frame, height=16, wrap='none', state='disabled')
    preview.pack(fill='both', expand=True, pady=8)
    status = tk.StringVar(value='预览最多前 100 个保留行/20000 字符。保存时重新读取源文件。')
    ttk.Label(frame, textvariable=status, wraplength=800).pack(anchor='w', pady=8)
    messages, event = queue.Queue(), threading.Event()
    state = {'busy': False, 'closing': False}
    def start(save):
        if not source.get().strip() or save and not output.get().strip():
            messagebox.showerror('缺少路径', '请选择输入和新输出文件。')
            return
        args = source.get(), output.get() if save else None
        kwargs = dict(encoding=encoding.get(), ignore_case=flags[0].get(), strip=flags[1].get(), drop_blank=flags[2].get(), event=event)
        event.clear()
        state['busy'] = True
        for control in controls:
            control.configure(state='disabled')
        stop.configure(state='normal')
        status.set('正在处理…')
        def worker():
            try:
                messages.put(('ok', deduplicate(*args, **kwargs)))
            except Exception as error:
                messages.put(('error', str(error)))
        threading.Thread(target=worker, daemon=True).start()
    bar = ttk.Frame(frame)
    bar.pack(fill='x')
    for label, save in [('预览', False), ('保存新文件', True)]:
        button = ttk.Button(bar, text=label, command=lambda s=save: start(s))
        button.pack(side='left', padx=4)
        controls.append(button)
    stop = ttk.Button(bar, text='取消', state='disabled', command=event.set)
    stop.pack(side='left', padx=8)
    def close():
        if state['busy']:
            state['closing'] = True
            event.set()
            status.set('正在取消，等待临时文件清理…')
        else:
            root.destroy()
    def poll():
        try:
            kind, data = messages.get_nowait()
        except queue.Empty:
            root.after(100, poll)
            return
        state['busy'] = False
        if state['closing']:
            root.destroy()
            return
        for control in controls:
            control.configure(state='readonly' if control is box else 'normal')
        stop.configure(state='disabled')
        if kind == 'error':
            status.set(data)
        else:
            preview.configure(state='normal')
            preview.delete('1.0', 'end')
            preview.insert('1.0', data['preview'])
            preview.configure(state='disabled')
            status.set(f"原 {data['input_lines']} 行，保留 {data['kept_lines']} 行，重复 {data['duplicate_lines']} 行，移除空白 {data['blank_lines_removed']} 行。" + ('已保存：' + data['output'] if 'output' in data else '预览完成。'))
        root.after(100, poll)
    root.protocol('WM_DELETE_WINDOW', close)
    root.after(100, poll)
    root.mainloop()

def main():
    parser = argparse.ArgumentParser(description='按首次顺序去重文本行；不覆盖已有文件。')
    parser.add_argument('input')
    parser.add_argument('--output', help='不指定时只预览')
    parser.add_argument('--encoding', choices=ENCODINGS, default='utf-8-sig')
    parser.add_argument('--ignore-case', action='store_true')
    parser.add_argument('--strip', action='store_true', help='比较时忽略首尾空白，保留原行')
    parser.add_argument('--drop-blank', action='store_true')
    args = parser.parse_args()
    try:
        print(json.dumps(deduplicate(args.input, args.output, encoding=args.encoding,
            ignore_case=args.ignore_case, strip=args.strip, drop_blank=args.drop_blank), ensure_ascii=True))
        return 0
    except KeyboardInterrupt:
        return 130
    except Exception as error:
        print(json.dumps({'error': str(error)}, ensure_ascii=True), file=sys.stderr)
        return 2

if __name__ == '__main__':
    if len(sys.argv) == 1:
        gui()
    else:
        raise SystemExit(main())
