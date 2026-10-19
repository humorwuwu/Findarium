import { useEffect, useState } from "react";
import { FolderOpen, RefreshCw, Trash2 } from "lucide-react";
import { api, pickFolders } from "../api";
import type { Source } from "../types";
import { useI18n } from "../i18n";

interface Props {
  onRefresh: () => void;
}

export function SourcesPage({ onRefresh }: Props) {
  const { t, time } = useI18n();
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
    if (!window.confirm(t.sources.removeConfirm)) return;
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
          <div className="text-[18px] font-semibold">{t.sources.title}</div>
          <div className="text-[12px] text-[var(--muted)]">{t.sources.subtitle}</div>
        </div>
        <button className="btn primary" onClick={add} disabled={busy}>
          <FolderOpen size={15} />
          {t.actions.addFolder}
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
                  <span className="chip neutral">{t.sources.documents(source.document_count)}</span>
                  {source.encrypted_count > 0 && (
                    <span className="chip warn">
                      {t.sources.encrypted(source.encrypted_count)}
                    </span>
                  )}
                  {source.failed_count > 0 && (
                    <span className="chip danger">{t.sources.failed(source.failed_count)}</span>
                  )}
                  <span className="chip neutral">
                    {t.sources.lastScan(
                      source.last_scan_at
                        ? time(source.last_scan_at * 1_000_000_000)
                        : t.sources.never,
                    )}
                  </span>
                </div>
                {source.last_error && (
                  <div className="mt-2 text-[11.5px] text-[var(--danger)]">{source.last_error}</div>
                )}
                <div className="mt-2 flex items-center gap-2">
                  <span className="shrink-0 text-[11px] text-[var(--muted)]">
                    {t.sources.excludeRules}
                  </span>
                  <input
                    className="input mono !py-1 !text-[11px]"
                    placeholder={t.sources.excludePlaceholder}
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
                  title={t.actions.scanNow}
                  onClick={async () => {
                    await api.scanSource(source.id);
                    onRefresh();
                  }}
                >
                  <RefreshCw size={14} />
                </button>
                <button
                  className="btn ghost danger !p-2"
                  title={t.actions.removeFolder}
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
            {t.sources.empty}
          </div>
        )}
      </div>
    </div>
  );
}
