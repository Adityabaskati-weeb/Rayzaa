"use client";

import dynamic from "next/dynamic";

const PayEasyDashboard = dynamic(() => import("./payeasy-dashboard"), {
  ssr: false,
  loading: () => (
    <main className="portal-shell">
      <section className="panel payeasy-shell">
        <div className="empty-state">
          <p>Preparing PayEasy checkout surface...</p>
          <span>Loading live payment orchestration and Rayzaa handoff.</span>
        </div>
      </section>
    </main>
  )
});

export default function PayEasyDashboardShell() {
  return <PayEasyDashboard />;
}
