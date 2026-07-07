// 매수·매도 체결 Embed. 시뮬레이션 모드에는 🟡 [시뮬레이션] 뱃지가 붙는다 (docs/DISCORD.md, docs/SAFETY.md).
import { EmbedBuilder } from "discord.js";

import { applyBinBranding } from "./common.js";

export const TRADE_COLOR = { BUY: 0x00b894, SELL: 0xe17055 } as const;

export interface TradeEmbedData {
  symbol: string;
  symbolName: string;
  market: "KR" | "US";
  quantity: number;
  fillPrice: number;
  totalAmountKrw: number;
  commissionKrw: number;
  reason: string;
  decisionId: string;
  orderId: string;
  mode: "LIVE" | "SIMULATION" | "DRY_RUN";
  realizedPnlKrw?: number;
  avgPrice?: number;
  balanceChangeKrw?: number;
}

export function buildBuyEmbed(data: TradeEmbedData): EmbedBuilder {
  const isSim = data.mode === "SIMULATION";
  const embed = new EmbedBuilder()
    .setColor(TRADE_COLOR.BUY)
    .setTitle(isSim ? "🟡 [시뮬레이션] [빈] 매수 체결 (가상)" : "[빈] 매수 체결")
    .setDescription(`${data.symbolName} (${data.symbol}) · ${data.market === "KR" ? "한국장" : "미국장"}`)
    .addFields(
      { name: "수량", value: `${data.quantity}주`, inline: true },
      { name: isSim ? "가상 체결가" : "체결가", value: `${data.fillPrice.toLocaleString()}원`, inline: true },
      { name: "총금액", value: `${data.totalAmountKrw.toLocaleString()}원`, inline: true },
      { name: "수수료", value: `${data.commissionKrw.toLocaleString()}원`, inline: true },
    );

  if (isSim && data.balanceChangeKrw !== undefined) {
    embed.addFields({
      name: "가상 잔고",
      value: `${data.balanceChangeKrw >= 0 ? "+" : ""}${data.balanceChangeKrw.toLocaleString()}원 차감`,
      inline: true,
    });
  }

  embed.addFields(
    { name: "판단 이유", value: data.reason },
    { name: "Decision ID", value: data.decisionId },
    { name: "Order ID", value: data.orderId },
  );
  embed.setTimestamp();

  return applyBinBranding(embed);
}

export function buildSellEmbed(data: TradeEmbedData): EmbedBuilder {
  const isSim = data.mode === "SIMULATION";
  const pnlPct =
    data.realizedPnlKrw !== undefined && data.totalAmountKrw - data.realizedPnlKrw !== 0
      ? data.realizedPnlKrw / (data.totalAmountKrw - data.realizedPnlKrw)
      : undefined;
  const pnlValue = `${data.realizedPnlKrw?.toLocaleString() ?? "0"}원${
    pnlPct !== undefined ? ` (${pnlPct >= 0 ? "+" : ""}${(pnlPct * 100).toFixed(2)}%)` : ""
  }`;

  const embed = new EmbedBuilder()
    .setColor(TRADE_COLOR.SELL)
    .setTitle(isSim ? "🟡 [시뮬레이션] [빈] 매도 체결 (가상)" : "[빈] 매도 체결")
    .setDescription(`${data.symbolName} (${data.symbol}) · ${data.market === "KR" ? "한국장" : "미국장"}`)
    .addFields(
      { name: "수량", value: `${data.quantity}주`, inline: true },
      { name: isSim ? "가상 체결가" : "체결가", value: `${data.fillPrice.toLocaleString()}원`, inline: true },
    );

  if (data.avgPrice !== undefined) {
    embed.addFields({ name: "평균단가", value: `${data.avgPrice.toLocaleString()}원`, inline: true });
  }

  embed.addFields(
    { name: "실현손익", value: pnlValue, inline: true },
    { name: "수수료", value: `${data.commissionKrw.toLocaleString()}원`, inline: true },
  );

  if (isSim && data.balanceChangeKrw !== undefined) {
    embed.addFields({
      name: "가상 잔고",
      value: `${data.balanceChangeKrw >= 0 ? "+" : ""}${data.balanceChangeKrw.toLocaleString()}원`,
      inline: true,
    });
  }

  embed.addFields(
    { name: "판단 이유", value: data.reason },
    { name: "Decision ID", value: data.decisionId },
    { name: "Order ID", value: data.orderId },
  );
  embed.setTimestamp();

  return applyBinBranding(embed);
}
