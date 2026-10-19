import { useState } from "react";
import { FolderOpen, HardDrive, Loader2, ShieldAlert } from "lucide-react";
import { api, pickFolder, pickFolders } from "../api";
import type { AppStatus } from "../types";
import { useI18n } from "../i18n";

interface Props {
  status: AppStatus;
  onRefresh: () => void;
}

export function Setup({ status, onRefresh }: Props) {
  const { t } = useI18n();
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
          {t.setup.title}
        </div>
        <p className="mb-5 text-[13px] leading-6 text-[var(--muted)]">{t.setup.intro}</p>

        <div className="section-title mb-2">{t.setup.step1}</div>
        <div className="mb-2 flex gap-2">
          <input
            className="input"
            placeholder={t.setup.pathPlaceholder}
            value={libraryPath}
            onChange={(event) => setLibraryPath(event.target.value)}
            disabled={libraryReady}
          />
          <button className="btn" onClick={chooseLibrary} disabled={libraryReady}>
            <FolderOpen size={15} />
            {t.actions.choose}
          </button>
        </div>
        <p className="mb-4 text-[11.5px] leading-5 text-[var(--muted)]">{t.setup.pathWarning}</p>

        {!libraryReady && (
          <>
            <label className="mb-4 flex items-center gap-2 text-[12.5px]">
              <input
                type="checkbox"
                checked={embedding}
                onChange={(event) => setEmbedding(event.target.checked)}
              />
              {t.setup.embedding}
            </label>
            <button
              className="btn primary mb-4"
              onClick={initialize}
              disabled={busy || !libraryPath.trim()}
            >
              {busy ? <Loader2 size={15} className="spin" /> : <HardDrive size={15} />}
              {t.setup.initialize}
            </button>
          </>
        )}

        {libraryReady && (
          <>
            <div className="section-title mb-2">{t.setup.step2}</div>
            <button className="btn primary mb-4" onClick={addFolders} disabled={busy}>
              {busy ? <Loader2 size={15} className="spin" /> : <FolderOpen size={15} />}
              {t.setup.chooseFolders}
            </button>
            <p className="mb-2 text-[11.5px] leading-5 text-[var(--muted)]">
              {t.setup.currentLibraryPrefix}
              <span className="mono">{status.library.path}</span>
            </p>
            {status.library.fallback && (
              <p className="mb-2 text-[11.5px] leading-5 text-[#ff9500]">{t.setup.fallback}</p>
            )}
          </>
        )}

        <div className="mt-2 flex items-start gap-2 rounded-xl border border-[var(--border)] p-3 text-[12px] text-[var(--muted)]">
          <ShieldAlert size={16} className="mt-0.5 shrink-0" />
          <div className="flex-1">
            {t.setup.permission}
            <button
              className="btn ghost ml-2 !px-2 !py-0.5 text-[12px]"
              onClick={() => api.openPrivacySettings()}
            >
              {t.actions.openSettings}
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
