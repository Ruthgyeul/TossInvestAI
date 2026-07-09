import { KioskStage } from "@/components/KioskStage";
import { MonitorDashboard } from "@/components/MonitorDashboard";
import { getMockSnapshot } from "@/lib/mock-snapshot";

export default function Home() {
  return (
    <KioskStage>
      <MonitorDashboard initialSnapshot={getMockSnapshot()} />
    </KioskStage>
  );
}
