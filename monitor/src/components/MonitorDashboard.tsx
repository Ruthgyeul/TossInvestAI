"use client";

import { useEffect, useState } from "react";
import type { MonitorSnapshot } from "@/lib/types";
import styles from "./Dashboard.module.css";
import { Header } from "./Header";
import { SubStrip } from "./SubStrip";
import { TotalAssetsCard } from "./TotalAssetsCard";
import { PnlChart } from "./PnlChart";
import { SystemHealthPanel } from "./SystemHealthPanel";
import { PositionsPanel } from "./PositionsPanel";
import { AiDecisionsPanel } from "./AiDecisionsPanel";
import { NewsPanel } from "./NewsPanel";
import { EventCalendarPanel } from "./EventCalendarPanel";

const REFRESH_INTERVAL_MS = 30_000;

export function MonitorDashboard({ initialSnapshot }: { initialSnapshot: MonitorSnapshot }) {
  const [snapshot, setSnapshot] = useState(initialSnapshot);

  useEffect(() => {
    let cancelled = false;

    async function refresh() {
      try {
        const res = await fetch("/api/snapshot", { cache: "no-store" });
        if (!res.ok) return;
        const data: MonitorSnapshot = await res.json();
        if (!cancelled) setSnapshot(data);
      } catch {
        // Kiosk stays on the last known-good snapshot rather than blanking out.
      }
    }

    const id = setInterval(refresh, REFRESH_INTERVAL_MS);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, []);

  return (
    <div className={styles.dashboard}>
      <Header data={snapshot.header} />
      <SubStrip data={snapshot.subStrip} />

      <div className={styles.bodyGrid}>
        <TotalAssetsCard data={snapshot.totalAssets} />
        <PnlChart data={snapshot.chart} />
        <SystemHealthPanel data={snapshot.systemHealth} />
        <PositionsPanel positions={snapshot.positions} />
        <AiDecisionsPanel
          decisions={snapshot.aiDecisions}
          countToday={snapshot.aiDecisionsCountToday}
        />
      </div>

      <div className={styles.bottomStrip}>
        <NewsPanel news={snapshot.news} />
        <EventCalendarPanel events={snapshot.events} />
      </div>
    </div>
  );
}
