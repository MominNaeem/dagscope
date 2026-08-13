import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: '◈ dagscope',
  description: 'Airflow DAG lineage and change impact analysis',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="h-screen overflow-hidden bg-canvas text-text">
        {children}
      </body>
    </html>
  );
}
