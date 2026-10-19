import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { api, setApiLanguage } from "../api";
import { formatBytes, formatTime } from "../format";
import { en } from "./en";
import type { Catalog, LanguagePreference, Locale } from "./types";
import { zhCN } from "./zh-CN";

const CATALOGS: Record<Locale, Catalog> = { "zh-CN": zhCN, en };

/** Language for the very first render: ?lang= (dev) then the system language. */
function detectLocale(): Locale {
  const override = new URLSearchParams(window.location.search).get("lang");
  if (override) return override.toLowerCase().startsWith("en") ? "en" : "zh-CN";
  return (navigator.language ?? "").toLowerCase().startsWith("zh") ? "zh-CN" : "en";
}

function asPreference(value: unknown): LanguagePreference {
  return value === "zh-CN" || value === "en" || value === "auto" ? value : "auto";
}

export interface I18n {
  /** Messages for the active language. */
  t: Catalog;
  locale: Locale;
  /** Stored preference: `auto` follows the system language. */
  preference: LanguagePreference;
  setPreference: (preference: LanguagePreference) => Promise<void>;
  /** Re-read the stored preference (for example once the library is ready). */
  refresh: () => Promise<void>;
  time: (ns: number | null | undefined) => string;
  bytes: (bytes: number) => string;
}

const I18nContext = createContext<I18n | null>(null);

export function LocaleProvider({ children }: { children: ReactNode }) {
  const [systemLocale] = useState<Locale>(detectLocale);
  const [preference, setPreferenceState] = useState<LanguagePreference>("auto");
  const locale = preference === "auto" ? systemLocale : preference;
  const t = CATALOGS[locale];

  const refresh = useCallback(async () => {
    try {
      const settings = await api.settings();
      setPreferenceState(asPreference(settings.language));
    } catch {
      /* library not ready yet; keep the system language */
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  useEffect(() => {
    // Every request carries the language so backend text matches the UI.
    setApiLanguage(locale);
    document.documentElement.lang = locale;
    document.title = t.app.title;
  }, [locale, t]);

  const setPreference = useCallback(async (next: LanguagePreference) => {
    setPreferenceState(next);
    try {
      await api.updateSettings({ language: next });
    } catch {
      /* keep the local choice even if persisting fails */
    }
  }, []);

  const value = useMemo<I18n>(
    () => ({
      t,
      locale,
      preference,
      setPreference,
      refresh,
      time: (ns) => formatTime(ns, locale),
      bytes: formatBytes,
    }),
    [locale, preference, refresh, setPreference, t],
  );

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n(): I18n {
  const value = useContext(I18nContext);
  if (value === null) {
    throw new Error("useI18n must be used inside LocaleProvider");
  }
  return value;
}
