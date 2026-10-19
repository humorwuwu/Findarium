import { useState } from "react";
import {
  ExternalLink,
  FolderSearch,
  Lock,
  RefreshCw,
  ScanSearch,
  X,
} from "lucide-react";
import { api } from "../api";
import type { DocumentDetail, GraphData } from "../types";
import { extensionColor, extensionLabel } from "../format";
import { useI18n } from "../i18n";
import { PdfViewer } from "./PdfViewer";
import { RelationGraph } from "./RelationGraph";

interface Props {
  detail: DocumentDetail | null;
  graph: GraphData | null;
  loading: boolean;
  onClose: () => void;
  onSelectDocument: (documentId: number) => void;
  onRefresh: () => void;
}

type Tab = "content" | "related" | "graph";

export function DetailPanel({
  detail,
  graph,
  loading,
  onClose,
  onSelectDocument,
  onRefresh,
}: Props) {
  const { t, bytes, time } = useI18n();
  const [tab, setTab] = useState<Tab>("content");

  if (!detail) {
    return (
      <div className="flex h-full items-center justify-center p-6 text-[12.5px] text-[var(--muted)]">
        {loading ? t.detail.loading : t.detail.selectPrompt}
      </div>
    );
  }

  const doc = detail;
  const encrypted = doc.status === "encrypted" || doc.status === "encrypted_suspected";
  const pdfPage = (() => {
    const first = doc.chunks?.find((chunk) => chunk.location_json?.page);
    return first ? Number(first.location_json.page) : 1;
  })();

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-start gap-3 border-b border-[var(--border)] p-4">
        <div
          className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl text-[10px] font-bold text-white"
          style={{ background: extensionColor(doc.ext) }}
        >
          {extensionLabel(doc.ext)}
        </div>
        <div className="min-w-0 flex-1">
          <div className="truncate text-[14px] font-semibold">{doc.title || doc.name}</div>
          <div className="mono truncate text-[11px] text-[var(--muted)]">{doc.path}</div>
          <div className="mt-1 flex flex-wrap gap-1.5 text-[11px] text-[var(--muted)]">
            <span>{bytes(doc.size_bytes)}</span>
            <span>{t.detail.modified(time(doc.mtime_ns))}</span>
            {doc.page_count ? <span>{t.detail.pageCount(doc.page_count)}</span> : null}
            {doc.sheet_count ? <span>{t.detail.sheetCount(doc.sheet_count)}</span> : null}
            {doc.word_count ? <span>{t.detail.wordCount(doc.word_count)}</span> : null}
          </div>
        </div>
        <button className="btn ghost !p-1.5" onClick={onClose}>
          <X size={15} />
        </button>
      </div>

      <div className="flex flex-wrap gap-2 border-b border-[var(--border)] px-4 py-2">
        <button className="btn" onClick={() => api.openDocument(doc.id)}>
          <ExternalLink size={14} />
          {t.actions.open}
        </button>
        <button className="btn" onClick={() => api.revealDocument(doc.id)}>
          <FolderSearch size={14} />
          {t.actions.revealShort}
        </button>
        <button
          className="btn"
          onClick={async () => {
            await api.reindexDocument(doc.id);
            onRefresh();
          }}
        >
          <RefreshCw size={14} />
          {t.actions.reindex}
        </button>
        {encrypted && (
          <button
            className="btn"
            onClick={async () => {
              await api.probeDocument(doc.id);
              onRefresh();
            }}
          >
            <ScanSearch size={14} />
            {t.actions.reprobe}
          </button>
        )}
      </div>

      {encrypted && (
        <div className="m-4 flex items-start gap-2 rounded-xl bg-[rgba(255,149,0,0.12)] p-3 text-[12px]">
          <Lock size={15} className="mt-0.5 shrink-0 text-[#ff9500]" />
          <div>
            <div className="font-medium">{t.detail.encryptedTitle}</div>
            <div className="mt-1 text-[var(--muted)]">
              {t.detail.encryptedExplain(doc.error || t.detail.encryptedFallback)}
            </div>
          </div>
        </div>
      )}

      <div className="flex gap-1 px-4 pt-2">
        {(
          [
            ["content", t.detail.tabContent],
            ["related", t.detail.tabRelated(doc.related?.length ?? 0)],
            ["graph", t.detail.tabGraph],
          ] as [Tab, string][]
        ).map(([key, label]) => (
          <button
            key={key}
            className={`btn ghost ${tab === key ? "!bg-[var(--accent-soft)] !text-[var(--accent)]" : ""}`}
            onClick={() => setTab(key)}
          >
            {label}
          </button>
        ))}
      </div>

      <div className="flex-1 overflow-auto p-4">
        {tab === "content" && (
          <div className="space-y-4">
            {doc.ext === ".pdf" && !encrypted && doc.status !== "missing" && (
              <PdfViewer fileUrl={api.fileUrl(doc.id)} page={pdfPage} />
            )}

            {doc.warnings?.length > 0 && (
              <div className="rounded-xl bg-[rgba(255,149,0,0.1)] p-3 text-[12px] text-[#ff9500]">
                {doc.warnings.map((warning) => (
                  <div key={warning}>{warning}</div>
                ))}
              </div>
            )}

            {doc.keywords?.length > 0 && (
              <div>
                <div className="section-title mb-2">{t.detail.keywords}</div>
                <div className="flex flex-wrap gap-1.5">
                  {doc.keywords.map((keyword) => (
                    <span key={keyword.keyword} className="chip neutral">
                      {keyword.keyword}
                    </span>
                  ))}
                </div>
              </div>
            )}

            <div>
              <div className="section-title mb-2">{t.detail.extracted}</div>
              {doc.chunks?.length ? (
                <div className="space-y-2">
                  {doc.chunks.slice(0, 120).map((chunk) => (
                    <div
                      key={chunk.id}
                      className="rounded-xl border border-[var(--border)] p-3 text-[12.5px] leading-5"
                    >
                      {chunk.location_label && (
                        <div className="mb-1 text-[11px] text-[var(--accent)]">
                          {chunk.location_label}
                        </div>
                      )}
                      <div className="whitespace-pre-wrap">{chunk.text}</div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-[12px] text-[var(--muted)]">
                  {encrypted ? t.detail.encryptedNoBody : t.detail.noBody}
                </div>
              )}
            </div>

            {doc.metadata && Object.keys(doc.metadata).length > 0 && (
              <div>
                <div className="section-title mb-2">{t.detail.metadata}</div>
                <div className="space-y-1 text-[11.5px] text-[var(--muted)]">
                  {Object.entries(doc.metadata)
                    .filter(([, value]) => value)
                    .slice(0, 12)
                    .map(([key, value]) => (
                      <div key={key} className="truncate">
                        {t.detail.metadataEntry(key, String(value))}
                      </div>
                    ))}
                </div>
              </div>
            )}
          </div>
        )}

        {tab === "related" && (
          <div className="space-y-2">
            {doc.related?.length ? (
              doc.related.map((item) => (
                <div
                  key={item.id}
                  className="cursor-pointer rounded-xl border border-[var(--border)] p-3 hover:bg-[var(--accent-soft)]"
                  onClick={() => onSelectDocument(item.id)}
                >
                  <div className="flex items-center gap-2">
                    <span
                      className="flex h-6 w-6 items-center justify-center rounded-md text-[8px] font-bold text-white"
                      style={{ background: extensionColor(item.ext) }}
                    >
                      {extensionLabel(item.ext)}
                    </span>
                    <div className="min-w-0 flex-1 truncate text-[12.5px] font-medium">
                      {item.title || item.name}
                    </div>
                    <span className="text-[11px] text-[var(--muted)]">
                      {item.score.toFixed(2)}
                    </span>
                  </div>
                  <div className="mt-1.5 text-[11.5px] text-[var(--muted)]">
                    {item.reasons.join(t.detail.listSeparator)}
                  </div>
                </div>
              ))
            ) : (
              <div className="text-[12px] text-[var(--muted)]">{t.detail.noRelated}</div>
            )}
          </div>
        )}

        {tab === "graph" &&
          (graph ? (
            <RelationGraph data={graph} onSelect={onSelectDocument} />
          ) : (
            <div className="text-[12px] text-[var(--muted)]">{t.detail.loadingGraph}</div>
          ))}
      </div>
    </div>
  );
}
