/**
 * Chinese catalog. This object is the source of truth for the message shape:
 * `Catalog` is derived from it, so English must define exactly the same keys
 * (see en.ts). Values are plain strings, or functions when the message needs
 * interpolation or plural forms.
 */
export const zhCN = {
  brand: "寻册",

  nav: {
    search: "搜索",
    recent: "最近",
    sources: "索引目录",
    encrypted: "加密文件",
    settings: "设置",
    help: "帮助",
    localOnly: "所有数据仅保存在本机",
  },

  app: {
    title: "Findarium · 寻册",
    starting: "正在启动本地索引服务…",
    placeholder: "搜索内容、文件名、自然语言，例如：上周修改的合同",
    results: (total: number, ms: number) => `${total} 个结果 · ${ms}ms`,
    noMatches: "没有找到匹配内容。",
    emptyHint: "输入关键词开始搜索；空搜索显示最近修改的文档。",
  },

  actions: {
    open: "打开",
    reveal: "在 Finder 中显示",
    revealShort: "Finder",
    reindex: "重建索引",
    reprobe: "重新检测",
    choose: "选择",
    addFolder: "添加文件夹",
    openSettings: "打开设置",
    removeFolder: "移除目录",
    scanNow: "立即扫描",
  },

  setup: {
    title: "建立本地索引库",
    intro:
      "所有正文、向量和搜索历史都保存在你选择的文件夹里，不会上传到任何服务器。加密文件只记录文件名和路径，不会提取正文；解密后会自动重新索引。",
    step1: "1. 索引库文件夹",
    pathPlaceholder: "例如 ~/MaterialIndex",
    pathWarning:
      "不要放在 iCloud/Dropbox 等自动同步目录，也不要放在会被公司加密软件加密的目录。应用支持目录只保存一个指向这里的位置指针。",
    embedding: "启用本地中文语义检索（首次会下载约 90 MB 模型，可稍后在设置中重试）",
    initialize: "初始化索引库",
    step2: "2. 添加要索引的目录",
    chooseFolders: "选择文件夹",
    currentLibraryPrefix: "当前索引库：",
    fallback: "程序目录不可写，已自动回退到应用支持目录；可在设置中迁移。",
    permission:
      "如果添加 ~/Documents、~/Desktop 等目录时读不到文件，需要在系统设置中授予“完全磁盘访问权限”。",
  },

  result: {
    encrypted: "已加密",
    encryptedNote: "该文件已加密，正文未索引；文件名/路径仍可搜索。",
    noSnippet: "没有可显示的正文片段。",
  },

  detail: {
    loading: "正在加载…",
    selectPrompt: "选择左侧结果查看详情",
    modified: (time: string) => `修改 ${time}`,
    pageCount: (n: number) => `${n} 页`,
    sheetCount: (n: number) => `${n} 个工作表`,
    wordCount: (n: number) => `${n} 词`,
    encryptedTitle: "该文件已加密，正文未索引",
    encryptedExplain: (reason: string) =>
      `${reason}。文件解密后会自动重新提取；应用不会尝试解密或绕过加密。`,
    encryptedFallback: "检测到受保护内容",
    tabContent: "内容",
    tabRelated: (n: number) => `相关文档 (${n})`,
    tabGraph: "关系图",
    keywords: "关键词",
    extracted: "提取内容",
    encryptedNoBody: "加密文件没有正文内容。",
    noBody: "没有提取到正文内容。",
    metadata: "元数据",
    metadataEntry: (key: string, value: string) => `${key}：${value}`,
    noRelated: "暂无相关文档。",
    loadingGraph: "正在加载关系图…",
    listSeparator: "；",
  },

  filters: {
    text: "文本",
    web: "网页",
    anyTime: "不限时间",
    today: "今天",
    last7: "最近 7 天",
    last30: "最近 30 天",
    thisYear: "今年",
    allFiles: "全部文件",
    onlyEncrypted: "只看加密",
    excludeEncrypted: "排除加密",
    sortRelevance: "按相关度",
    sortModified: "按修改时间",
    sortCreated: "按创建时间",
  },

  pdf: {
    previewFailed: (error: string) => `PDF 预览失败：${error}`,
  },

  graph: {
    empty: "暂无关系数据。",
  },

  encrypted: {
    title: "加密 / 受保护文件",
    subtitle:
      "这些文件只记录了文件名和路径，没有提取正文。文件解密后会自动重新索引；应用不会尝试解密或绕过加密。",
    recheckAll: "全部重新检测",
    lastProbe: (time: string) => ` · 最后检测 ${time}`,
    empty: "当前没有检测到加密文件。",
  },

  sources: {
    title: "索引目录",
    subtitle: "已索引目录会实时监听变化，并每 10 分钟做一次校对扫描。",
    documents: (n: number) => `${n} 个文档`,
    encrypted: (n: number) => `${n} 个加密`,
    failed: (n: number) => `${n} 个失败`,
    lastScan: (time: string) => `最后扫描 ${time}`,
    never: "尚未",
    excludeRules: "排除规则",
    excludePlaceholder: "例如 *.tmp、临时/*",
    removeConfirm: "移除该目录会删除它在本索引库中的所有内容，确定继续？",
    empty: "还没有索引目录，点击右上角添加。",
  },

  settings: {
    title: "设置",
    language: "界面语言",
    languageAuto: "跟随系统",
    languageZh: "中文",
    languageEn: "English",
    languageNote: "切换后界面与搜索结果文案立即更新；提取时写入索引的少量文字会在下次重建索引后更新。",
    library: "索引库",
    libraryFallback: "程序目录不可写，数据已回退到应用支持目录；可以在这里迁移到其他位置。",
    defaultLocationPrefix: "默认位置：程序所在目录下的 ",
    programDir: (dir: string) => `（当前程序目录：${dir}）`,
    relocate: "迁移索引库位置",
    relocateConfirm: (path: string) =>
      `将索引库迁移到：\n${path}\n\n迁移期间会暂停索引，确定继续？`,
    rebuild: "重建全部索引",
    rebuildQueued: (n: number) => `已加入重建队列：${n} 个文档`,
    privacy: "完全磁盘访问权限",
    scanSection: "扫描与加密复查",
    scanInterval: "定时校对间隔（秒）",
    encryptedInterval: "加密文件复查间隔（秒）",
    saved: "已保存",
    performance: "索引性能",
    performanceSummary: (p: {
      active: number;
      desired: number;
      max: number;
      load: string;
      cpu: string;
      batch: string;
    }) =>
      `并发 worker：${p.active} / ${p.desired}（上限 ${p.max}） · 系统负载 ${p.load} · 进程 CPU ${p.cpu}% · 向量批大小 ${p.batch}`,
    performanceNote:
      "空闲时自动提高提取并发；CPU 占用或系统负载升高时降回 1 个 worker，并缩小向量批大小，避免影响你正在使用的其他程序。",
    model: "语义模型",
    modelLabel: "模型：",
    statusLabel: "状态：",
    modelReady: "已就绪",
    modelLoading: "加载中",
    modelFailed: (error: string) => `失败（${error}）`,
    modelDisabled: "未启用",
    modelUnknownError: "未知错误",
    modelIndexed: (n: number) => ` · 已向量化 ${n} 个文档`,
    modelRetry: "重试模型加载 / 重新排队",
    modelRetryResult: (state: string, n: number) => `模型状态：${state}，重新排队 ${n} 个文档`,
    problems: "索引问题",
  },

  status: {
    connecting: "正在连接本地服务…",
    semantic: (n: number) => `语义 ${n}`,
    semanticLoading: "语义模型加载中",
    semanticUnavailable: "语义不可用",
    semanticOff: "语义已关闭",
    sources: (n: number) => `${n} 个目录`,
    documents: (n: number) => `${n} 个文档`,
    toIndex: (n: number) => `待索引 ${n}`,
    queue: (n: number) => `队列 ${n}`,
    workers: (active: number, desired: number, max: number) =>
      `并发 ${active}/${desired}（上限 ${max}）`,
    load: (value: string) => `负载 ${value}`,
    encrypted: (n: number) => `加密 ${n}`,
    failed: (n: number) => `失败 ${n}`,
    noLibrary: "索引库未初始化",
  },

  help: {
    title: "帮助",
    subtitle: "Findarium 完全在本机运行：文档不会被复制，也不会上传到任何服务器。",
    quickStart: {
      title: "快速上手",
      steps: [
        "在“索引目录”里添加要索引的文件夹；首次扫描会自动开始。",
        "在搜索框输入关键词，或用一句话描述你要找的东西，例如“上周修改的合同”。",
        "点击结果查看正文片段、位置、相关文档和关系图，也可以直接打开文件或按 ⌘K 重新聚焦搜索框。",
        "索引在后台持续进行，文件改动会在几秒内反映到搜索结果里。",
      ],
    },
    syntax: {
      title: "搜索语法",
      intro: "除了直接输入关键词，还支持这些写法（也可以直接用界面上的筛选器）：",
      rows: [
        { syntax: "ext:pdf 验收报告", meaning: "只看 PDF；也支持 ext:word、ext:excel、ext:ppt、ext:markdown" },
        { syntax: 'folder:"项目A"', meaning: "限定在路径包含“项目A”的文档里搜索" },
        { syntax: "modified:>=2026-01-01", meaning: "按修改时间过滤，created: 同理" },
        { syntax: "size:>10mb", meaning: "按文件大小过滤" },
        { syntax: "上周修改的合同", meaning: "中文时间词（今天、昨天、本周、上个月、今年…）会转成时间过滤" },
        { syntax: "最近 7 天的报价单", meaning: "“最近 N 天/周/月”会过滤时间并偏向较新的文档" },
        { syntax: "last week reports", meaning: "英文时间词同样可用：today、yesterday、this week、last month…" },
      ],
    },
    encrypted: {
      title: "加密与受保护文件",
      body: "公司加密软件保护的文件会被识别并标注，只记录文件名和路径，不提取正文，也不会出现在语义检索里。文件名和路径仍然可以搜索。文件解密后，后台复查会自动重新提取并索引；重新加密后旧正文会被清除。应用不会尝试解密、破解或绕过加密，也不会修改你的文件。",
    },
    performance: {
      title: "索引与性能",
      body: "索引使用一个 1–4 个 worker 的小型进程池：系统空闲时自动提高提取并发，CPU 占用或负载升高时降回 1 个 worker，同时缩小向量批大小，尽量不影响你正在使用的其他程序。语义向量在后台单独补全，关键词搜索不必等它完成。当前的 worker 数量、负载和批大小可以在设置页看到。",
    },
    privacy: {
      title: "数据与隐私",
      body: "所有正文、向量、任务和搜索历史都保存在你选择的索引库文件夹里（默认在程序目录下的 FindariumData，里面只有一个 index.sqlite3 和 backups/、models/、logs/）。应用支持目录里只放一个指向索引库的位置指针。除首次下载语义模型外不发任何网络请求，也不收集遥测数据。",
    },
    faq: {
      title: "常见问题",
      items: [
        {
          q: "添加 ~/Documents、~/Desktop 后读不到文件？",
          a: "macOS 需要授予“完全磁盘访问权限”：打开 系统设置 → 隐私与安全性 → 完全磁盘访问权限，把 Findarium 打开。设置页里有直达按钮。",
        },
        {
          q: "语义检索不可用？",
          a: "首次使用需要下载约 90 MB 的中文模型。断网或下载失败时关键词搜索仍然可用，可以在设置页点“重试模型加载 / 重新排队”。",
        },
        {
          q: "外接盘没挂载，索引会被删掉吗？",
          a: "不会。来源目录不可访问时只会标记为暂不可用，保留已有索引；重新挂载并扫描后即可继续。",
        },
        {
          q: "扫描版 PDF 搜不到内容？",
          a: "没有文本层的 PDF 会被标记为“部分索引”，可以按文件名搜到。当前版本不做 OCR。",
        },
        {
          q: "能把索引库放在 iCloud/Dropbox 里吗？",
          a: "不建议。同步工具可能损坏 SQLite 的 WAL 文件，也可能被公司加密软件加密。请在设置页迁移到本地目录。",
        },
      ],
    },
  },
};
