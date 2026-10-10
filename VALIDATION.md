# 技术检查记录

2026-10-10，Windows x64。源码在 Python 3.14.6 和 3.11.9 下执行 `python test_text_line_deduplicator.py`；PyInstaller 6.21.0 构建后执行 `python test_text_line_deduplicator.py --exe dist/TextLineDeduplicator.exe`，均通过。

真实文件覆盖 UTF-8 无 BOM/有 BOM、GBK、GB18030、UTF-16 LE/BE 字节序，CRLF/LF/CR 混合换行及末行无换行。对所有输出逐字节核对；默认精确判重、首次顺序、Unicode casefold（Straße）、比较去首尾空白、空白行移除；空文件/BOM-only、错误编码/NUL、已有输出/源路径拒绝及源内容不变。源码还检查提前取消、写入 fsync 后取消的临时文件清理、大小限制、输入符号链接拒绝。

桌面 EXE 通过本地 Windows MCP 的原生打开对话框选择中文名单，保存到新文件：原 5 行、保留 3 行、重复 2 行；输出 BOM、原行内容和换行逐字节一致，源文件不变、无临时文件残留。

范围限制：未检查其他操作系统/Windows 版本、恶意并发修改或所有编码字符映射。输入上限 50 MiB，不声称大量唯一短行内存恒定。UTF-8 BOM 与 UTF-16 字节序保持已检查。

公开下载及下载 EXE 运行结果在发布端另记，网络检查完成前不声称通过。
