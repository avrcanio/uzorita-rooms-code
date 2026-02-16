import type { Metadata } from "next";
import { Fraunces, Manrope } from "next/font/google";
import Script from "next/script";
import { cookies, headers } from "next/headers";
import "./globals.css";
import { getPublicProperty } from "../lib/api";
import { pickLang } from "../lib/i18n";

const manrope = Manrope({
  variable: "--font-manrope",
  subsets: ["latin"],
});

const fraunces = Fraunces({
  variable: "--font-fraunces",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  metadataBase: new URL(process.env.NEXT_PUBLIC_SITE_URL || "https://booking.uzorita.hr"),
  title: "Uzorita Luxury Rooms",
  description: "Rezervacije za Uzorita Luxury Rooms",
  icons: {
    icon: "/kapa.png"
  }
};

export default async function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  const cookieStore = await cookies();
  const headerStore = await headers();
  const cookieLang = cookieStore.get("booking_lang")?.value ?? null;
  const acceptLanguage = headerStore.get("accept-language");
  const lang = pickLang({ cookieLang, acceptLanguage, fallback: "hr" });
  let gaId = "";
  try {
    const property = await getPublicProperty({ lang });
    gaId = (property.google_analytics_measurement_id || "").trim();
  } catch {
    gaId = "";
  }

  return (
    <html lang={lang}>
      <body className={`${manrope.variable} ${fraunces.variable} antialiased`}>
        {gaId ? (
          <>
            <Script src={`https://www.googletagmanager.com/gtag/js?id=${encodeURIComponent(gaId)}`} strategy="afterInteractive" />
            <Script
              id="ga4-init"
              strategy="afterInteractive"
              dangerouslySetInnerHTML={{
                __html: `
window.dataLayer = window.dataLayer || [];
function gtag(){dataLayer.push(arguments);}
gtag('js', new Date());
gtag('config', '${gaId}');
                `.trim(),
              }}
            />
          </>
        ) : null}
        {children}
      </body>
    </html>
  );
}
