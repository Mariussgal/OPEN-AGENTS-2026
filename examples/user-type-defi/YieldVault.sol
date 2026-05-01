// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

interface IERC20Like {
    function transfer(address to, uint256 value) external returns (bool);
    function transferFrom(address from, address to, uint256 value) external returns (bool);
    function balanceOf(address account) external view returns (uint256);
}

contract YieldVault {
    IERC20Like public immutable asset;
    uint256 public totalShares;
    mapping(address => uint256) public sharesOf;

    event Deposit(address indexed user, uint256 amount, uint256 mintedShares);
    event Withdraw(address indexed user, uint256 burnedShares, uint256 amountOut);

    constructor(address asset_) {
        require(asset_ != address(0), "ZERO_ASSET");
        asset = IERC20Like(asset_);
    }

    function totalAssets() public view returns (uint256) {
        return asset.balanceOf(address(this));
    }

    function deposit(uint256 amount) external returns (uint256 mintedShares) {
        require(amount > 0, "ZERO_AMOUNT");

        uint256 assetsBefore = totalAssets();
        require(asset.transferFrom(msg.sender, address(this), amount), "TRANSFER_IN_FAIL");

        if (totalShares == 0 || assetsBefore == 0) {
            mintedShares = amount;
        } else {
            mintedShares = (amount * totalShares) / assetsBefore;
        }

        require(mintedShares > 0, "ZERO_SHARES");
        sharesOf[msg.sender] += mintedShares;
        totalShares += mintedShares;

        emit Deposit(msg.sender, amount, mintedShares);
    }

    function withdraw(uint256 shareAmount) external returns (uint256 amountOut) {
        require(shareAmount > 0, "ZERO_SHARES");
        require(sharesOf[msg.sender] >= shareAmount, "INSUFFICIENT_SHARES");

        uint256 assets = totalAssets();
        amountOut = (shareAmount * assets) / totalShares;

        sharesOf[msg.sender] -= shareAmount;
        totalShares -= shareAmount;

        require(asset.transfer(msg.sender, amountOut), "TRANSFER_OUT_FAIL");
        emit Withdraw(msg.sender, shareAmount, amountOut);
    }
}

