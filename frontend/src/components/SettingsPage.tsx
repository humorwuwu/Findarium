import { useEffect, useState } from "react";
import { FolderOpen, Languages, RefreshCw, RotateCcw, ShieldCheck } from "lucide-react";
import { api, pickFolder } from "../api";
import type { AppStatus } from "../types";
import { useI18n } from "../i18n";
import type { LanguagePreference } from "../i18n/types";

interface Props {
  status: AppStatus;
  onRefresh: () => void;
}

export function SettingsPage({ status, onRefresh }: Props) {
  const { t, preference, setPreference } = useI18n();
  const [settings, setSettings] = useState<Record<string, unknown>>({});
  const [message, setMessage] = useState<string | null>(null);
  const [errors, setErrors] = useState<{ jobs: unknown[]; documents: unknown[] } | null>(null);

  async function load() {
    setSettings(await api.settings());
    try {
      setErrors(await api.errors());
    } catch {
      setErrors(null);
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function save(key: string, value: string) {
    const next = await api.updateSettings({ [key]: value });
    setSettings(next);
    setMessage(t.settings.saved);
    setTimeout(() => setMessage(null), 1500);
  }

  async function relocate() {
    const path = await pickFolder();
    if (!path) return;
    if (!window.confirm(t.settings.relocateConfirm(path))) return;
    await api.relocateLibrary(path);
    onRefresh();
  }

  const libraryPath = String(settings.library_path ?? status.library.path ?? "");
  const modelState =
    status.embedding_state === "ready"
      ? t.settings.modelReady
      : status.embedding_state === "loading"
        ? t.settings.modelLoading
        : status.embedding_state === "failed"
          ? t.settings.modelFailed(status.embedding_error ?? t.settings.modelUnknownError)
          : t.settings.modelDisabled;

  return (
    <div className="mx-auto w-full max-w-[900px] space-y-5 p-6">
      <div className="text-[18px] font-semibold">{t.settings.title}</div>

      <div className="solid-panel p-4">
        <div className="section-title mb-3">{t.settings.language}</div>
        <div className="flex flex-wrap items-center gap-2">
          <Languages size={14} className="text-[var(--muted)]" />
          <select
            className="rounded-lg border border-[var(--border)] bg-transparent px-2 py-1 text-[12px]"
            value={preference}
            onChange={(event) =>
              setPreference(event.target.value as LanguagePreference)
            }
          >
            <option value="auto">{t.settings.languageAuto}</option>
            <option value="zh-CN">{t.settings.languageZh}</option>
            <option value="en">{t.settings.languageEn}</option>
          </select>
        </div>
        <div className="mt-2 text-[11.5px] leading-5 text-[var(--muted)]">
          {t.settings.languageNote}
        </div>
      </div>

      <div className="solid-panel p-4">
        <div className="section-title mb-3">{t.settings.library}</div>
        <div className="mono mb-2 break-all text-[11.5px] text-[var(--muted)]">{libraryPath}</div>
        {status.library.fallback && (
          <div className="mb-2 rounded-lg bg-[rgba(255,149,0,0.12)] p-2 text-[11.5px] text-[#ff9500]">
            {t.settings.libraryFallback}
          </div>
        )}
        <div className="mb-3 text-[11.5px] text-[var(--muted)]">
          {t.settings.defaultLocationPrefix}
          <span className="mono">FindariumData</span>
          {status.library.program_dir ? t.settings.programDir(status.library.program_dir) : ""}
        </div>
        <div className="flex flex-wrap gap-2">
          <button className="btn" onClick={relocate}>
            <FolderOpen size={14} />
            {t.settings.relocate}
          </button>
          <button
            className="btn"
            onClick={async () => {
              const result = await api.rebuild();
              setMessage(t.settings.rebuildQueued(result.queued));
            }}
          >
            <RotateCcw size={14} />
            {t.settings.rebuild}
          </button>
          <button className="btn" onClick={() => api.openPrivacySettings()}>
            <ShieldCheck size={14} />
            {t.settings.privacy}
          </button>
        </div>
      </div>

      <div className="solid-panel p-4">
        <div className="section-title mb-3">{t.settings.scanSection}</div>
        <div className="grid grid-cols-2 gap-4">
          <label className="block">
            <div className="mb-1 text-[12px] text-[var(--muted)]">{t.settings.scanInterval}</div>
            <input
              className="input"
              defaultValue={String(settings.scan_interval_seconds ?? 600)}
              onBlur={(event) => save("scan_interval_seconds", event.target.value)}
            />
          </label>
          <label className="block">
            <div className="mb-1 text-[12px] text-[var(--muted)]">
              {t.settings.encryptedInterval}
            </div>
            <input
              className="input"
              defaultValue={String(settings.encrypted_recheck_seconds ?? 600)}
              onBlur={(event) => save("encrypted_recheck_seconds", event.target.value)}
            />
          </label>
        </div>
      </div>

      <div className="solid-panel p-4">
        <div className="section-title mb-3">{t.settings.performance}</div>
        <div className="mb-2 text-[12.5px] text-[var(--muted)]">
          {t.settings.performanceSummary({
            active: status.workers?.active ?? 0,
            desired: status.workers?.desired ?? 0,
            max: status.workers?.max ?? 1,
            load: (status.load_ratio ?? 0).toFixed(2),
            cpu: ((status.process_cpu ?? 0) * 100).toFixed(0),
            batch: String(status.embedding_batch ?? "—"),
          })}
        </div>
        <div className="text-[11.5px] leading-5 text-[var(--muted)]">
          {t.settings.performanceNote}
        </div>
      </div>

      <div className="solid-panel p-4">
        <div className="section-title mb-3">{t.settings.model}</div>
        <div className="mb-3 text-[12.5px] text-[var(--muted)]">
          {t.settings.modelLabel}
          {status.embedding_model ?? "BAAI/bge-small-zh-v1.5"} · {t.settings.statusLabel}
          {modelState}
          {status.embedding_ready != null ? t.settings.modelIndexed(status.embedding_ready) : ""}
        </div>
        <button
          className="btn"
          onClick={async () => {
            const result = await api.retryModel();
            setMessage(t.settings.modelRetryResult(result.state, result.queued));
          }}
        >
          <RefreshCw size={14} />
          {t.settings.modelRetry}
        </button>
      </div>

      {errors && (errors.jobs.length > 0 || errors.documents.length > 0) && (
        <div className="solid-panel p-4">
          <div className="section-title mb-3">{t.settings.problems}</div>
          <div className="space-y-1 text-[11.5px] text-[var(--muted)]">
            {errors.jobs.slice(0, 10).map((job, index) => (
              <div key={index} className="mono truncate">
                {JSON.stringify(job)}
              </div>
            ))}
            {errors.documents.slice(0, 10).map((doc, index) => (
              <div key={`d${index}`} className="mono truncate">
                {JSON.stringify(doc)}
              </div>
            ))}
          </div>
        </div>
      )}

      {message && <div className="text-[12px] text-[var(--success)]">{message}</div>}
    </div>
  );
}
