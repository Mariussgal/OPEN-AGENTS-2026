import { ethers, namehash } from "ethers";
import * as dotenv from "dotenv";
dotenv.config();

/** Parent pour les certificats d’audit (sous-domaines type contract-abcd12.<parent>). */
const PARENT_CERT = process.env.ENS_PARENT_CERT || "certified.onchor-ai.eth";
/** Parent pour les profils auditeurs. */
const PARENT_AUDITORS = process.env.ENS_PARENT_AUDITORS || "auditors.onchor-ai.eth";

const ENS_REGISTRY = "0x00000000000C2E074eC69A0dFb2997BA6C7d2e1e";
const PUBLIC_RESOLVER = "0x8FADE66B79cC9f707aB26799354482EB93a5B7dD";

const REGISTRY_ABI = [
    "function setSubnodeRecord(bytes32 node, bytes32 label, address owner, address resolver, uint64 ttl) external",
];
const RESOLVER_ABI = [
    "function setText(bytes32 node, string key, string value) external",
    "function text(bytes32 node, string key) external view returns (string)",
];

async function getContracts() {
    const provider = new ethers.JsonRpcProvider(
        `https://eth-sepolia.g.alchemy.com/v2/${process.env.ALCHEMY_API_KEY}`
    );
    const wallet = new ethers.Wallet(process.env.PRIVATE_KEY!, provider);
    const registry = new ethers.Contract(ENS_REGISTRY, REGISTRY_ABI, wallet);
    const resolver = new ethers.Contract(PUBLIC_RESOLVER, RESOLVER_ABI, wallet);
    return { wallet, registry, resolver };
}

async function mintCert(
    contractAddress: string,
    verdict: string,
    highCount: string,
    mediumCount: string,
    txProof: string,
    reportHash: string,
    auditDate: string
) {
    const { wallet, registry, resolver } = await getContracts();

    const label = `contract-${contractAddress.slice(2, 8).toLowerCase()}`;
    const parentNode = namehash(PARENT_CERT);
    const labelHash = ethers.keccak256(ethers.toUtf8Bytes(label));
    const fullName = `${label}.${PARENT_CERT}`;
    const subnameNode = namehash(fullName);

    console.log(`Minting ${fullName}...`);
    const tx1 = await registry.setSubnodeRecord(
        parentNode, labelHash, wallet.address, PUBLIC_RESOLVER, 0
    );
    await tx1.wait();
    console.log(`✓ Subname minted — tx: ${tx1.hash}`);

    const records = [
        ["verdict", verdict],
        ["high_count", highCount],
        ["medium_count", mediumCount],
        ["audit_date", auditDate],
        ["tx_proof", txProof],
        ["report_hash", reportHash],
    ];

    for (const [key, value] of records) {
        const tx = await resolver.setText(subnameNode, key, value);
        await tx.wait();
        console.log(`✓ ${key} = ${value}`);
    }

    console.log(`\nENS_SUBNAME=${fullName}`);
    console.log(`ENS_NODE=${subnameNode}`);
    return fullName;
}

async function mintAuditor(
    walletAddress: string,
    contributions: string,
    reputationScore: string,
    confirmedFindings: string
) {
    const { wallet, registry, resolver } = await getContracts();

    const label = walletAddress.slice(2, 10).toLowerCase();
    const parentNode = namehash(PARENT_AUDITORS);
    const labelHash = ethers.keccak256(ethers.toUtf8Bytes(label));
    const fullName = `${label}.${PARENT_AUDITORS}`;
    const subnameNode = namehash(fullName);

    console.log(`Minting ${fullName}...`);
    const tx1 = await registry.setSubnodeRecord(
        parentNode, labelHash, wallet.address, PUBLIC_RESOLVER, 0
    );
    await tx1.wait();
    console.log(`✓ Subname minted — tx: ${tx1.hash}`);

    const records = [
        ["contributions", contributions],
        ["reputation_score", reputationScore],
        ["confirmed_findings", confirmedFindings],
    ];

    for (const [key, value] of records) {
        const tx = await resolver.setText(subnameNode, key, value);
        await tx.wait();
        console.log(`✓ ${key} = ${value}`);
    }

    console.log(`\nENS_SUBNAME=${fullName}`);
    return fullName;
}

// CLI interface — called from Python via subprocess
const [, , command, ...args] = process.argv;

if (command === "mintCert") {
    const [addr, verdict, high, medium, txProof, reportHash, date] = args;
    mintCert(addr, verdict, high, medium, txProof, reportHash, date)
        .catch(console.error);
} else if (command === "mintAuditor") {
    const [addr, contributions, score, confirmed] = args;
    mintAuditor(addr, contributions, score, confirmed)
        .catch(console.error);
} else {
    console.error("Usage: npx ts-node scripts/ensManager.ts mintCert <address> <verdict> <high> <medium> <txProof> <reportHash> <date>");
    console.error("       npx ts-node scripts/ensManager.ts mintAuditor <address> <contributions> <score> <confirmed>");
    process.exit(1);
}
