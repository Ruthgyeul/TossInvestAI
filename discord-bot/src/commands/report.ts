// /report, /report kr|us — 즉시 리포트 생성·발송 (docs/REPORT.md)
//
// core는 202 {jobId}로 즉시 응답하고, 완료되면 report_ready pub/sub 이벤트가 jobId를
// correlation_id로 실어 발행된다 (docs/INTERNAL_API.md "동기 vs 지연 응답"). deferReply()로
// 응답을 미뤄두고, eventSubscriber.ts가 완료 이벤트 수신 시 editReply()로 마무리한다.
import { ChatInputCommandInteraction, SlashCommandBuilder } from "discord.js";

import { buildErrorEmbed } from "../embeds/info.js";
import { generateReport } from "../lib/coreClient.js";
import { trackInteraction } from "../lib/interactionTracker.js";
import type { BotCommand } from "./types.js";

const data = new SlashCommandBuilder()
  .setName("report")
  .setDescription("즉시 통합 리포트 생성·발송")
  .addStringOption((opt) =>
    opt.setName("market").setDescription("시장별 리포트").addChoices(
      { name: "KR", value: "KR" },
      { name: "US", value: "US" },
    ),
  );

async function execute(interaction: ChatInputCommandInteraction): Promise<void> {
  const market = (interaction.options.getString("market") as "KR" | "US" | null) ?? "ALL";
  await interaction.deferReply();
  try {
    const { jobId } = await generateReport(market);
    trackInteraction(jobId, interaction);
  } catch (err) {
    await interaction.editReply({ embeds: [buildErrorEmbed("[빈] ⚠️ 리포트 요청 실패", (err as Error).message)] });
  }
}

export const commands: BotCommand[] = [{ data, execute }];
