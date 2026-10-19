import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Loader2, Search as SearchIcon } from "lucide-react";
import { api } from "./api";
import type { AppStatus, DocumentDetail, GraphData, SearchResponse } from "./types";
import { Sidebar, type View } from "./components/Sidebar";
import { StatusBar } from "./components/StatusBar";
import { Setup } from "./components/Setup";
import { ResultCard } from "./components/ResultCard";
import { DetailPanel } from "./components/DetailPanel";
import {
  DEFAULT_FILTERS,
  FilterBar,
  filtersToParams,
  type Filters,
} from "./components/FilterBar";
import { SourcesPage } from "./components/SourcesPage";
import { EncryptedPage } from "./components/EncryptedPage";
import { SettingsPage } from "./components/SettingsPage";

export default function App() {
  const [status, setStatus] = useState<AppStatus | null>(null);
  const [view, setView] = useState<View>("search");
  const [query, setQuery] = useState("");
  const [filters, setFilters] = useState<Filters>(DEFAULT_FILTERS);
  const [results, setResults] = useState<SearchResponse | null>(null);
  const [searching, setSearching] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [detail, setDetail] = useState<DocumentDetail | null>(null);
  const [graph, setGraph] = useState<GraphData | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const searchInputRef = useRef<HTMLInputElement | null>(null);

  const refreshStatus = useCallback(async () => {
    try {
      setStatus(await api.status());
    } catch {
      /* backend not ready yet */
    }
  }, []);

  useEffect(() => {
    refreshStatus();
    const source = new EventSource(api.eventsUrl());
    source.addEventListener("status", (event) => {
      try {
        setStatus(JSON.parse((event as MessageEvent).data));
      } catch {
        /* ignore malformed event */
      }
    });
    const timer = window.setInterval(refreshStatus, 8000);
    return () => {
      source.close();
      window.clearInterval(timer);
    };
  }, [refreshStatus]);

  const libraryReady = Boolean(status?.library.ready);

  const runSearch = useCallback(async () => {
    if (!libraryReady) return;
    setSearching(true);
    setSearchError(null);
    try {
      const response = await api.search(query, filtersToParams(filters), 40);
      setResults(response);
    } catch (exc) {
      setSearchError(exc instanceof Error ? exc.message : String(exc));
    } finally {
      setSearching(false);
    }
  }, [filters, libraryReady, query]);

  useEffect(() => {
    if (!libraryReady) return;
    const timer = window.setTimeout(runSearch, 220);
    return () => window.clearTimeout(timer);
  }, [runSearch, libraryReady]);

  const selectDocument = useCallback(async (documentId: number) => {
    setSelectedId(documentId);
    setDetailLoading(true);
    setGraph(null);
    try {
      const [document, graphData] = await Promise.all([
        api.document(documentId),
        api.graph(documentId).catch(() => ({ nodes: [], edges: [] })),
      ]);
      setDetail(document);
      setGraph(graphData);
    } finally {
      setDetailLoading(false);
    }
  }, []);

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        searchInputRef.current?.focus();
      }
      if (event.key === "Escape") {
        setSelectedId(null);
        setDetail(null);
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  const items = results?.items ?? [];

  const content = useMemo(() => {
    if (!status) {
      return (
        <div className="flex h-full items-center justify-center gap-2 text-[var(--muted)]">
          <Loader2 size={16} className="spin" /> 正在启动本地索引服务…
        </div>
      );
    }
    if (!libraryReady || (status.sources === 0 && view === "search")) {
      return <Setup status={status} onRefresh={refreshStatus} />;
    }
    if (view === "sources") {
      return <SourcesPage onRefresh={refreshStatus} />;
    }
    if (view === "encrypted") {
      return <EncryptedPage />;
    }
    if (view === "settings") {
      return <SettingsPage status={status} onRefresh={refreshStatus} />;
    }
    return (
      <div className="flex h-full min-w-0 flex-1">
        <div className="flex min-w-0 flex-1 flex-col">
          <div className="flex items-center gap-2 px-4 pt-3">
            <div className="relative flex-1">
              <SearchIcon
                size={15}
                className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-[var(--muted)]"
              />
              <input
                ref={searchInputRef}
                className="input !pl-9"
                placeholder="搜索内容、文件名、自然语言，例如：上周修改的合同"
                value={query}
                onChange={(event) => {
                  setQuery(event.target.value);
                  if (view !== "search") setView("search");
                }}
                autoFocus
              />
              {searching && (
                <Loader2
                  size={14}
                  className="spin absolute right-3 top-1/2 -translate-y-1/2 text-[var(--muted)]"
                />
              )}
            </div>
          </div>
          <FilterBar filters={filters} onChange={setFilters} />

          {results?.explanation?.length ? (
            <div className="flex flex-wrap gap-1.5 px-4 pt-2 text-[11px] text-[var(--muted)]">
              {results.explanation.map((line, index) => (
                <span key={index} className="chip neutral">
                  {line}
                </span>
              ))}
              <span className="ml-auto">{results.total} 个结果 · {results.elapsed_ms}ms</span>
            </div>
          ) : null}

          {searchError && (
            <div className="m-4 rounded-xl bg-[rgba(255,59,48,0.12)] p-3 text-[12px] text-[var(--danger)]">
              {searchError}
            </div>
          )}

          <div className="min-h-0 flex-1 overflow-auto p-2">
            {items.length === 0 && !searching ? (
              <div className="p-8 text-center text-[12.5px] text-[var(--muted)]">
                {query ? "没有找到匹配内容。" : "输入关键词开始搜索；空搜索显示最近修改的文档。"}
              </div>
            ) : (
              items.map((item) => (
                <ResultCard
                  key={item.document_id}
                  item={item}
                  selected={selectedId === item.document_id}
                  onSelect={() => selectDocument(item.document_id)}
                  onOpen={() => api.openDocument(item.document_id).then(() => api.feedback(query, item.document_id, "open"))}
                  onReveal={() => api.revealDocument(item.document_id)}
                />
              ))
            )}
          </div>
        </div>

        <div className="w-[430px] shrink-0 border-l border-[var(--border)]">
          <DetailPanel
            detail={detail}
            graph={graph}
            loading={detailLoading}
            onClose={() => {
              setSelectedId(null);
              setDetail(null);
            }}
            onSelectDocument={selectDocument}
            onRefresh={() => {
              if (selectedId) selectDocument(selectedId);
              refreshStatus();
            }}
          />
        </div>
      </div>
    );
  }, [
    detail,
    detailLoading,
    filters,
    graph,
    items,
    libraryReady,
    query,
    refreshStatus,
    results,
    searchError,
    searching,
    selectDocument,
    selectedId,
    status,
    view,
  ]);

  if (status && !libraryReady) {
    return (
      <div className="flex h-full flex-col">
        <div className="min-h-0 flex-1 overflow-auto">{content}</div>
        <StatusBar status={status} />
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col">
      <div className="flex min-h-0 flex-1">
        <Sidebar view={view} onChange={setView} encryptedCount={status?.encrypted ?? 0} />
        <div className="flex min-w-0 flex-1 flex-col">{content}</div>
      </div>
      <StatusBar status={status} />
    </div>
  );
}
