import { useEffect, useState } from "react";
import { ExternalLink, FolderSearch, Lock, ScanSearch } from "lucide-react";
import { api } from "../api";
import type { EncryptedDocument } from "../types";
import { useI18n } from "../i18n";

export function EncryptedPage() {
  const { t, bytes, time } = useI18n();
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
          <div className="text-[18px] font-semibold">{t.encrypted.title}</div>
          <div className="text-[12px] text-[var(--muted)]">{t.encrypted.subtitle}</div>
        </div>
        <button className="btn" onClick={recheckAll} disabled={busy}>
          <ScanSearch size={15} />
          {t.encrypted.recheckAll}
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
                {item.encryption_kind || item.status} · {bytes(item.size_bytes)} ·{" "}
                {time(item.mtime_ns)}
                {item.last_probe_at
                  ? t.encrypted.lastProbe(time(item.last_probe_at * 1_000_000_000))
                  : ""}
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
            {t.encrypted.empty}
          </div>
        )}
      </div>
    </div>
  );
}
