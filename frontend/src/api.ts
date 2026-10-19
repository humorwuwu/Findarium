import type {
  AppStatus,
  DocumentDetail,
  EncryptedDocument,
  GraphData,
  SearchResponse,
  Source,
} from "./types";

declare global {
  interface Window {
    pywebview?: {
      api?: {
        pick_folder?: () => Promise<string | null>;
        pick_folders?: () => Promise<string[]>;
      };
    };
  }
}

const params = new URLSearchParams(window.location.search);
export const TOKEN = params.get("token") ?? "";
export const API_BASE = (params.get("api") ?? "").replace(/\/$/, "");

function url(path: string): string {
  return `${API_BASE}${path}`;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url(path), {
    ...init,
    headers: {
      "Content-Type": "application/json",
      "X-Findarium-Token": TOKEN,
      ...(init?.headers ?? {}),
    },
  });
  if (!response.ok) {
    let detail = `${response.status} ${response.statusText}`;
    try {
      const body = await response.json();
      if (body?.detail) detail = String(body.detail);
    } catch {
      /* ignore */
    }
    throw new Error(detail);
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export const api = {
  status: () => request<AppStatus>("/api/status"),
  libraryStatus: () => request<AppStatus["library"]>("/api/library"),
  initializeLibrary: (path: string, embeddingEnabled = true) =>
    request<AppStatus>("/api/library/initialize", {
      method: "POST",
      body: JSON.stringify({ path, embedding_enabled: embeddingEnabled }),
    }),
  relocateLibrary: (path: string) =>
    request<AppStatus>("/api/library", {
      method: "PUT",
      body: JSON.stringify({ path, embedding_enabled: true }),
    }),
  sources: () => request<Source[]>("/api/sources"),
  addSource: (path: string, label?: string) =>
    request<{ id: number; path: string }>("/api/sources", {
      method: "POST",
      body: JSON.stringify({ path, label }),
    }),
  patchSource: (
    id: number,
    body: { enabled?: boolean; label?: string; exclude_globs?: string },
  ) =>
    request<{ ok: boolean }>(`/api/sources/${id}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),
  removeSource: (id: number) =>
    request<{ ok: boolean; removed_documents: number }>(`/api/sources/${id}`, {
      method: "DELETE",
    }),
  scanSource: (id: number) =>
    request<{ ok: boolean }>(`/api/sources/${id}/scan`, { method: "POST" }),
  search: (
    query: string,
    filters: {
      ext?: string[];
      after?: string;
      before?: string;
      folder?: string;
      encrypted?: string;
      sort?: string;
    },
    limit = 30,
  ) => {
    const search = new URLSearchParams();
    if (query) search.set("q", query);
    for (const ext of filters.ext ?? []) search.append("ext", ext);
    if (filters.after) search.set("after", filters.after);
    if (filters.before) search.set("before", filters.before);
    if (filters.folder) search.set("folder", filters.folder);
    if (filters.encrypted) search.set("encrypted", filters.encrypted);
    if (filters.sort) search.set("sort", filters.sort);
    search.set("limit", String(limit));
    return request<SearchResponse>(`/api/search?${search.toString()}`);
  },
  feedback: (query: string, documentId: number, action: string) =>
    request<{ ok: boolean }>("/api/search/feedback", {
      method: "POST",
      body: JSON.stringify({ query, document_id: documentId, action }),
    }),
  document: (id: number) => request<DocumentDetail>(`/api/documents/${id}`),
  related: (id: number) =>
    request<DocumentDetail["related"]>(`/api/documents/${id}/related`),
  graph: (id: number) => request<GraphData>(`/api/documents/${id}/graph`),
  openDocument: (id: number) =>
    request<{ ok: boolean }>(`/api/documents/${id}/open`, { method: "POST" }),
  revealDocument: (id: number) =>
    request<{ ok: boolean }>(`/api/documents/${id}/reveal`, { method: "POST" }),
  reindexDocument: (id: number) =>
    request<{ ok: boolean }>(`/api/documents/${id}/reindex`, { method: "POST" }),
  probeDocument: (id: number) =>
    request<{ ok: boolean }>(`/api/documents/${id}/probe`, { method: "POST" }),
  encrypted: () => request<EncryptedDocument[]>("/api/encrypted"),
  recheckEncrypted: () =>
    request<{ queued: number }>("/api/encrypted/recheck", { method: "POST" }),
  settings: () => request<Record<string, unknown>>("/api/settings"),
  updateSettings: (body: Record<string, unknown>) =>
    request<Record<string, unknown>>("/api/settings", {
      method: "PUT",
      body: JSON.stringify(body),
    }),
  rebuild: () => request<{ queued: number }>("/api/index/rebuild", { method: "POST" }),
  errors: () =>
    request<{ jobs: unknown[]; documents: unknown[] }>("/api/errors"),
  retryModel: () =>
    request<{ ok: boolean; queued: number; state: string }>("/api/model/retry", {
      method: "POST",
    }),
  openPrivacySettings: () =>
    request<{ ok: boolean }>("/api/native/open-privacy-settings", {
      method: "POST",
    }),
  fileUrl: (id: number) => `${url(`/api/documents/${id}/file`)}?token=${encodeURIComponent(TOKEN)}`,
  eventsUrl: () => `${url("/api/events")}?token=${encodeURIComponent(TOKEN)}`,
};

export async function pickFolder(): Promise<string | null> {
  const native = window.pywebview?.api?.pick_folder;
  if (native) {
    try {
      return await native();
    } catch {
      /* fall through */
    }
  }
  try {
    const result = await request<{ path: string }>("/api/native/pick-folder", {
      method: "POST",
    });
    return result.path;
  } catch {
    return null;
  }
}

export async function pickFolders(): Promise<string[]> {
  const native = window.pywebview?.api?.pick_folders;
  if (native) {
    try {
      return await native();
    } catch {
      /* fall through */
    }
  }
  const single = await pickFolder();
  return single ? [single] : [];
}
