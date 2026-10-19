import { ExternalLink, FolderSearch, Lock } from "lucide-react";
import type { SearchItem } from "../types";
import { extensionColor, extensionLabel, formatBytes, formatTime } from "../format";
import { Highlight } from "./Highlight";

interface Props {
  item: SearchItem;
  selected: boolean;
  onSelect: () => void;
  onOpen: () => void;
  onReveal: () => void;
}

export function ResultCard({ item, selected, onSelect, onOpen, onReveal }: Props) {
  const doc = item.document;
  const encrypted = doc.status === "encrypted" || doc.status === "encrypted_suspected";
  return (
    <div
      className={`result-card ${selected ? "selected" : ""}`}
      onClick={onSelect}
      onDoubleClick={onOpen}
    >
      <div className="flex items-start gap-3">
        <div
          className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-lg text-[10px] font-bold text-white"
          style={{ background: extensionColor(doc.ext) }}
        >
          {extensionLabel(doc.ext)}
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <div className="truncate text-[13.5px] font-semibold">
              {doc.title || doc.name}
            </div>
            {encrypted && (
              <span className="chip warn">
                <Lock size={11} />
                已加密
              </span>
            )}
          </div>
          <div className="mono mt-0.5 truncate text-[11px] text-[var(--muted)]">
            {doc.path}
          </div>

          {item.matches.length > 0 ? (
            <div className="mt-2 space-y-1">
              {item.matches.slice(0, 2).map((match, index) => (
                <div key={`${match.chunk_id}-${index}`} className="text-[12.5px] leading-5">
                  {match.location_label && (
                    <span className="mr-2 rounded bg-[var(--accent-soft)] px-1.5 py-0.5 text-[10.5px] text-[var(--accent)]">
                      {match.location_label}
                    </span>
                  )}
                  <span className="text-[var(--text)]">
                    <Highlight text={match.snippet} spans={match.spans} />
                  </span>
                </div>
              ))}
            </div>
          ) : (
            <div className="mt-2 text-[12px] text-[var(--muted)]">
              {encrypted
                ? "该文件已加密，正文未索引；文件名/路径仍可搜索。"
                : "没有可显示的正文片段。"}
            </div>
          )}

          <div className="mt-2 flex flex-wrap items-center gap-1.5">
            {item.tags.slice(0, 4).map((tag) => (
              <span key={tag} className="chip neutral">
                {tag}
              </span>
            ))}
            <span className="ml-auto text-[11px] text-[var(--muted)]">
              {formatBytes(doc.size_bytes)} · {formatTime(doc.mtime_ns)}
            </span>
          </div>
        </div>
        <div className="flex shrink-0 flex-col gap-1">
          <button
            className="btn ghost !p-1.5"
            title="打开文件"
            onClick={(event) => {
              event.stopPropagation();
              onOpen();
            }}
          >
            <ExternalLink size={14} />
          </button>
          <button
            className="btn ghost !p-1.5"
            title="在 Finder 中显示"
            onClick={(event) => {
              event.stopPropagation();
              onReveal();
            }}
          >
            <FolderSearch size={14} />
          </button>
        </div>
      </div>
    </div>
  );
}
