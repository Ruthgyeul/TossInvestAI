// /backtest {strategy} {period} — 백테스트 실행 (1Y/3Y/5Y) (docs/BIN.md)
//
// strategy/backtest.py 엔진은 Phase 5에서 구현된다(tests/test_backtest.py 참고) — 접수는 정상
// 처리되지만 완료 이벤트(backtest_complete)는 아직 "미구현" 결과를 담아 온다.
//
// deferReply()로 응답을 미뤄두고, eventSubscriber.ts가 jobId(correlation_id)가 일치하는
// backtest_complete 이벤트 수신 시 editReply()로 마무리한다 (docs/INTERNAL_API.md).
import { ChatInputCommandInteraction, SlashCommandBuilder } from "discord.js";

import { buildErrorEmbed } from "../embeds/info.js";
import { runBacktest } from "../lib/coreClient.js";
import { trackInteraction } from "../lib/interactionTracker.js";
import type { BotCommand } from "./types.js";

const data = new SlashCommandBuilder()
  .setName("backtest")
  .setDescription("백테스트 실행")
  .addStringOption((opt) => opt.setName("strategy").setDescription("전략 이름").setRequired(true))
  .addStringOption((opt) =>
    opt.setName("period").setDescription("기간").setRequired(true).addChoices(
      { name: "1Y", value: "1Y" },
      { name: "3Y", value: "3Y" },
      { name: "5Y", value: "5Y" },
    ),
  );

async function execute(interaction: ChatInputCommandInteraction): Promise<void> {
  const strategy = interaction.options.getString("strategy", true);
  const period = interaction.options.getString("period", true) as "1Y" | "3Y" | "5Y";

  await interaction.deferReply();
  try {
    const { jobId } = await runBacktest(strategy, period);
    trackInteraction(jobId, interaction);
  } catch (err) {
    await interaction.editReply({ embeds: [buildErrorEmbed("[빈] ⚠️ 백테스트 요청 실패", (err as Error).message)] });
  }
}

export const commands: BotCommand[] = [{ data, execute }];
