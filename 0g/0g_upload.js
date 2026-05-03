/**
 * JSON (stdin or file) -> upload to 0G Storage -> stdout: {"ok":true,"rootHash":"...","txHash":"..."}
 * --merkle-only: Merkle root via MemData, without transaction.
 */
import path from "path";
import fs from "fs";
import { fileURLToPath } from "url";
import dotenv from "dotenv";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
dotenv.config({ path: path.join(__dirname, ".env") });

const log = (...a) => console.error("[0g_upload]", ...a);
console.log = (...a) => log(...a);

const { Indexer, MemData } = await import("@0gfoundation/0g-ts-sdk");
const { ethers } = await import("ethers");

const DEFAULT_EVM = "https://evmrpc-testnet.0g.ai";
const DEFAULT_INDEXER = "https://indexer-storage-testnet-turbo.0g.ai";

function emit(obj) {
  process.stdout.write(`${JSON.stringify(obj)}\n`);
}

function die(msg, code = 1) {
  emit({ ok: false, error: msg });
  process.exit(code);
}

async function readPayload(argv) {
  const merkleOnly = argv.includes("--merkle-only");
  const files = argv.filter((a) => !a.startsWith("-"));
  if (files.length > 0) {
    const p = files[0];
    if (!fs.existsSync(p)) die(`file not found: ${p}`);
    return { raw: fs.readFileSync(p, "utf8"), merkleOnly };
  }
  const chunks = [];
  for await (const c of process.stdin) chunks.push(c);
  const raw = Buffer.concat(chunks).toString("utf8").trim();
  if (!raw) die("empty stdin: pipe JSON or pass a file path");
  return { raw, merkleOnly };
}

function parseJson(raw) {
  try {
    JSON.parse(raw);
  } catch (e) {
    die(`invalid JSON: ${e.message}`);
  }
  return raw;
}

const argv = process.argv.slice(2);
const { raw, merkleOnly } = await readPayload(argv);
const jsonStr = parseJson(raw);
const bytes = new TextEncoder().encode(jsonStr);
const mem = new MemData(bytes);

if (merkleOnly) {
  const [tree, err] = await mem.merkleTree();
  if (err != null || !tree) die(err?.message ?? "merkleTree failed");
  const rh = tree.rootHash();
  if (!rh) die("empty root hash");
  emit({ ok: true, rootHash: rh, merkleOnly: true });
  process.exit(0);
}

const pk = process.env.OG_PRIVATE_KEY;
if (!pk) die("OG_PRIVATE_KEY is required for upload (set in 0g/.env or export), or use --merkle-only");

const evmRpc = process.env.OG_EVM_RPC || DEFAULT_EVM;
const indRpc = process.env.OG_INDEXER_RPC || DEFAULT_INDEXER;
const key = pk.startsWith("0x") ? pk : `0x${pk}`;

let signer;
try {
  signer = new ethers.Wallet(key, new ethers.JsonRpcProvider(evmRpc));
} catch (e) {
  die(`wallet: ${e.message}`);
}

const indexer = new Indexer(indRpc);
const [result, err] = await indexer.upload(mem, evmRpc, signer, {
  finalityRequired: false,
});

if (err != null) die(err.message || String(err));

const rootHash = result.rootHash;
const txHash = result.txHash;
if (!rootHash) die("upload returned no rootHash");

emit({ ok: true, rootHash, txHash: txHash || "" });
