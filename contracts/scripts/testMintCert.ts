import { ethers } from "ethers";
import * as dotenv from "dotenv";
dotenv.config();

const ENS_REGISTRY = "0x00000000000C2E074eC69A0dFb2997BA6C7d2e1e";
const PUBLIC_RESOLVER = "0x8FADE66B79cC9f707aB26799354482EB93a5B7dD";

const ENS_REGISTRY_ABI = [
    "function setSubnodeRecord(bytes32 node, bytes32 label, address owner, address resolver, uint64 ttl) external",
];

const RESOLVER_ABI = [
    "function setText(bytes32 node, string key, string value) external",
    "function text(bytes32 node, string key) external view returns (string)",
];

function namehash(name: string): string {
    let node = "0x0000000000000000000000000000000000000000000000000000000000000000";
    if (name === "") return node;
    const labels = name.split(".").reverse();
    for (const label of labels) {
        const labelHash = ethers.keccak256(ethers.toUtf8Bytes(label));
        node = ethers.keccak256(ethers.concat([node, labelHash]));
    }
    return node;
}

async function main() {
    const provider = new ethers.JsonRpcProvider(
        `https://eth-sepolia.g.alchemy.com/v2/${process.env.ALCHEMY_API_KEY}`
    );
    const wallet = new ethers.Wallet(process.env.PRIVATE_KEY!, provider);

    const registry = new ethers.Contract(ENS_REGISTRY, ENS_REGISTRY_ABI, wallet);
    const resolver = new ethers.Contract(PUBLIC_RESOLVER, RESOLVER_ABI, wallet);

    const certifiedNode = namehash("certified.keeper-memory.eth");
    const label = "vault-0x7f2e";
    const labelHash = ethers.keccak256(ethers.toUtf8Bytes(label));
    const subnameNode = namehash(`${label}.certified.keeper-memory.eth`);

    console.log("Minting vault-0x7f2e.certified.keeper-memory.eth...");
    const tx1 = await registry.setSubnodeRecord(
        certifiedNode,
        labelHash,
        wallet.address,
        PUBLIC_RESOLVER,
        0
    );
    await tx1.wait();
    console.log("✓ Subname minted — tx:", tx1.hash);

    console.log("\nSetting text records...");
    const records = [
        ["verdict", "CERTIFIED"],
        ["high_count", "0"],
        ["medium_count", "2"],
        ["audit_date", "2026-04-26"],
        ["tx_proof", "0x180869dd939fdecd1eaf8f39968ae76a650848a9fe69fa50bcc425904e43758e"],
        ["report_hash", "0xa3f8c2d1e4b5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0"],
    ];

    for (const [key, value] of records) {
        const tx = await resolver.setText(subnameNode, key, value);
        await tx.wait();
        console.log(`✓ ${key} = ${value}`);
    }

    console.log("\nVerifying text records...");
    for (const [key] of records) {
        const value = await resolver.text(subnameNode, key);
        console.log(`  ${key}: ${value}`);
    }

    console.log("\n✓ Test complete");
    console.log(`Subname: ${label}.certified.keeper-memory.eth`);
    console.log(`Node: ${subnameNode}`);
}

main().catch(console.error);