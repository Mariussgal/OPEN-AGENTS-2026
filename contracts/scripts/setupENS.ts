import { ethers } from "ethers";
import * as dotenv from "dotenv";
dotenv.config();

const ENS_REGISTRY = "0x00000000000C2E074eC69A0dFb2997BA6C7d2e1e";
const PUBLIC_RESOLVER = "0x8FADE66B79cC9f707aB26799354482EB93a5B7dD";
const NAME_WRAPPER = "0x0635513f179D50A207757E05759CbD106d7dFbe8";

const ENS_REGISTRY_ABI = [
    "function setSubnodeRecord(bytes32 node, bytes32 label, address owner, address resolver, uint64 ttl) external",
    "function owner(bytes32 node) external view returns (address)",
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
    console.log("Setting up ENS subnames from:", wallet.address);

    const registry = new ethers.Contract(ENS_REGISTRY, ENS_REGISTRY_ABI, wallet);
    const nameWrapper = new ethers.Contract(
        NAME_WRAPPER,
        ["function isWrapped(bytes32 node) external view returns (bool)"],
        provider
    );

    const wrapped = await nameWrapper.isWrapped(namehash("onchor-ai.eth"));
    console.log("onchor-ai.eth wrapped:", wrapped);

    const parentNode = namehash("Onchor-ai.eth");

    // Verify you are owner
    const owner = await registry.owner(parentNode);
    console.log("Onchor-ai.eth owner:", owner);

    const subnames = ["certified", "auditors"];

    for (const label of subnames) {
        console.log(`\nMinting ${label}.Onchor-ai.eth...`);
        const labelHash = ethers.keccak256(ethers.toUtf8Bytes(label));
        const tx = await registry.setSubnodeRecord(
            parentNode,
            labelHash,
            wallet.address,
            PUBLIC_RESOLVER,
            0
        );
        await tx.wait();
        console.log(`✓ ${label}.Onchor-ai.eth — tx: ${tx.hash}`);
        console.log(`  Node: ${namehash(`${label}.Onchor-ai.eth`)}`);
    }

    console.log("\n✓ ENS setup complete");
}

main().catch(console.error);