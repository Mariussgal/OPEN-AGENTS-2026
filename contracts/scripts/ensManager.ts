// contracts/scripts/ensManager.ts

import { ethers, namehash } from "ethers";
import * as dotenv from "dotenv";
dotenv.config();

const PARENT_CERT     = process.env.ENS_PARENT_CERT || "certified.onchor-ai.eth";
const ENS_REGISTRY    = "0x00000000000C2E074eC69A0dFb2997BA6C7d2e1e";
const PUBLIC_RESOLVER = "0x8FADE66B79cC9f707aB26799354482EB93a5B7dD";

const REGISTRY_ABI = [
    `function setSubnodeRecord(
        bytes32 node, bytes32 label,
        address owner, address resolver, uint64 ttl
    ) external`,
    `function owner(bytes32 node) external view returns (address)`,
];

const RESOLVER_ABI = [
    `function setText(bytes32 node, string key, string value) external`,
    `function text(bytes32 node, string key) external view returns (string)`,
    `function multicall(bytes[] calldata data) external returns (bytes[] memory results)`
];

async function getContracts() {
    const provider = new ethers.JsonRpcProvider(
        `https://eth-sepolia.g.alchemy.com/v2/${process.env.ALCHEMY_API_KEY}`
    );
    const wallet   = new ethers.Wallet(process.env.PRIVATE_KEY!, provider);
    const registry = new ethers.Contract(ENS_REGISTRY, REGISTRY_ABI, wallet);
    const resolver = new ethers.Contract(PUBLIC_RESOLVER, RESOLVER_ABI, wallet);
    return { wallet, registry, resolver };
}

async function mintCert(
    ensLabel: string,
    verdict: string,
    highCount: string,
    mediumCount: string,
    txProof: string,
    reportHash: string,
    auditDate: string
) {
    if (!reportHash || reportHash.length < 10) {
        console.error(`report_hash invalide: ${reportHash}`);
        process.exit(1);
    }

    const { wallet, registry, resolver } = await getContracts();

    const label       = ensLabel;
    const parentNode  = namehash(PARENT_CERT);
    const labelHash   = ethers.keccak256(ethers.toUtf8Bytes(label));
    const fullName    = `${label}.${PARENT_CERT}`;
    const subnameNode = namehash(fullName);

    // ── Check that wallet is owner of parent ──────────────────
    const parentOwner = await registry.owner(parentNode);
    console.log(`Owner of ${PARENT_CERT}: ${parentOwner}`);
    console.log(`Wallet:                  ${wallet.address}`);

    if (parentOwner.toLowerCase() !== wallet.address.toLowerCase()) {
        throw new Error(
            `Wallet not owner of ${PARENT_CERT}.\n` +
            `Owner: ${parentOwner} | Wallet: ${wallet.address}`
        );
    }

    // -- Mint subname --
    console.log(`Minting ${fullName}...`);
    const tx1 = await registry.setSubnodeRecord(
        parentNode,
        labelHash,
        wallet.address,   // owner = wallet
        PUBLIC_RESOLVER,  // resolver
        0n                // ttl
    );
    await tx1.wait();
    const mintTx = tx1.hash;
    console.log(`✓ Subname minted — tx: ${tx1.hash}`);

    // ── Check subname owner before setText ──────────────────────────
    const subnameOwner = await registry.owner(subnameNode);
    console.log(`Owner subname: ${subnameOwner}`);

    // ── setText ──────────────────────────────────────────────────────────
    const records = [
        ["verdict",      verdict],
        ["high_count",   highCount],
        ["medium_count", mediumCount],
        ["audit_date",   auditDate],
        ["tx_proof",     txProof],
        ["report_hash",  reportHash],
    ];

    const calldatas = records.map(([key, value]) => {
        return resolver.interface.encodeFunctionData("setText", [subnameNode, key, value]);
    });

    console.log(`Sending multicall for ${records.length} records...`);
    const tx2 = await resolver.multicall(calldatas);
    await tx2.wait();
    
    for (const [key, value] of records) {
        console.log(`✓ ${key} = ${value}`);
    }

    console.log(`ENS_SUBNAME=${fullName}`);
    console.log(`ENS_MINT_TX=${mintTx}`);
    return fullName;
}

const [, , command, ...args] = process.argv;
console.log(`Args received (${args.length}):`, args);

if (command === "mintCert") {
    const [ensLabel, verdict, high, medium, txProof, reportHash, date] = args;
    console.log(`reportHash received: '${reportHash}'`);
    mintCert(ensLabel, verdict, high, medium, txProof, reportHash, date)
        .catch(console.error);
} else {
    console.error("Usage: npx ts-node scripts/ensManager.ts mintCert <address> <verdict> <high> <medium> <txProof> <reportHash> <date>");
    process.exit(1);
}