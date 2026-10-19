import { Loader2 } from "lucide-react";
import type { AppStatus } from "../types";
import { useI18n } from "../i18n";

interface Props {
  status: AppStatus | null;
}

export function StatusBar({ status }: Props) {
  const { t } = useI18n();
  if (!status) {
    return (
      <div className="flex h-7 items-center gap-2 border-t border-[var(--border)] px-3 text-[11px] text-[var(--muted)]">
        {t.status.connecting}
      </div>
    );
  }
  const embeddingLabel =
    status.embedding_state === "ready"
      ? t.status.semantic(status.embedding_ready ?? 0)
      : status.embedding_state === "loading"
        ? t.status.semanticLoading
        : status.embedding_state === "failed"
          ? t.status.semanticUnavailable
          : t.status.semanticOff;
  const busy = (status.pending ?? 0) > 0 || (status.running ?? 0) > 0 || status.indexing > 0;
  return (
    <div className="flex h-7 items-center gap-3 border-t border-[var(--border)] px-3 text-[11px] text-[var(--muted)]">
      {busy && <Loader2 size={12} className="spin" />}
      <span>{t.status.sources(status.sources)}</span>
      <span>{t.status.documents(status.documents)}</span>
      {status.indexing > 0 && <span>{t.status.toIndex(status.indexing)}</span>}
      {(status.pending ?? 0) > 0 && <span>{t.status.queue(status.pending ?? 0)}</span>}
      <span>{embeddingLabel}</span>
      {status.workers && (
        <span>
          {t.status.workers(
            status.workers.active ?? 0,
            status.workers.desired ?? 0,
            status.workers.max ?? 1,
          )}
        </span>
      )}
      {status.load_ratio != null && <span>{t.status.load(status.load_ratio.toFixed(2))}</span>}
      {status.encrypted > 0 && <span>{t.status.encrypted(status.encrypted)}</span>}
      {status.failed > 0 && (
        <span className="text-[var(--danger)]">{t.status.failed(status.failed)}</span>
      )}
      <span className="ml-auto mono truncate max-w-[420px]">
        {status.library.path ?? t.status.noLibrary}
      </span>
    </div>
  );
}
