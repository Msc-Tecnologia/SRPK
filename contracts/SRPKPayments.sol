// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

interface IERC20 {
    function transferFrom(address sender, address recipient, uint256 amount) external returns (bool);
    function allowance(address owner, address spender) external view returns (uint256);
    function balanceOf(address account) external view returns (uint256);
}

contract SRPKPayments {
    address public immutable merchant;
    address public owner;

    event PaymentReceived(address indexed payer, address indexed token, uint256 amount, string productId, bytes32 emailHash);
    event MerchantUpdated(address indexed oldMerchant, address indexed newMerchant);
    event OwnerTransferred(address indexed oldOwner, address indexed newOwner);

    modifier onlyOwner() {
        require(msg.sender == owner, "not owner");
        _;
    }

    constructor(address merchantAddress) {
        require(merchantAddress != address(0), "merchant=0");
        merchant = merchantAddress;
        owner = msg.sender;
    }

    function transferOwnership(address newOwner) external onlyOwner {
        require(newOwner != address(0), "newOwner=0");
        emit OwnerTransferred(owner, newOwner);
        owner = newOwner;
    }

    // Pay with native coin (ETH/BNB)
    function payNative(string calldata productId, bytes32 emailHash) external payable {
        require(msg.value > 0, "no value");
        (bool ok, ) = payable(merchant).call{value: msg.value}("");
        require(ok, "transfer failed");
        emit PaymentReceived(msg.sender, address(0), msg.value, productId, emailHash);
    }

    // Pay with ERC20 (e.g., USDT)
    function payERC20(address token, uint256 amount, string calldata productId, bytes32 emailHash) external {
        require(token != address(0), "token=0");
        require(amount > 0, "amount=0");
        require(IERC20(token).transferFrom(msg.sender, merchant, amount), "transferFrom failed");
        emit PaymentReceived(msg.sender, token, amount, productId, emailHash);
    }
}

