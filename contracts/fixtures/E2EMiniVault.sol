// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/// @dev Minimal contract to test audit pipeline (intentionally obvious reentrancy).
contract E2EMiniVault {
    mapping(address => uint256) public balances;

    function deposit() external payable {
        balances[msg.sender] += msg.value;
    }

    function withdraw(uint256 amount) external {
        require(balances[msg.sender] >= amount, "insufficient balance");
        (bool ok, ) = payable(msg.sender).call{value: amount}("");
        require(ok, "transfer failed");
        balances[msg.sender] -= amount;
    }
}
