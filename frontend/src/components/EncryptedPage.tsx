import { useEffect, useState } from "react";
import { ExternalLink, FolderSearch, Lock, ScanSearch } from "lucide-react";
import { api } from "../api";
import type { EncryptedDocument } from "../types";
import { formatBytes, formatTime } from "../format";

export function EncryptedPage() {
  const [items, setItems] = useState<EncryptedDocument[]>([]);
  const [busy, setBusy] = useState(false);

  async function load() {
    setItems(await api.encrypted());
  }

  useEffect(() => {
    load();
  }, []);

  async function recheckAll() {
    setBusy(true);
    try {
      await api.recheckEncrypted();
      await load();
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto w-full max-w-[900px] p-6">
      <div className="mb-4 flex items-center justify-between">
        <div>
          <div className="text-[18px] font-semibold">加密 / 受保护文件</div>
          <div className="text-[12px] text-[var(--muted)]">
            这些文件只记录了文件名和路径，没有提取正文。文件解密后会自动重新索引；应用不会尝试解密或绕过加密。
          </div>
        </div>
        <button className="btn" onClick={recheckAll} disabled={busy}>
          <ScanSearch size={15} />
          全部重新检测
        </button>
      </div>

      <div className="space-y-2">
        {items.map((item) => (
          <div key={item.id} className="solid-panel flex items-center gap-3 p-3">
            <Lock size={16} className="shrink-0 text-[#ff9500]" />
            <div className="min-w-0 flex-1">
              <div className="truncate text-[13px] font-medium">{item.name}</div>
              <div className="mono truncate text-[11px] text-[var(--muted)]">{item.path}</div>
              <div className="mt-1 text-[11.5px] text-[var(--muted)]">
                {item.encryption_kind || item.status} · {formatBytes(item.size_bytes)} ·{" "}
                {formatTime(item.mtime_ns)}
                {item.last_probe_at ? ` · 最后检测 ${formatTime(item.last_probe_at * 1_000_000_000)}` : ""}
              </div>
            </div>
            <button className="btn ghost !p-2" onClick={() => api.probeDocument(item.id).then(load)}>
              <ScanSearch size={14} />
            </button>
            <button className="btn ghost !p-2" onClick={() => api.openDocument(item.id)}>
              <ExternalLink size={14} />
            </button>
            <button className="btn ghost !p-2" onClick={() => api.revealDocument(item.id)}>
              <FolderSearch size={14} />
            </button>
          </div>
        ))}
        {items.length === 0 && (
          <div className="panel p-6 text-center text-[12.5px] text-[var(--muted)]">
            当前没有检测到加密文件。
          </div>
        )}
      </div>
    </div>
  );
}
