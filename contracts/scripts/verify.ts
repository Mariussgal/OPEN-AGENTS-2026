import * as dotenv from "dotenv";
import * as fs from "fs";
dotenv.config();

const DEPLOYED_ADDRESS = "0x4DC06573aa7b214645f649E4b9412Fe5aEd775F8";
const ETHERSCAN_API_KEY = process.env.ETHERSCAN_API_KEY!;

interface EtherscanResponse {
    status: string;
    message: string;
    result: string;
}

async function verify() {
    const source = fs.readFileSync("./contracts/AnchorRegistry.sol", "utf8");

    const params = new URLSearchParams({
        apikey: ETHERSCAN_API_KEY,
        module: "contract",
        action: "verifysourcecode",
        contractaddress: DEPLOYED_ADDRESS,
        sourceCode: source,
        codeformat: "solidity-single-file",
        contractname: "AnchorRegistry",
        compilerversion: "v0.8.24+commit.e11b9ed9",
        optimizationUsed: "0",
        chainId: "11155111",
    });

    const res = await fetch("https://api.etherscan.io/v2/api?chainid=11155111", {
        method: "POST",
        body: params,
    });

    const data = (await res.json()) as EtherscanResponse;
    console.log("Etherscan response:", data);

    if (data.status === "1") {
        console.log("Verification submitted! GUID:", data.result);
        console.log("Check status in ~30s at:");
        console.log(`https://sepolia.etherscan.io/address/${DEPLOYED_ADDRESS}#code`);
    } else {
        console.error("Verification failed:", data.result);
    }
}

verify().catch(console.error);