// /resume — 자동매매 재개, 개발자 확인 필요 (docs/SAFETY.md)
import { ChatInputCommandInteraction, SlashCommandBuilder } from "discord.js";

import { buildErrorEmbed, buildInfoEmbed } from "../embeds/info.js";
import { resumeTrading } from "../lib/coreClient.js";
import type { BotCommand } from "./types.js";

const data = new SlashCommandBuilder().setName("resume").setDescription("자동매매 재개");

async function execute(interaction: ChatInputCommandInteraction): Promise<void> {
  try {
    const result = await resumeTrading();
    const embed = result.success
      ? buildInfoEmbed("[빈] ▶️ 자동매매 재개", "자동매매를 재개했습니다.")
      : buildErrorEmbed("[빈] ⚠️ 재개 실패", "알 수 없는 사유");
    await interaction.reply({ embeds: [embed] });
  } catch (err) {
    const embed = buildErrorEmbed("[빈] ⚠️ 재개 요청 실패", (err as Error).message);
    await interaction.reply({ embeds: [embed], ephemeral: true });
  }
}

export const commands: BotCommand[] = [{ data, execute }];
