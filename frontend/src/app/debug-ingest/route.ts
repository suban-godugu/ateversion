import { appendFile, mkdir } from "fs/promises";
import { NextRequest, NextResponse } from "next/server";
import path from "path";

/**
 * Local debug ingest fallback — writes NDJSON for session 4c992b.
 * Not used in production logic.
 */
export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const dir = path.join(process.cwd(), "..", ".cursor");
    await mkdir(dir, { recursive: true });
    const file = path.join(dir, "debug-4c992b.log");
    await appendFile(file, `${JSON.stringify({ ...body, sessionId: "4c992b", via: "debug-ingest" })}\n`);
    return NextResponse.json({ ok: true });
  } catch (e) {
    return NextResponse.json({ ok: false, error: String(e) }, { status: 500 });
  }
}
