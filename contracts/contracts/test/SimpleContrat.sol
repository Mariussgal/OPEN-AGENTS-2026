// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

contract SimpleStorage {
    address public owner;
    uint256 private value;
    string  private message;

    event ValueUpdated(address indexed by, uint256 newValue);
    event MessageUpdated(address indexed by, string newMessage);
    event OwnershipTransferred(address indexed previousOwner, address indexed newOwner);

    error NotOwner();
    error EmptyMessage();
    error ZeroValue();

    modifier onlyOwner() {
        if (msg.sender != owner) revert NotOwner();
        _;
    }

    constructor(uint256 initialValue, string memory initialMessage) {
        owner   = msg.sender;
        value   = initialValue;
        message = initialMessage;
    }

    function setValue(uint256 newValue) external onlyOwner {
        if (newValue == 0) revert ZeroValue();
        value = newValue;
        emit ValueUpdated(msg.sender, newValue);
    }

    function setMessage(string calldata newMessage) external onlyOwner {
        if (bytes(newMessage).length == 0) revert EmptyMessage();
        message = newMessage;
        emit MessageUpdated(msg.sender, newMessage);
    }

    function transferOwnership(address newOwner) external onlyOwner {
        require(newOwner != address(0), "Zero address");
        emit OwnershipTransferred(owner, newOwner);
        owner = newOwner;
    }

    function getValue() external view returns (uint256) {
        return value;
    }

    function getMessage() external view returns (string memory) {
        return message;
    }
}