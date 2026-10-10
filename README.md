# 文本行去重器

按首次出现顺序清理重复文本行，适合整理网址、词表、名单和日志。可忽略大小写或首尾空白进行比较，也可移除空白行；保留首次出现的原行内容、换行、编码及 BOM。

[下载 Windows EXE](https://github.com/9999999-svg/text-line-deduplicator/releases/download/v1.0.0/TextLineDeduplicator.exe) · [下载 Python 源码](https://github.com/9999999-svg/text-line-deduplicator/releases/download/v1.0.0/text-line-deduplicator-source-v1.0.0.zip) · [SHA-256](https://github.com/9999999-svg/text-line-deduplicator/releases/download/v1.0.0/SHA256SUMS.txt)

## 使用

双击 EXE，选择输入文本、编码及判重选项，点击「预览」查看数量和前 100 个保留行。选择新文件名，点击「保存新文件」。保存时按当前选项重新读取输入。已有文件和源文件不会被覆盖。

```powershell
python text_line_deduplicator.py
python text_line_deduplicator.py "名单.txt" --output "名单-去重.txt"
python text_line_deduplicator.py "词表.txt" --encoding gbk --strip --ignore-case --drop-blank --output "新词表.txt"
TextLineDeduplicator.exe "网址.txt"
```

不指定 `--output` 时只预览。命令行输出 JSON，退出码 0 完成、2 失败、130 中断。默认按整行内容精确比较，换行符不参与比较；忽略大小写使用 Unicode casefold，例如 Straße 和 STRASSE 会视为相同。空白行移除包括仅含空格或制表符的行。

## 必要限制

输入最多 50 MiB，只支持普通文本文件。支持 UTF-8、UTF-8 BOM、GBK、GB18030、带 BOM 的 UTF-16，按选择编码严格读取，不自动猜测。保留 CRLF、LF、CR 换行及 UTF-16 字节序；混合换行不会被统一。不同短行很多时可能占用数百 MiB 内存。

不解析 CSV 表格或 Office 文件：CSV 中的多行字段会被当成普通文本行，请使用适合表格的工具处理。输入/输出路径不能经过链接或目录联接。预览最多前 100 个保留行/20000 字符，保存包括全部保留行。正常失败或取消会清理临时文件，强制结束进程可能留下 `.line-dedup-*.tmp`。

EXE 为 Windows x64，约 12.5 MiB，未签名，内含 Python/Tcl/Tk，无需另装 Python。源码仅使用标准库，需带 Tkinter 的 Python 3.11 或更高版本。构建：在已有 Python 环境中安装 PyInstaller 6.21.0 后运行 `python build.py`。依赖版本、体积、卸载和第三方许可见 [DEPENDENCIES.md](DEPENDENCIES.md)、[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。卸载直接删除 EXE 和相关文件。

## 自愿赞助

功能和自有 MIT 源码全部免费，赞助完全自愿。

<img src="assets/donate-wechat.png" alt="自愿微信赞助二维码" width="280">
