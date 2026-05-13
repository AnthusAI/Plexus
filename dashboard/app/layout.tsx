import "./globals.css";
import { Inter, Jersey_20 } from "next/font/google";

const inter = Inter({ subsets: ["latin"] });
const jersey20 = Jersey_20({
  subsets: ["latin"],
  weight: "400",
  variable: "--font-jersey-20",
  adjustFontFallback: false,
});

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html suppressHydrationWarning>
      <body className={`${inter.className} ${jersey20.variable}`}>
        {children}
      </body>
    </html>
  );
}
