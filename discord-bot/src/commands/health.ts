// /health — 라즈베리파이 상태 (CPU·메모리·온도·디스크) (docs/LOGGING.md)
import { ChatInputCommandInteraction, SlashCommandBuilder } from "discord.js";

import { buildErrorEmbed, buildInfoEmbed } from "../embeds/info.js";
import { getHealth } from "../lib/coreClient.js";
import type { BotCommand } from "./types.js";

const data = new SlashCommandBuilder().setName("health").setDescription("라즈베리파이 상태 조회");

async function execute(interaction: ChatInputCommandInteraction): Promise<void> {
  try {
    const health = await getHealth();
    const lines = [
      `CPU     ${health.cpuPct.toFixed(1)}%`,
      `메모리  ${health.memoryPct.toFixed(1)}%`,
      `디스크  ${health.diskPct.toFixed(1)}%`,
      `온도    ${health.tempC.toFixed(1)}°C`,
      `토스 API  ${health.tossApiReachable ? "정상" : "응답 없음"}`,
    ];
    const embed = buildInfoEmbed("[빈] 라즈베리파이 상태", lines.join("\n"));
    await interaction.reply({ embeds: [embed] });
  } catch (err) {
    const embed = buildErrorEmbed("[빈] ⚠️ 상태 조회 실패", (err as Error).message);
    await interaction.reply({ embeds: [embed], ephemeral: true });
  }
}

export const commands: BotCommand[] = [{ data, execute }];
