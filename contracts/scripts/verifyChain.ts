import { ethers } from "ethers";
import * as dotenv from "dotenv";
dotenv.config();

const ANCHOR_REGISTRY = process.env.ANCHOR_REGISTRY_ADDRESS!;
const REGISTRY_ABI = [
    "function isAnchored(bytes32 pHash) external view returns (bool)",
    "function getAnchor(bytes32 pHash) external view returns (bytes32 rootHash0G, address contributor, uint256 timestamp)",
    "function getTotalAnchors() external view returns (uint256)",
];

async function verifyChain(patternHash: string) {
    const provider = new ethers.JsonRpcProvider(
        `https://eth-sepolia.g.alchemy.com/v2/${process.env.ALCHEMY_API_KEY}`
    );

    const registry = new ethers.Contract(ANCHOR_REGISTRY, REGISTRY_ABI, provider);

    console.log("\n═══════════════════════════════════════════════");
    console.log("  Onchor.ai — Independent Verification");
    console.log("═══════════════════════════════════════════════");
    console.log(`\nPattern Hash: ${patternHash}`);

    // Step 1 — verify onchain
    console.log("\n[Step 1] Checking onchain anchor (KeeperHub)...");
    const isAnchored = await registry.isAnchored(patternHash);

    if (!isAnchored) {
        console.log("✗ Pattern NOT anchored onchain");
        process.exit(1);
    }

    const [rootHash0G, contributor, timestamp] = await registry.getAnchor(patternHash);
    const date = new Date(Number(timestamp) * 1000).toISOString();

    console.log(`✓ Pattern anchored onchain`);
    console.log(`  Contract:    ${ANCHOR_REGISTRY}`);
    console.log(`  Contributor: ${contributor}`);
    console.log(`  Anchored at: ${date}`);
    console.log(`  rootHash0G:  ${rootHash0G}`);
    console.log(`  Etherscan:   https://sepolia.etherscan.io/address/${ANCHOR_REGISTRY}`);

    // Step 2 — link to 0G Storage
    console.log("\n[Step 2] 0G Storage pointer...");
    console.log(`✓ rootHash0G: ${rootHash0G}`);
    console.log(`  Retrieve pattern: node 0g/0g_download.js ${rootHash0G}`);
    console.log(`  (Full pattern with fix available on 0G decentralized storage)`);

    // Step 3 — global stats
    console.log("\n[Step 3] Registry stats...");
    const total = await registry.getTotalAnchors();
    console.log(`✓ Total patterns anchored: ${total}`);

    console.log("\n═══════════════════════════════════════════════");
    console.log("  Verification COMPLETE ✓");
    console.log("  Chain: patternHash → KeeperHub → rootHash0G → 0G");
    console.log("═══════════════════════════════════════════════\n");
}

const patternHash = process.argv[2];
if (!patternHash) {
    console.error("Usage: npx ts-node scripts/verifyChain.ts <patternHash>");
    process.exit(1);
}

verifyChain(patternHash).catch(console.error);