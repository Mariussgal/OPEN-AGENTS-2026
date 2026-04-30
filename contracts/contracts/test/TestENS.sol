// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/**
 * @title Counter
 * @notice Compteur simple — aucune vulnérabilité intentionnelle.
 */
contract Counter {
    uint256 private count;
    address public immutable owner;

    event Incremented(address indexed by, uint256 newCount);
    event Reset(address indexed by);

    error NotOwner();
    error Overflow();

    constructor() {
        owner = msg.sender;
    }

    function increment() external {
        if (count >= type(uint256).max) revert Overflow();
        unchecked { count += 1; }
        emit Incremented(msg.sender, count);
    }

    function reset() external {
        if (msg.sender != owner) revert NotOwner();
        count = 0;
        emit Reset(msg.sender);
    }

    function getCount() external view returns (uint256) {
        return count;
    }
}