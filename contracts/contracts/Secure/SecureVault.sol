// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title SecureVault
 * @dev Un contrat simple et sécurisé pour tester la certification ENS.
 */
contract SecureVault {
    mapping(address => uint256) public balances;
    bool private locked;

    event Deposited(address indexed user, uint256 amount);
    event Withdrawn(address indexed user, uint256 amount);

    modifier nonReentrant() {
        require(!locked, "ReentrancyGuard: reentrant call");
        locked = true;
        _;
        locked = false;
    }

    function _deposit(address user, uint256 amount) private {
        require(amount > 0, "Amount must be > 0");
        balances[user] += amount;
        emit Deposited(user, amount);
    }

    function deposit() external payable nonReentrant {
        _deposit(msg.sender, msg.value);
    }

    function withdraw(uint256 amount) external nonReentrant {
        require(balances[msg.sender] >= amount, "Insufficient balance");
        
        // Effet avant l'interaction (Checks-Effects-Interactions)
        balances[msg.sender] -= amount;
        
        // Interaction
        (bool success, ) = msg.sender.call{value: amount}("");
        require(success, "Transfer failed");
        
        emit Withdrawn(msg.sender, amount);
    }

    receive() external payable nonReentrant {
        _deposit(msg.sender, msg.value);
    }
}
