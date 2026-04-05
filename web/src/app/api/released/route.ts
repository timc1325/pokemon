import { NextResponse } from "next/server";

const RELEASED_API_URL =
  "https://pogoapi.net/api/v1/released_pokemon.json";

export async function GET() {
  try {
    const res = await fetch(RELEASED_API_URL, {
      headers: { "User-Agent": "Mozilla/5.0" },
      next: { revalidate: 3600 },
    });
    const data = await res.json();
    const ids = Object.keys(data).map(Number);
    return NextResponse.json(ids);
  } catch {
    return NextResponse.json([], { status: 500 });
  }
}
