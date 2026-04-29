import { buildModule } from "@nomicfoundation/hardhat-ignition/modules";

const AnchorRegistryModule = buildModule("AnchorRegistryModule", (m) => {
    const anchorRegistry = m.contract("AnchorRegistry");
    return { anchorRegistry };
});

export default AnchorRegistryModule;