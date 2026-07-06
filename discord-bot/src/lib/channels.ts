// 채널 조회 + 없으면 생성 (docs/DISCORD.md "채널 삭제는 불가능하다. 봇은 필요 시
// 카테고리 하위 채널 생성만 가능", CLAUDE.md 규칙 8).
//
// 설정된 채널 ID(config.channels.*)가 유효하면 그대로 쓴다. ID가 비어있거나 채널이
// 삭제/이전되어 fetch가 실패하면 이름으로 길드에서 찾고, 그마저 없으면 새로 생성한다.
import { ChannelType, Client, Guild, TextChannel } from "discord.js";

import { config } from "../config.js";

const CATEGORY_NAME = "빈(Bin) 트레이딩 봇";

const CHANNEL_NAMES: Record<keyof typeof config.channels, string> = {
  status: "status",
  analyze: "stock-analyze",
  buy: "stock-buy",
  sell: "stock-sell",
  system: "stock-system",
  error: "stock-error",
  news: "stock-news",
  log: "stock-log",
};

async function getOrCreateCategory(guild: Guild) {
  const existing = guild.channels.cache.find(
    (c) => c.type === ChannelType.GuildCategory && c.name === CATEGORY_NAME,
  );
  if (existing) return existing;
  return guild.channels.create({ name: CATEGORY_NAME, type: ChannelType.GuildCategory });
}

async function getOrCreateChannel(
  client: Client,
  channelId: string,
  channelName: string,
): Promise<TextChannel | null> {
  if (channelId) {
    const channel = await client.channels.fetch(channelId).catch(() => null);
    if (channel instanceof TextChannel) return channel;
  }

  const guild = await client.guilds.fetch(config.guildId).catch(() => null);
  if (!guild) return null;

  const byName = guild.channels.cache.find(
    (c) => c.type === ChannelType.GuildText && c.name === channelName,
  );
  if (byName instanceof TextChannel) return byName;

  const category = await getOrCreateCategory(guild);
  return guild.channels.create({
    name: channelName,
    type: ChannelType.GuildText,
    parent: category.id,
  });
}

export async function getChannel(
  client: Client,
  key: keyof typeof config.channels,
): Promise<TextChannel | null> {
  return getOrCreateChannel(client, config.channels[key], CHANNEL_NAMES[key]);
}
