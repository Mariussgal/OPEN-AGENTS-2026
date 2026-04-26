// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

contract AnchorRegistry {
    struct Anchor {
        bytes32 rootHash0G;
        address contributor;
        uint256 timestamp;
        bool exists;
    }

    mapping(bytes32 => Anchor) public anchors;

    mapping(address => uint256) public contributionCount;

    bytes32[] public patternHashes;

    event Anchored(
        bytes32 indexed patternHash,
        bytes32 indexed rootHash0G,
        address indexed contributor,
        uint256 timestamp
    );

    error AlreadyAnchored(bytes32 patternHash);

    function anchor(bytes32 pHash, bytes32 root0G) external {
        if (anchors[pHash].exists) {
            revert AlreadyAnchored(pHash);
        }

        anchors[pHash] = Anchor({
            rootHash0G: root0G,
            contributor: msg.sender,
            timestamp: block.timestamp,
            exists: true
        });

        contributionCount[msg.sender]++;
        patternHashes.push(pHash);

        emit Anchored(pHash, root0G, msg.sender, block.timestamp);
    }

    function isAnchored(bytes32 pHash) external view returns (bool) {
        return anchors[pHash].exists;
    }

    function getAnchor(
        bytes32 pHash
    )
        external
        view
        returns (bytes32 rootHash0G, address contributor, uint256 timestamp)
    {
        Anchor memory a = anchors[pHash];
        require(a.exists, "Pattern not anchored");
        return (a.rootHash0G, a.contributor, a.timestamp);
    }

    function getTotalAnchors() external view returns (uint256) {
        return patternHashes.length;
    }
}
