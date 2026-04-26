import { ethers } from "ethers";
import * as fs from "fs";
import * as path from "path";
import * as dotenv from "dotenv";

dotenv.config();

async function main() {
    const provider = new ethers.JsonRpcProvider(
        `https://eth-sepolia.g.alchemy.com/v2/${process.env.ALCHEMY_API_KEY}`
    );
    const wallet = new ethers.Wallet(process.env.PRIVATE_KEY!, provider);

    console.log("Deploying from:", wallet.address);

    const artifactPath = path.resolve(
        "./artifacts/contracts/AnchorRegistry.sol/AnchorRegistry.json"
    );
    const artifact = JSON.parse(fs.readFileSync(artifactPath, "utf8"));

    const factory = new ethers.ContractFactory(artifact.abi, artifact.bytecode, wallet);
    const contract = await factory.deploy();
    await contract.waitForDeployment();

    const address = await contract.getAddress();
    console.log("AnchorRegistry deployed to:", address);
}

main().catch(console.error);