import PayEasyDashboardShell from "../../components/payeasy-dashboard-shell";

export const dynamic = "force-dynamic";

export const metadata = {
  title: "PayEasy | Live Checkout Surface",
  description: "Customer-facing checkout surface wired into Rayzaa"
};

export default function PayEasyPage() {
  return <PayEasyDashboardShell />;
}
