import { NextResponse } from "next/server";

const SHINY_RATES_URL = "https://shinyrates.com/data/rate";

function parseRate(rateText: string): number {
  const normalized = rateText.trim().toLowerCase().replace(/\s/g, "").replace(/,/g, "");
  const fracMatch = normalized.match(/^(\d+(?:\.\d+)?)\/(\d+(?:\.\d+)?)$/);
  if (fracMatch) {
    const den = parseFloat(fracMatch[2]);
    return den ? parseFloat(fracMatch[1]) / den : 0;
  }
  const pctMatch = normalized.match(/^(\d+(?:\.\d+)?)%$/);
  if (pctMatch) return parseFloat(pctMatch[1]) / 100;
  return 0;
}

export async function GET() {
  try {
    const res = await fetch(SHINY_RATES_URL, {
      headers: {
        "User-Agent": "Mozilla/5.0",
        Accept: "application/json",
      },
      next: { revalidate: 600 },
    });
    const data: Array<{ id: string; rate: string; total: string }> =
      await res.json();

    const rates = data.map((d) => ({
      pokemonId: parseInt(d.id, 10),
      rate: d.rate,
      rateValue: parseRate(d.rate),
      sampleSize: parseInt(d.total.replace(/,/g, ""), 10),
    }));

    return NextResponse.json(rates);
  } catch {
    return NextResponse.json([], { status: 500 });
  }
}
