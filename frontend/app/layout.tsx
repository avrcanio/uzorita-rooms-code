import type { Metadata } from "next";
import { DM_Mono, Manrope } from "next/font/google";
import "./globals.css";

const manrope = Manrope({
  variable: "--font-manrope",
  subsets: ["latin"],
});

const dmMono = DM_Mono({
  variable: "--font-dm-mono",
  weight: ["400", "500"],
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Uzorita Rooms",
  description: "Recepcijski sustav za Uzorita Rooms",
  icons: {
    icon: "/kapa.png",
    shortcut: "/kapa.png",
    apple: "/kapa.png",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="hr">
      <body className={`${manrope.variable} ${dmMono.variable} antialiased`}>
        {children}
      </body>
    </html>
  );
}
