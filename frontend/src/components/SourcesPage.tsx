import { useEffect, useState } from "react";
import { FolderOpen, RefreshCw, Trash2 } from "lucide-react";
import { api, pickFolders } from "../api";
import type { Source } from "../types";
import { formatTime } from "../format";

interface Props {
  onRefresh: () => void;
}

export function SourcesPage({ onRefresh }: Props) {
  const [sources, setSources] = useState<Source[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    try {
      setSources(await api.sources());
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function add() {
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
      await load();
      onRefresh();
    } finally {
      setBusy(false);
    }
  }

  async function remove(id: number) {
    if (!window.confirm("移除该目录会删除它在本索引库中的所有内容，确定继续？")) return;
    setBusy(true);
    try {
      await api.removeSource(id);
      await load();
      onRefresh();
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto w-full max-w-[900px] p-6">
      <div className="mb-4 flex items-center justify-between">
        <div>
          <div className="text-[18px] font-semibold">索引目录</div>
          <div className="text-[12px] text-[var(--muted)]">
            已索引目录会实时监听变化，并每 10 分钟做一次校对扫描。
          </div>
        </div>
        <button className="btn primary" onClick={add} disabled={busy}>
          <FolderOpen size={15} />
          添加文件夹
        </button>
      </div>

      {error && (
        <div className="mb-3 rounded-xl bg-[rgba(255,59,48,0.12)] p-3 text-[12px] text-[var(--danger)]">
          {error}
        </div>
      )}

      <div className="space-y-3">
        {sources.map((source) => (
          <div key={source.id} className="solid-panel p-4">
            <div className="flex items-start gap-3">
              <div className="min-w-0 flex-1">
                <div className="truncate text-[13.5px] font-semibold">
                  {source.label || source.path}
                </div>
                <div className="mono mt-0.5 truncate text-[11px] text-[var(--muted)]">
                  {source.path}
                </div>
                <div className="mt-2 flex flex-wrap gap-1.5 text-[11px]">
                  <span className="chip neutral">{source.document_count} 个文档</span>
                  {source.encrypted_count > 0 && (
                    <span className="chip warn">{source.encrypted_count} 个加密</span>
                  )}
                  {source.failed_count > 0 && (
                    <span className="chip danger">{source.failed_count} 个失败</span>
                  )}
                  <span className="chip neutral">
                    最后扫描 {source.last_scan_at ? formatTime(source.last_scan_at * 1_000_000_000) : "尚未"}
                  </span>
                </div>
                {source.last_error && (
                  <div className="mt-2 text-[11.5px] text-[var(--danger)]">{source.last_error}</div>
                )}
                <div className="mt-2 flex items-center gap-2">
                  <span className="shrink-0 text-[11px] text-[var(--muted)]">排除规则</span>
                  <input
                    className="input mono !py-1 !text-[11px]"
                    placeholder="例如 *.tmp、临时/*"
                    defaultValue={source.exclude_globs}
                    onBlur={async (event) => {
                      await api.patchSource(source.id, {
                        exclude_globs: event.target.value,
                      });
                      await load();
                      onRefresh();
                    }}
                  />
                </div>
              </div>
              <div className="flex gap-1">
                <button
                  className="btn ghost !p-2"
                  title="立即扫描"
                  onClick={async () => {
                    await api.scanSource(source.id);
                    onRefresh();
                  }}
                >
                  <RefreshCw size={14} />
                </button>
                <button
                  className="btn ghost danger !p-2"
                  title="移除目录"
                  onClick={() => remove(source.id)}
                >
                  <Trash2 size={14} />
                </button>
              </div>
            </div>
          </div>
        ))}
        {sources.length === 0 && (
          <div className="panel p-6 text-center text-[12.5px] text-[var(--muted)]">
            还没有索引目录，点击右上角添加。
          </div>
        )}
      </div>
    </div>
  );
}
