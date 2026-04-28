/**
 * rootHash → JSON sur stdout: {"ok":true,"data":{...}}
 */
import path from "path";
import { fileURLToPath } from "url";
import dotenv from "dotenv";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
dotenv.config({ path: path.join(__dirname, ".env") });

const log = (...a) => console.error("[0g_download]", ...a);
console.log = (...a) => log(...a);

const { Indexer } = await import("@0gfoundation/0g-ts-sdk");

const DEFAULT_INDEXER = "https://indexer-storage-testnet-turbo.0g.ai";

function emit(obj) {
  process.stdout.write(`${JSON.stringify(obj)}\n`);
}

function die(msg, code = 1) {
  emit({ ok: false, error: msg });
  process.exit(code);
}

const rootHash = process.argv[2];
if (!rootHash) die("usage: node 0g_download.js <rootHash>");

const indRpc = process.env.OG_INDEXER_RPC || DEFAULT_INDEXER;
const indexer = new Indexer(indRpc);

const [blob, err] = await indexer.downloadSingleToBlob(rootHash, {});
if (err != null) die(err.message || String(err));

const text = new TextDecoder().decode(await blob.arrayBuffer());
let data;
try {
  data = JSON.parse(text);
} catch (e) {
  die(`downloaded bytes are not valid JSON: ${e.message}`);
}

emit({ ok: true, data });
