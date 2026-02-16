import { NextResponse, type NextRequest } from "next/server";
import { normalizeLang, pickLang } from "./lib/i18n";

export function middleware(req: NextRequest) {
  const url = req.nextUrl;

  const queryLang = normalizeLang(url.searchParams.get("lang"));
  const cookieLang = req.cookies.get("booking_lang")?.value ?? null;
  const acceptLanguage = req.headers.get("accept-language");

  const lang = pickLang({ queryLang: queryLang ?? undefined, cookieLang, acceptLanguage, fallback: "hr" });
  const res = NextResponse.next();

  // If user explicitly set ?lang=, persist it. Otherwise set it once from header/fallback.
  if (queryLang || !cookieLang) {
    res.cookies.set("booking_lang", lang, { path: "/", sameSite: "lax", maxAge: 60 * 60 * 24 * 365 });
  }

  return res;
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};

