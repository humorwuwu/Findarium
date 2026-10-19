import { useI18n } from "../i18n";

export interface Filters {
  ext: string[];
  time: string;
  encrypted: string;
  sort: string;
}

export const DEFAULT_FILTERS: Filters = {
  ext: [],
  time: "any",
  encrypted: "any",
  sort: "relevance",
};

interface Props {
  filters: Filters;
  onChange: (filters: Filters) => void;
}

export function FilterBar({ filters, onChange }: Props) {
  const { t } = useI18n();
  const extensions: { value: string; label: string }[] = [
    { value: "pdf", label: "PDF" },
    { value: "docx", label: "Word" },
    { value: "xlsx", label: "Excel" },
    { value: "pptx", label: "PPT" },
    { value: "md", label: "Markdown" },
    { value: "txt", label: t.filters.text },
    { value: "html", label: t.filters.web },
  ];
  const times: { value: string; label: string }[] = [
    { value: "any", label: t.filters.anyTime },
    { value: "today", label: t.filters.today },
    { value: "week", label: t.filters.last7 },
    { value: "month", label: t.filters.last30 },
    { value: "year", label: t.filters.thisYear },
  ];

  function toggleExt(value: string) {
    const next = filters.ext.includes(value)
      ? filters.ext.filter((item) => item !== value)
      : [...filters.ext, value];
    onChange({ ...filters, ext: next });
  }

  return (
    <div className="flex flex-wrap items-center gap-1.5 border-b border-[var(--border)] px-4 py-2">
      {extensions.map((item) => (
        <button
          key={item.value}
          className={`chip ${filters.ext.includes(item.value) ? "" : "neutral"}`}
          onClick={() => toggleExt(item.value)}
        >
          {item.label}
        </button>
      ))}
      <span className="mx-1 h-4 w-px bg-[var(--border)]" />
      <select
        className="rounded-lg border border-[var(--border)] bg-transparent px-2 py-1 text-[11.5px]"
        value={filters.time}
        onChange={(event) => onChange({ ...filters, time: event.target.value })}
      >
        {times.map((item) => (
          <option key={item.value} value={item.value}>
            {item.label}
          </option>
        ))}
      </select>
      <select
        className="rounded-lg border border-[var(--border)] bg-transparent px-2 py-1 text-[11.5px]"
        value={filters.encrypted}
        onChange={(event) => onChange({ ...filters, encrypted: event.target.value })}
      >
        <option value="any">{t.filters.allFiles}</option>
        <option value="only">{t.filters.onlyEncrypted}</option>
        <option value="exclude">{t.filters.excludeEncrypted}</option>
      </select>
      <select
        className="ml-auto rounded-lg border border-[var(--border)] bg-transparent px-2 py-1 text-[11.5px]"
        value={filters.sort}
        onChange={(event) => onChange({ ...filters, sort: event.target.value })}
      >
        <option value="relevance">{t.filters.sortRelevance}</option>
        <option value="modified">{t.filters.sortModified}</option>
        <option value="created">{t.filters.sortCreated}</option>
      </select>
    </div>
  );
}

export function filtersToParams(filters: Filters): {
  ext?: string[];
  after?: string;
  before?: string;
  encrypted?: string;
  sort?: string;
} {
  const now = new Date();
  const after = (() => {
    switch (filters.time) {
      case "today":
        return new Date(now.getFullYear(), now.getMonth(), now.getDate()).toISOString();
      case "week":
        return new Date(now.getTime() - 7 * 86400_000).toISOString();
      case "month":
        return new Date(now.getTime() - 30 * 86400_000).toISOString();
      case "year":
        return new Date(now.getFullYear(), 0, 1).toISOString();
      default:
        return undefined;
    }
  })();
  return {
    ext: filters.ext.length ? filters.ext : undefined,
    after,
    encrypted: filters.encrypted !== "any" ? filters.encrypted : undefined,
    sort: filters.sort !== "relevance" ? filters.sort : undefined,
  };
}
