import type { Metadata } from "next";
import { Inter } from "next/font/google";
import Navbar from "@/components/navbar";
import "./globals.css";

const inter = Inter({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-inter",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Retry — Revenue Recovery Agent Console",
  description: "AI-powered revenue failure diagnosis and automated recovery workspace.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={`h-full ${inter.variable}`}>
      <body className={`${inter.className} font-sans antialiased min-h-screen flex flex-col bg-[#f8fafc] text-slate-900`}>
        <Navbar />
        <main className="flex-1 flex flex-col pt-16 bg-[#f8fafc]">
          {children}
        </main>
      </body>
    </html>
  );
}
