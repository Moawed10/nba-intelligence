import type { Metadata, Viewport } from "next";
import { Barlow_Condensed, Geist, Geist_Mono } from "next/font/google";
import { Suspense } from "react";

import { Providers } from "@/components/providers";
import { RouteFocus } from "@/components/shell/route-focus";
import { TabBar } from "@/components/shell/tab-bar";
import { themeScript } from "@/components/shell/theme-toggle";
import { TopNav } from "@/components/shell/top-nav";

import "./globals.css";

const geist = Geist({ subsets: ["latin"], variable: "--font-geist", display: "swap" });
const geistMono = Geist_Mono({ subsets: ["latin"], variable: "--font-geist-mono", display: "swap" });
// Condensed display face for titles, names and scoreboard numbers.
const display = Barlow_Condensed({
  subsets: ["latin"],
  weight: ["600", "700", "800"],
  variable: "--font-barlow",
  display: "swap",
});

export const metadata: Metadata = {
  title: { default: "NBA Intelligence", template: "%s · NBA Intelligence" },
  description: "NBA player performance predictions with calibrated uncertainty, built on real box scores.",
};

export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: dark)", color: "#000000" },
    { media: "(prefers-color-scheme: light)", color: "#f2f2f7" },
  ],
  viewportFit: "cover",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`dark ${geist.variable} ${geistMono.variable} ${display.variable}`} suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeScript }} />
      </head>
      <body className="min-h-dvh">
        <a
          href="#main"
          className="sr-only z-50 rounded-md bg-primary px-4 py-2 text-primary-foreground focus:not-sr-only focus:fixed focus:left-4 focus:top-3"
        >
          Skip to content
        </a>
        <Providers>
          <TopNav />
          <main id="main" className="mx-auto w-full max-w-6xl px-4 pb-28 pt-8 sm:px-6 md:pb-16 md:pt-12">
            {children}
          </main>
          <TabBar />
          <Suspense fallback={null}>
            <RouteFocus />
          </Suspense>
        </Providers>
      </body>
    </html>
  );
}
