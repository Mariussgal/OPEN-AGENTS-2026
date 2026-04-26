// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/**
 * @title EulerVault
 * @notice Intentionally vulnerable vault — FOR DEMO PURPOSES ONLY
 * @dev Contains a reentrancy vulnerability in withdraw()
 *      Inspired by the Euler Finance hack pattern (March 2023, $197M)
 */
contract EulerVault {
    mapping(address => uint256) public balances;

    event Deposit(address indexed user, uint256 amount);
    event Withdrawal(address indexed user, uint256 amount);

    function deposit() external payable {
        balances[msg.sender] += msg.value;
        emit Deposit(msg.sender, msg.value);
    }

    // ⚠️ VULNERABLE: external call before state update — classic reentrancy
    function withdraw(uint256 amount) external {
        require(balances[msg.sender] >= amount, "Insufficient balance");

        // BUG: interaction before effect
        (bool ok, ) = msg.sender.call{value: amount}("");
        require(ok, "Transfer failed");

        // State updated AFTER external call — too late
        balances[msg.sender] -= amount;

        emit Withdrawal(msg.sender, amount);
    }

    function getBalance() external view returns (uint256) {
        return address(this).balance;
    }
}
