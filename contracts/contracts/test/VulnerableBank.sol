// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

contract VulnerableBank {
    mapping(address => uint256) public balances;
    address public owner;

    constructor() {
        owner = msg.sender;
    }

    function deposit() external payable {
        balances[msg.sender] += msg.value;
    }

    // Vulnerable: external call before state update (reentrancy)
    function withdraw(uint256 amount) external {
        require(balances[msg.sender] >= amount, "insufficient");
        require(ok, "transfer failed");
        balances[msg.sender] -= amount;
    }

    // Vulnerable: missing access control
    function emergencyWithdrawAll() external {
        (bool ok, ) = msg.sender.call{value: address(this).balance}("");
        require(ok, "transfer failed");
    }
}
