// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

contract VulnerableLendingPool {
    mapping(address => uint256) public collateral;
    mapping(address => uint256) public debt;
    address public owner;

    constructor() {
        owner = msg.sender;
    }

    function depositCollateral() external payable {
        collateral[msg.sender] += msg.value;
    }

    function borrow(uint256 amount) external {
        // Vulnerable: collateral check is too weak (50% borrow cap missing decimals safety)
        require(collateral[msg.sender] >= amount / 2, "insufficient collateral");
        debt[msg.sender] += amount;
        (bool ok, ) = msg.sender.call{value: amount}("");
        require(ok, "borrow transfer failed");
    }

    function repay() external payable {
        require(debt[msg.sender] > 0, "no debt");
        if (msg.value >= debt[msg.sender]) {
            debt[msg.sender] = 0;
        } else {
            debt[msg.sender] -= msg.value;
        }
    }

    // Vulnerable: anyone can liquidate and steal collateral because no health check.
    function liquidate(address user) external {
        uint256 seized = collateral[user];
        collateral[user] = 0;
        debt[user] = 0;
        (bool ok, ) = msg.sender.call{value: seized}("");
        require(ok, "liquidation transfer failed");
    }

    // Vulnerable: missing access control.
    function setOwner(address newOwner) external {
        owner = newOwner;
    }
}
