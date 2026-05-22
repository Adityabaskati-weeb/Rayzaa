import CommandCenterShell from "../../components/command-center-shell";

export const dynamic = "force-dynamic";

export const metadata = {
  title: "Rayzaa | Trust Operations Command",
  description: "Analyst-facing operational trust intelligence command center"
};

export default function RayzaaPage() {
  return <CommandCenterShell />;
}
