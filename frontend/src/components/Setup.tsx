import { useState } from "react";
import { FolderOpen, HardDrive, Loader2, ShieldAlert } from "lucide-react";
import { api, pickFolder, pickFolders } from "../api";
import type { AppStatus } from "../types";

interface Props {
  status: AppStatus;
  onRefresh: () => void;
}

export function Setup({ status, onRefresh }: Props) {
  const [libraryPath, setLibraryPath] = useState(status.library.path ?? "");
  const [embedding, setEmbedding] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const libraryReady = status.library.ready;

  async function chooseLibrary() {
    const path = await pickFolder();
    if (path) setLibraryPath(path);
  }

  async function initialize() {
    if (!libraryPath.trim()) return;
    setBusy(true);
    setError(null);
    try {
      await api.initializeLibrary(libraryPath.trim(), embedding);
      onRefresh();
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    } finally {
      setBusy(false);
    }
  }

  async function addFolders() {
    const folders = await pickFolders();
    if (!folders.length) return;
    setBusy(true);
    setError(null);
    try {
      for (const folder of folders) {
        try {
          await api.addSource(folder);
        } catch (exc) {
          setError(exc instanceof Error ? exc.message : String(exc));
        }
      }
      onRefresh();
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex h-full items-center justify-center p-8">
      <div className="panel w-full max-w-[640px] p-7">
        <div className="mb-1 flex items-center gap-2 text-[20px] font-semibold">
          <HardDrive size={20} />
          建立本地索引库
        </div>
        <p className="mb-5 text-[13px] leading-6 text-[var(--muted)]">
          所有正文、向量和搜索历史都保存在你选择的文件夹里，不会上传到任何服务器。
          加密文件只记录文件名和路径，不会提取正文；解密后会自动重新索引。
        </p>

        <div className="section-title mb-2">1. 索引库文件夹</div>
        <div className="mb-2 flex gap-2">
          <input
            className="input"
            placeholder="例如 ~/MaterialIndex"
            value={libraryPath}
            onChange={(event) => setLibraryPath(event.target.value)}
            disabled={libraryReady}
          />
          <button className="btn" onClick={chooseLibrary} disabled={libraryReady}>
            <FolderOpen size={15} />
            选择
          </button>
        </div>
        <p className="mb-4 text-[11.5px] leading-5 text-[var(--muted)]">
          不要放在 iCloud/Dropbox 等自动同步目录，也不要放在会被公司加密软件加密的目录。
          应用支持目录只保存一个指向这里的位置指针。
        </p>

        {!libraryReady && (
          <>
            <label className="mb-4 flex items-center gap-2 text-[12.5px]">
              <input
                type="checkbox"
                checked={embedding}
                onChange={(event) => setEmbedding(event.target.checked)}
              />
              启用本地中文语义检索（首次会下载约 90 MB 模型，可稍后在设置中重试）
            </label>
            <button className="btn primary mb-4" onClick={initialize} disabled={busy || !libraryPath.trim()}>
              {busy ? <Loader2 size={15} className="spin" /> : <HardDrive size={15} />}
              初始化索引库
            </button>
          </>
        )}

        {libraryReady && (
          <>
            <div className="section-title mb-2">2. 添加要索引的目录</div>
            <button className="btn primary mb-4" onClick={addFolders} disabled={busy}>
              {busy ? <Loader2 size={15} className="spin" /> : <FolderOpen size={15} />}
              选择文件夹
            </button>
            <p className="mb-2 text-[11.5px] leading-5 text-[var(--muted)]">
              当前索引库：<span className="mono">{status.library.path}</span>
            </p>
            {status.library.fallback && (
              <p className="mb-2 text-[11.5px] leading-5 text-[#ff9500]">
                程序目录不可写，已自动回退到应用支持目录；可在设置中迁移。
              </p>
            )}
          </>
        )}

        <div className="mt-2 flex items-start gap-2 rounded-xl border border-[var(--border)] p-3 text-[12px] text-[var(--muted)]">
          <ShieldAlert size={16} className="mt-0.5 shrink-0" />
          <div className="flex-1">
            如果添加 ~/Documents、~/Desktop 等目录时读不到文件，需要在系统设置中授予
            “完全磁盘访问权限”。
            <button
              className="btn ghost ml-2 !px-2 !py-0.5 text-[12px]"
              onClick={() => api.openPrivacySettings()}
            >
              打开设置
            </button>
          </div>
        </div>

        {error && (
          <div className="mt-3 rounded-xl bg-[rgba(255,59,48,0.12)] p-3 text-[12px] text-[var(--danger)]">
            {error}
          </div>
        )}
      </div>
    </div>
  );
}
