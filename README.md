<img src="packaging/icon.png" alt="Findarium" width="120" align="right" />

# Findarium / 寻册

**中文** · [English](README.en.md)

本地优先的 macOS 桌面文档索引与检索工具：把若干文件夹里的 Word、Excel、PDF、Markdown 等文档
提取成全文与语义索引，然后用中文关键词、文件名或自然语言找回它们。所有数据都留在本机。

## 功能

- 添加文件夹后自动扫描并索引 PDF、DOCX、XLSX、PPTX、Markdown、TXT、CSV、HTML。
- **单一 SQLite 索引库**，放在你指定的文件夹里，包含提取正文、FTS5 全文索引、本地语义向量、
  任务队列、设置与搜索历史。应用支持目录里只放一个指向它的位置指针。
- 中文检索使用重叠二元组分词（两字词和子串都能命中），配合本地 `BAAI/bge-small-zh-v1.5`
  语义向量、文件名模糊匹配、时间新鲜度与本地点击反馈一起排序。
- 结果显示高亮片段、位置（PDF 页码 / Excel 工作表与行 / PPT 幻灯片 / Markdown 标题），
  相关文档及原因，以及可交互的关系图。
- 加密或受保护的文件（例如公司加密软件加密的文档）**只做标注**：文件名和路径仍可搜索，
  但不保存正文和向量。文件监听与定时复查会在文件可读后自动索引。应用不会尝试解密、破解
  或绕过加密。
- 启动即扫描，运行中由 FSEvents 实时监听，并有定时校对兜底。
- 界面、帮助与文档均提供中英文两套文案，可在设置页切换（默认跟随系统）。
- 原生窗口（pywebview），结果可直接打开文件或在 Finder 中定位。

## 开发

```bash
uv sync
cd frontend && npm install && npm run build
cd ..
uv run findarium
```

前端热更新开发：

```bash
./scripts/dev.sh
```

只跑后端（调试 API 时很方便）：

```bash
uv run findarium --headless --library /tmp/findarium-dev --no-embedding
```

命令行语言可用 `--lang auto|zh-CN|en` 指定，默认跟随系统。

运行检查：

```bash
uv run ruff check src tests
uv run pytest
cd frontend && npm run typecheck && npm run build
```

## 多台电脑之间同步

版本控制里只有源码、测试、锁文件和打包资源（约 2 MB，97 个文件）；虚拟环境、依赖和构建
产物都可以重新生成：

```bash
./scripts/clean.sh    # 删掉 dist/、build/、.venv/、node_modules/ 和各种缓存（1.4 GB → 3.6 MB）
./scripts/setup.sh    # 在新机器上恢复：uv sync + npm ci + 前端构建
```

注意：如果同步工具同步的是整个项目文件夹（而不只是 git），请确保它不包含 `FindariumData/`。
程序默认把索引库建在程序所在目录下，所以从同步目录里直接运行会把数据库也放进同步范围，
而同步工具可能损坏 SQLite 的 WAL 文件。开发时建议用 `--library` 指向一个本地目录，或在
设置页把索引库迁移出去。

## 打包

双击可用的 `.app`（onedir，启动更快，推荐）：

```bash
./scripts/build.sh
open dist/Findarium.app
```

单文件可执行版本（onefile，只有一个 Mach-O 文件，首次启动较慢，因为要先解压到临时目录）：

```bash
./scripts/build-onefile.sh
./dist-onefile/Findarium                      # 打开桌面窗口
./dist-onefile/Findarium --headless --port 8811 --library ~/MaterialIndex
```

PyInstaller 产出的是未签名（ad-hoc）构建，适合本机使用；分发给其他 Mac 需要 Developer ID
签名与公证。

## 发布

远端发布由 GitHub Actions 完成，本地不需要出包。推送 `v*` 标签时，
`.github/workflows/release.yml` 会在 macOS（Apple Silicon）上构建并把产物挂到 GitHub Release：

```bash
./scripts/set-version.sh 0.2.0    # 写进 pyproject / __version__ / 前端 / Info.plist
git commit -am "Release 0.2.0"
git tag v0.2.0
git push origin main v0.2.0
```

产物是 `Findarium-<版本>-macos-arm64.zip`（`.app`）、`...-onefile`（单文件可执行版本）
和 `SHA256SUMS.txt`。要重跑某个已有标签的构建（例如换了 runner 或依赖），用
Actions → Release → Run workflow 填版本号，标签必须已经推送过。

打包前会先跑 ruff 和 pytest，测试不过不会出包。当前产物是未签名（ad-hoc）构建，下载者首次
打开需要去掉隔离标记（release notes 里写了命令）；要做到双击即开，需要 Developer ID 签名
与公证：在仓库里配置好证书和 Apple ID 相关的 secrets 后，在 workflow 的
「Ad-hoc sign the app bundle」一步之前插入 `codesign` / `notarytool` 步骤。

日常检查（ruff、pytest、前端 typecheck 与构建）由 `.github/workflows/ci.yml` 在推送 main
和提 PR 时执行。

## 数据

默认情况下，索引库建在程序所在目录下：

- `dist/FindariumData/`（`dist/Findarium.app` 旁边）
- `dist-onefile/FindariumData/`（单文件可执行文件旁边）
- `./FindariumData/`（从源码运行时）

里面只有一个数据库 `index.sqlite3`，以及 `backups/`、`models/`、`logs/`。如果程序目录不可写
（例如放在系统管理的位置），应用会回退到 `~/Library/Application Support/Findarium/data`，
并在界面上说明。`~/Library/Application Support/Findarium/bootstrap.json` 里只记录一个指针，
用于记住你在设置页手动迁移后的位置。

不要把索引库放在 iCloud/Dropbox 之类的自动同步目录（WAL 文件可能被同步损坏），也不要放在
会被公司加密软件加密的目录。

## 自适应索引

索引使用一个会随机器状态伸缩的小型 worker 池：

- 系统空闲时提高提取并发（最多 4 个 worker）。
- 负载或本进程 CPU 占用升高时降回 1 个 worker，保证其他程序不受影响。
- 语义向量由独立 worker 在后台补全，负载高时自动缩小批大小，不会阻塞关键词索引。

当前 worker 数量、系统负载与向量批大小显示在底部状态栏和设置页。

## 已知限制

- 不做 OCR：扫描版 PDF 标记为“部分索引”，只能按文件名搜到。
- 不支持旧版 `.doc` / `.xls`。
- Word/Excel/PPT 的应用内预览显示提取出的文字与位置，不是完整排版；需要完整效果请用“打开”。
- 提取时写入索引的少量文字（例如表格的“列标题:”前缀）跟随当时的界面语言，切换语言后
  需要重建索引才会更新；其余文案（标签、原因、位置、错误）都按当前语言即时生成。
- PyMuPDF 采用 AGPL 许可。本项目定位为个人本地工具，如需分发请先评估其许可，或把 PDF
  提取器替换为 pypdf/pdfplumber。

## 许可

本项目采用 MIT 许可证，详见 [LICENSE](LICENSE)。注意 PDF 提取依赖 PyMuPDF（AGPL-3.0），
该依赖不适用 MIT 许可；如需分发，请先评估其许可，或把 PDF 提取器替换为 pypdf/pdfplumber。
