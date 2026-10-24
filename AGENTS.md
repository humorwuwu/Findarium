# AGENTS.md — Findarium

> 工作区总规约在上一级 [`AGENTS.md`](../AGENTS.md)（本机 `ongoing/`；仓库单独克隆时没有它，以本文件为准）。新建同类目录前先读总规约。总规约与本文件冲突时，以本文件更具体的那条为准，但不得放松总规约的红线。


离线材料索引。Python（uv）+ React。远端 `github.com/humorwuwu/Findarium`。公开仓库，文档里不要写真实工程名。

## 目录（不要发明新名字）

| 路径 | 角色 | 阶段结束后 |
|---|---|---|
| `src/`、`frontend/src/`、`tests/`、`packaging/`、`scripts/` | 源码、测试、打包规格 | 保留 |
| `release/macos/` | **唯一的可运行发行产物** | 保留。含 `Findarium.app`、版本化 zip / onefile、以及旁边的 `FindariumData/` 索引库 |
| `dist/`、`dist-onefile/`、`build/`、`frontend/dist/`、`frontend/.vite/` | PyInstaller / Vite 中间产物 | 打包脚本会删；漏了就 `./scripts/clean.sh` |
| `.venv`、`frontend/node_modules` | 开发依赖 | 默认保留。只有 `./scripts/clean.sh --deep` 才删 |
| `FindariumData/`（仓库根） | 从源码运行时的索引库 | 不要删，也不要放进同步目录 |

平台目录只允许 `macos`、`windows`、`linux`、`ios`、`android`、`web`。本项目目前只有 `release/macos/`。不要把 `.app` 或 zip 放在仓库根，也不要再建一个 `dist/` 当发行目录。

文件名：`Findarium-<version>-macos-<arch>.zip`、`Findarium-<version>-macos-<arch>-onefile`。

## 阶段清理

测试通过并且 `release/macos/` 里已经有可运行产物之后，立刻运行：

```sh
./scripts/clean.sh            # 中间产物和缓存
./scripts/clean.sh --deep     # 换机器同步前，再删 .venv 和 node_modules
```

不要删除 `release/macos/FindariumData/`。那是用户的索引库，不是编译垃圾。

GitHub Actions 的 `release.yml` 在 runner 上用扁平的 `release/` 暂存即将上传的文件，并用 PyInstaller 默认的 `dist/`。那是 CI 暂存，不是本机休息态。改 workflow 时两处一起改。

## 命令

```sh
./scripts/setup.sh            # uv sync + npm ci + 前端构建
./scripts/dev.sh
uv run pytest
./scripts/build.sh            # -> release/macos/Findarium.app
./scripts/build-onefile.sh
```
