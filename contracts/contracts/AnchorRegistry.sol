// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

contract AnchorRegistry {
    event Anchored(
        bytes32 indexed patternHash,
        bytes32 indexed rootHash0G,
        address indexed contributor,
        uint256 timestamp
    );

    function anchor(bytes32 pHash, bytes32 root0G) external {
        emit Anchored(pHash, root0G, msg.sender, block.timestamp);
    }
}