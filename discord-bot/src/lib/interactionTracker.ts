// `/report`·`/backtest`의 지연 응답(deferReply → editReply) 추적 (docs/INTERNAL_API.md "동기 vs 지연 응답").
//
// core가 202 {jobId}로 접수만 응답하고, 완료되면 report_ready/backtest_complete 이벤트를
// jobId를 correlation_id로 실어 발행한다. 이 맵은 jobId → 원본 인터랙션을 기억해두었다가
// 완료 이벤트 수신 시 editReply()로 마무리할 수 있게 한다.
import { ChatInputCommandInteraction } from "discord.js";

const pending = new Map<string, ChatInputCommandInteraction>();

export function trackInteraction(jobId: string, interaction: ChatInputCommandInteraction): void {
  pending.set(jobId, interaction);
}

export function resolveInteraction(jobId: string | null): ChatInputCommandInteraction | undefined {
  if (!jobId) return undefined;
  const interaction = pending.get(jobId);
  if (interaction) pending.delete(jobId);
  return interaction;
}
