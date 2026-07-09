import type { SystemHealthSnapshot } from "@/lib/types";
import styles from "./Dashboard.module.css";

const STATUS_DOT_CLASS = {
  ok: styles.statusOk,
  warn: styles.statusWarn,
  error: styles.statusError,
} as const;

const LOG_LEVEL_CLASS = {
  INFO: styles.logLevelInfo,
  WARN: styles.logLevelWarn,
  ERROR: styles.logLevelError,
} as const;

export function SystemHealthPanel({ data }: { data: SystemHealthSnapshot }) {
  return (
    <div className={`${styles.card} ${styles.systemHealthCard}`}>
      <div className={styles.sectionHeader}>
        <div className={styles.sectionTitle}>시스템 헬스</div>
        <div className={styles.sectionMeta} style={{ fontSize: 9 }}>
          에러 {data.errorCountToday}건 · HB {data.lastHeartbeatSecondsAgo}초 전
        </div>
      </div>

      <div className={styles.serviceList}>
        {data.services.map((svc) => (
          <div className={styles.serviceRow} key={svc.name}>
            <span className={styles.serviceName}>
              <span className={`${styles.statusDot} ${STATUS_DOT_CLASS[svc.status]}`} />
              {svc.name}
            </span>
            <span className={styles.serviceDetail}>{svc.detail}</span>
          </div>
        ))}
      </div>

      {data.logs.map((log, i) => (
        <div className={styles.logRow} key={i}>
          <span className={styles.logTime}>{log.time}</span>
          <span className={`${styles.logLevel} ${LOG_LEVEL_CLASS[log.level]}`}>{log.level}</span>
          <span className={styles.logMessage}>{log.message}</span>
        </div>
      ))}

      <div className={styles.subsectionHeader}>
        <div className={styles.subsectionTitle}>Safety Gate 거부</div>
        <div className={styles.safetyGateRate}>
          {data.safetyGate.passRateLabel} · 금일 {data.safetyGate.rejectionsToday}건
        </div>
      </div>
      {data.safetyGate.rejections.map((rej, i) => (
        <div className={styles.safetyRow} key={i}>
          <span className={styles.safetyTime}>{rej.time}</span>
          <span className={styles.safetyText}>{rej.message}</span>
        </div>
      ))}

      <div className={styles.selfAssessRow}>
        <span className={styles.subsectionTitle}>자기평가</span>
        <span className={styles.safetyText}>
          {data.selfAssessment.time} · {data.selfAssessment.summary}
        </span>
      </div>
    </div>
  );
}
