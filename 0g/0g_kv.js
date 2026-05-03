import path from "path";
import { fileURLToPath } from "url";
import fs from "fs";
import dotenv from "dotenv";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
dotenv.config({ path: path.join(__dirname, ".env") });

const { Indexer, MemData } = await import("@0gfoundation/0g-ts-sdk");
const { ethers } = await import("ethers");

const EVM_RPC = process.env.OG_EVM_RPC || "https://evmrpc-testnet.0g.ai";
const INDEXER_RPC = process.env.OG_INDEXER_RPC || "https://indexer-storage-testnet-turbo.0g.ai";
const MANIFEST_KEY = "onchor-manifest-v1";
const MANIFEST_CACHE = path.join(__dirname, ".manifest_root_hash");

function emit(obj) { process.stdout.write(JSON.stringify(obj) + "\n"); }
function die(msg) { emit({ ok: false, error: msg }); process.exit(1); }

const pk = process.env.OG_PRIVATE_KEY;
if (!pk) die("OG_PRIVATE_KEY required");

const provider = new ethers.JsonRpcProvider(EVM_RPC);
const signer = new ethers.Wallet(pk.startsWith("0x") ? pk : "0x" + pk, provider);
const indexer = new Indexer(INDEXER_RPC);

const cmd = process.argv[2];
const key = process.argv[3];
const val = process.argv[4];

if (cmd === "set") {
  if (!key || !val) die("usage: set <key> <json>");
  let parsed;
  try { parsed = JSON.parse(val); } catch(e) { die("invalid JSON: " + e.message); }
  const payload = JSON.stringify({ key: key, data: parsed });
  const bytes = new TextEncoder().encode(payload);
  const mem = new MemData(bytes);
  const [result, err] = await indexer.upload(mem, EVM_RPC, signer, { finalityRequired: false });
  if (err != null) die(err.message || String(err));
  const rh = result && result.rootHash;
  if (!rh) die("upload returned no rootHash");
  if (key === MANIFEST_KEY) {
    fs.writeFileSync(MANIFEST_CACHE, rh, "utf-8");
  }
  emit({ ok: true, tx: (result.txHash || ""), rootHash: rh, key: key });

} else if (cmd === "get") {
  if (!key) die("usage: get <rootHash>");
  const [blob, err] = await indexer.downloadSingleToBlob(key, {});
  if (err != null) die(err.message || String(err));
  const text = new TextDecoder().decode(await blob.arrayBuffer());
  const parsed = JSON.parse(text);
  emit({ ok: true, data: parsed.data || parsed });

} else if (cmd === "get-manifest") {
  if (!fs.existsSync(MANIFEST_CACHE)) {
    emit({ ok: true, data: { entries: [] } });
    process.exit(0);
  }
  const rh = fs.readFileSync(MANIFEST_CACHE, "utf-8").trim();
  if (!rh) { emit({ ok: true, data: { entries: [] } }); process.exit(0); }
  const [blob, err] = await indexer.downloadSingleToBlob(rh, {});
  if (err != null) die(err.message || String(err));
  const text = new TextDecoder().decode(await blob.arrayBuffer());
  const parsed = JSON.parse(text);
  emit({ ok: true, data: parsed.data || parsed, rootHash: rh });

} else {
  die("usage: node 0g_kv.js <set|get|get-manifest> [key] [json]");
}