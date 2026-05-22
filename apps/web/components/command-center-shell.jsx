"use client";

import dynamic from "next/dynamic";

const CommandCenter = dynamic(() => import("./command-center"), {
  ssr: false,
  loading: () => (
    <main className="app-shell">
      <section className="panel center-panel">
        <div className="empty-state">
          <p>Preparing Trust Operations Command...</p>
          <span>Loading live command center modules.</span>
        </div>
      </section>
    </main>
  )
});

export default function CommandCenterShell() {
  return <CommandCenter />;
}
