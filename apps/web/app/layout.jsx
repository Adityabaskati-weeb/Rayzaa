import "./globals.css";

export const metadata = {
  title: "Rayzaa | Trust Operations Command",
  description: "Operational trust intelligence command center"
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link
          href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Serif:wght@400;500;600&display=swap"
          rel="stylesheet"
        />
      </head>
      <body>
        {children}
        <footer className="global-footer">
          <div className="global-footer-inner">
            <span>Rayzaa trust intelligence workflow</span>
            <div className="global-footer-links">
              <span>PayEasy checkout</span>
              <span>Replay chronology</span>
              <span>System status</span>
            </div>
          </div>
        </footer>
      </body>
    </html>
  );
}
