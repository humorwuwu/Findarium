import type { Catalog } from "./types";

/** English catalog. Must define exactly the same keys as zh-CN.ts. */
export const en: Catalog = {
  brand: "Findarium",

  nav: {
    search: "Search",
    recent: "Recent",
    sources: "Folders",
    encrypted: "Encrypted",
    settings: "Settings",
    help: "Help",
    localOnly: "All data stays on this Mac",
  },

  app: {
    title: "Findarium",
    starting: "Starting the local index service…",
    placeholder: "Search content, file names or plain language, e.g. contracts modified last week",
    results: (total, ms) => `${total} results · ${ms}ms`,
    noMatches: "No matching content found.",
    emptyHint: "Type a keyword to search; an empty search shows recently modified documents.",
  },

  actions: {
    open: "Open",
    reveal: "Reveal in Finder",
    revealShort: "Finder",
    reindex: "Reindex",
    reprobe: "Recheck",
    choose: "Choose",
    addFolder: "Add folder",
    openSettings: "Open settings",
    removeFolder: "Remove folder",
    scanNow: "Scan now",
  },

  setup: {
    title: "Create your local index library",
    intro:
      "All extracted text, vectors and search history live in the folder you choose and are never uploaded anywhere. Encrypted files keep only their name and path — no content is extracted — and are indexed automatically once they become readable.",
    step1: "1. Library folder",
    pathPlaceholder: "e.g. ~/MaterialIndex",
    pathWarning:
      "Do not place it in an iCloud/Dropbox-style sync folder or in a folder a company encryption client encrypts. The app-support directory only holds a pointer to this location.",
    embedding: "Enable local Chinese semantic search (downloads a ~90 MB model on first use; can be retried later in Settings)",
    initialize: "Create library",
    step2: "2. Add folders to index",
    chooseFolders: "Choose folders",
    currentLibraryPrefix: "Current library: ",
    fallback:
      "The program directory is not writable, so data fell back to the app-support directory; you can move it in Settings.",
    permission:
      "If files in ~/Documents, ~/Desktop and similar folders cannot be read, grant “Full Disk Access” in System Settings.",
  },

  result: {
    encrypted: "Encrypted",
    encryptedNote: "This file is encrypted, so its content is not indexed; name and path are still searchable.",
    noSnippet: "No text snippet to show.",
  },

  detail: {
    loading: "Loading…",
    selectPrompt: "Select a result to see details",
    modified: (time) => `Modified ${time}`,
    pageCount: (n) => `${n} ${n === 1 ? "page" : "pages"}`,
    sheetCount: (n) => `${n} ${n === 1 ? "sheet" : "sheets"}`,
    wordCount: (n) => `${n} words`,
    encryptedTitle: "This file is encrypted; its content is not indexed",
    encryptedExplain: (reason) =>
      `${reason}. It is re-extracted automatically once decrypted; the app never tries to decrypt or bypass encryption.`,
    encryptedFallback: "Protected content detected",
    tabContent: "Content",
    tabRelated: (n) => `Related (${n})`,
    tabGraph: "Graph",
    keywords: "Keywords",
    extracted: "Extracted content",
    encryptedNoBody: "Encrypted files have no extracted content.",
    noBody: "No content was extracted.",
    metadata: "Metadata",
    metadataEntry: (key, value) => `${key}: ${value}`,
    noRelated: "No related documents yet.",
    loadingGraph: "Loading the relation graph…",
    listSeparator: "; ",
  },

  filters: {
    text: "Text",
    web: "Web",
    anyTime: "Any time",
    today: "Today",
    last7: "Last 7 days",
    last30: "Last 30 days",
    thisYear: "This year",
    allFiles: "All files",
    onlyEncrypted: "Encrypted only",
    excludeEncrypted: "Exclude encrypted",
    sortRelevance: "By relevance",
    sortModified: "By modified",
    sortCreated: "By created",
  },

  pdf: {
    previewFailed: (error) => `PDF preview failed: ${error}`,
  },

  graph: {
    empty: "No relation data yet.",
  },

  encrypted: {
    title: "Encrypted / protected files",
    subtitle:
      "Only the file name and path are recorded for these files; no content was extracted. They are re-indexed automatically once decrypted. The app never tries to decrypt or bypass encryption.",
    recheckAll: "Recheck all",
    lastProbe: (time) => ` · last checked ${time}`,
    empty: "No encrypted files detected right now.",
  },

  sources: {
    title: "Indexed folders",
    subtitle: "Indexed folders are watched in real time, with a reconciliation scan every 10 minutes.",
    documents: (n) => `${n} ${n === 1 ? "document" : "documents"}`,
    encrypted: (n) => `${n} encrypted`,
    failed: (n) => `${n} failed`,
    lastScan: (time) => `Last scan ${time}`,
    never: "never",
    excludeRules: "Exclude",
    excludePlaceholder: "e.g. *.tmp, drafts/*",
    removeConfirm:
      "Removing this folder deletes everything it contributed to this library. Continue?",
    empty: "No indexed folders yet — add one with the button above.",
  },

  settings: {
    title: "Settings",
    language: "Language",
    languageAuto: "Follow system",
    languageZh: "中文",
    languageEn: "English",
    languageNote:
      "The interface and search results update immediately. A few labels written into the index while extracting change after the next full reindex.",
    library: "Library",
    libraryFallback:
      "The program directory is not writable, so data fell back to the app-support directory; you can move it here.",
    defaultLocationPrefix: "Default location: ",
    programDir: (dir) => ` (program directory: ${dir})`,
    relocate: "Move library",
    relocateConfirm: (path) =>
      `Move the index library to:\n${path}\n\nIndexing pauses during the move. Continue?`,
    rebuild: "Rebuild the whole index",
    rebuildQueued: (n) => `Queued ${n} documents for rebuild`,
    privacy: "Full Disk Access",
    scanSection: "Scanning and encrypted recheck",
    scanInterval: "Reconciliation interval (seconds)",
    encryptedInterval: "Encrypted-file recheck interval (seconds)",
    saved: "Saved",
    performance: "Indexing performance",
    performanceSummary: (p) =>
      `Workers: ${p.active} / ${p.desired} (max ${p.max}) · load ${p.load} · process CPU ${p.cpu}% · embedding batch ${p.batch}`,
    performanceNote:
      "Extraction runs in parallel when the machine is idle and drops back to a single worker with a smaller embedding batch when CPU usage or load rises, so other apps stay responsive.",
    model: "Semantic model",
    modelLabel: "Model: ",
    statusLabel: "status: ",
    modelReady: "ready",
    modelLoading: "loading",
    modelFailed: (error) => `failed (${error})`,
    modelDisabled: "disabled",
    modelUnknownError: "unknown error",
    modelIndexed: (n) => ` · ${n} documents embedded`,
    modelRetry: "Retry model load / requeue",
    modelRetryResult: (state, n) => `Model state: ${state}, requeued ${n} documents`,
    problems: "Indexing problems",
  },

  status: {
    connecting: "Connecting to the local service…",
    semantic: (n) => `Semantic ${n}`,
    semanticLoading: "Semantic model loading",
    semanticUnavailable: "Semantic unavailable",
    semanticOff: "Semantic off",
    sources: (n) => `${n} ${n === 1 ? "folder" : "folders"}`,
    documents: (n) => `${n} ${n === 1 ? "document" : "documents"}`,
    toIndex: (n) => `Pending ${n}`,
    queue: (n) => `Queue ${n}`,
    workers: (active, desired, max) => `Workers ${active}/${desired} (max ${max})`,
    load: (value) => `Load ${value}`,
    encrypted: (n) => `Encrypted ${n}`,
    failed: (n) => `Failed ${n}`,
    noLibrary: "Library not initialized",
  },

  help: {
    title: "Help",
    subtitle: "Findarium runs entirely on this Mac: documents are never copied or uploaded anywhere.",
    quickStart: {
      title: "Quick start",
      steps: [
        "Add the folders you want indexed under “Folders”; the first scan starts automatically.",
        "Type keywords in the search box, or describe what you are looking for in plain language, e.g. “contracts modified last week”.",
        "Click a result to see snippets, locations, related documents and the relation graph; open the file directly or press ⌘K to focus the search box.",
        "Indexing keeps running in the background — changes to files show up in search within seconds.",
      ],
    },
    syntax: {
      title: "Search syntax",
      intro: "Besides plain keywords you can use these forms (the filter bar does the same thing):",
      rows: [
        { syntax: "ext:pdf acceptance report", meaning: "PDF only; also ext:word, ext:excel, ext:ppt, ext:markdown" },
        { syntax: 'folder:"Project A"', meaning: "Restrict the search to documents whose path contains “Project A”" },
        { syntax: "modified:>=2026-01-01", meaning: "Filter by modification time; created: works the same way" },
        { syntax: "size:>10mb", meaning: "Filter by file size" },
        { syntax: "last week contracts", meaning: "English time words: today, yesterday, this week, last month, this year…" },
        { syntax: "last 7 days quotes", meaning: "“last N days/weeks/months” filters by time and favors newer documents" },
        { syntax: "上周修改的合同", meaning: "Chinese time words work too, in either interface language" },
      ],
    },
    encrypted: {
      title: "Encrypted and protected files",
      body: "Files protected by a company encryption client are detected and marked: only the name and path are stored, no content is extracted, and they are left out of semantic search. Their names and paths stay searchable. Once a file becomes readable, the background recheck extracts and indexes it automatically; if it is encrypted again, the old content is purged. The app never tries to decrypt, crack or bypass encryption, and never modifies your files.",
    },
    performance: {
      title: "Indexing and performance",
      body: "Indexing uses a small pool of 1–4 workers: extraction runs in parallel when the machine is idle and drops back to one worker, with a smaller embedding batch, when CPU usage or load rises. Semantic vectors are backfilled by a separate worker, so keyword search never waits for them. The current worker count, load ratio and batch size are shown in Settings.",
    },
    privacy: {
      title: "Data and privacy",
      body: "All extracted text, vectors, jobs and search history live in the library folder you choose (by default FindariumData next to the program, containing a single index.sqlite3 plus backups/, models/ and logs/). The app-support directory holds only a pointer to that location. Apart from the one-time semantic model download the app makes no network requests and collects no telemetry.",
    },
    faq: {
      title: "FAQ",
      items: [
        {
          q: "Files in ~/Documents or ~/Desktop are not being read",
          a: "macOS requires Full Disk Access: open System Settings → Privacy & Security → Full Disk Access and enable Findarium. Settings has a button that opens that pane.",
        },
        {
          q: "Semantic search is unavailable",
          a: "The first use downloads a ~90 MB Chinese model. Keyword search still works offline or if the download fails; use “Retry model load / requeue” in Settings.",
        },
        {
          q: "Will an unmounted external drive delete my index?",
          a: "No. When a source folder is unreachable it is only marked as temporarily unavailable and the existing index is kept; remount the drive and scan again to continue.",
        },
        {
          q: "Scanned PDFs are not searchable",
          a: "PDFs without a text layer are marked “partially indexed” and can still be found by file name. This version does not do OCR.",
        },
        {
          q: "Can the library live in iCloud or Dropbox?",
          a: "Not recommended: sync tools can corrupt SQLite's WAL files, and a company encryption client may encrypt the database itself. Move it to a local folder in Settings.",
        },
      ],
    },
  },
};
