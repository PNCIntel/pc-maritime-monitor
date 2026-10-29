import type { Metadata } from 'next';
import './style.css';
export const metadata: Metadata = { title: 'Below the Waterline | Power & Corridors', description: 'Evidence-led maritime due diligence and vessel intelligence' };
export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) { return <html lang="en"><body>{children}</body></html>; }
