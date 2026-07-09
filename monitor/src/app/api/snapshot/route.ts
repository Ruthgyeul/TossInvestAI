import { NextResponse } from "next/server";
import { getMockSnapshot } from "@/lib/mock-snapshot";

// Kiosk polls this on an interval — always compute fresh, never cache.
export const dynamic = "force-dynamic";

export async function GET() {
  return NextResponse.json(getMockSnapshot());
}
