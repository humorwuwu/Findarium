import { zhCN } from "./zh-CN";

/**
 * Message shape derived from the Chinese catalog: plain strings stay `string`,
 * and functions keep their parameter types. English is checked against it, so a
 * missing, extra or mistyped key fails `npm run typecheck`.
 */
export type Catalog = typeof zhCN;

export type Locale = "zh-CN" | "en";

/** Value stored in the library settings; `auto` follows the system language. */
export type LanguagePreference = "auto" | Locale;

export const LOCALES: Locale[] = ["zh-CN", "en"];
