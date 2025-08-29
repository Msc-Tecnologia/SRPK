// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/security/ReentrancyGuard.sol";
import "@openzeppelin/contracts/token/ERC20/IERC20.sol";

contract SRPKPayment is Ownable, ReentrancyGuard {
    // Payment recipient address
    address public paymentRecipient = 0x680c48F49187a2121a25e3F834585a8b82DfdC16;
    
    // Webhook contract address
    address public webhookContract;
    
    // Supported tokens
    address public constant USDT_ADDRESS = 0x55d398326f99059fF775485246999027B3197955; // BSC USDT
    address public constant ETH_ADDRESS = 0x2170Ed0880ac9A755fd29B2688956BD959F933F8; // BSC ETH
    
    // Product prices in USD (with 6 decimals for USDT compatibility)
    uint256 public constant STARTER_PRICE = 99000000; // $99.00
    uint256 public constant PROFESSIONAL_PRICE = 299000000; // $299.00
    
    // License structure
    struct License {
        address buyer;
        string email;
        string name;
        string productType;
        uint256 purchaseTime;
        uint256 expiryTime;
        string txHash;
        bool isActive;
    }
    
    // Payment record structure
    struct Payment {
        address buyer;
        string productType;
        uint256 amount;
        string paymentToken;
        uint256 timestamp;
        string email;
    }
    
    // Mappings
    mapping(address => License[]) public userLicenses;
    mapping(string => License) public licensesByKey;
    mapping(address => Payment[]) public userPayments;
    
    // Events
    event LicensePurchased(
        address indexed buyer,
        string email,
        string productType,
        string paymentToken,
        uint256 amount,
        string licenseKey,
        uint256 expiryTime
    );
    
    event PaymentReceived(
        address indexed buyer,
        string productType,
        uint256 amount,
        string paymentToken
    );
    
    event LicenseRevoked(
        string licenseKey,
        address indexed buyer
    );
    
    // Webhook interface
    interface IWebhookContract {
        function triggerWebhooks(uint8 eventType, bytes memory data) external;
    }
    
    // Modifiers
    modifier validProduct(string memory productType) {
        require(
            keccak256(bytes(productType)) == keccak256(bytes("starter")) ||
            keccak256(bytes(productType)) == keccak256(bytes("professional")),
            "Invalid product type"
        );
        _;
    }
    
    constructor() {}
    
    // Purchase with BNB
    function purchaseWithBNB(
        string memory email,
        string memory name,
        string memory productType
    ) external payable nonReentrant validProduct(productType) {
        uint256 requiredAmount = getProductPrice(productType);
        require(msg.value >= requiredAmount, "Insufficient BNB sent");
        
        // Transfer BNB to payment recipient
        (bool success, ) = paymentRecipient.call{value: msg.value}("");
        require(success, "BNB transfer failed");
        
        // Create license
        _createLicense(msg.sender, email, name, productType, "BNB", msg.value);
        
        // Record payment
        _recordPayment(msg.sender, productType, msg.value, "BNB", email);
    }
    
    // Purchase with USDT
    function purchaseWithUSDT(
        string memory email,
        string memory name,
        string memory productType
    ) external nonReentrant validProduct(productType) {
        uint256 requiredAmount = getProductPrice(productType);
        
        // Transfer USDT from buyer to payment recipient
        IERC20 usdt = IERC20(USDT_ADDRESS);
        require(
            usdt.transferFrom(msg.sender, paymentRecipient, requiredAmount),
            "USDT transfer failed"
        );
        
        // Create license
        _createLicense(msg.sender, email, name, productType, "USDT", requiredAmount);
        
        // Record payment
        _recordPayment(msg.sender, productType, requiredAmount, "USDT", email);
    }
    
    // Purchase with ETH (Wrapped ETH on BSC)
    function purchaseWithETH(
        string memory email,
        string memory name,
        string memory productType,
        uint256 amount
    ) external nonReentrant validProduct(productType) {
        // Note: Amount should be calculated based on current ETH/USD price
        require(amount > 0, "Invalid amount");
        
        // Transfer ETH from buyer to payment recipient
        IERC20 eth = IERC20(ETH_ADDRESS);
        require(
            eth.transferFrom(msg.sender, paymentRecipient, amount),
            "ETH transfer failed"
        );
        
        // Create license
        _createLicense(msg.sender, email, name, productType, "ETH", amount);
        
        // Record payment
        _recordPayment(msg.sender, productType, amount, "ETH", email);
    }
    
    // Internal function to create license
    function _createLicense(
        address buyer,
        string memory email,
        string memory name,
        string memory productType,
        string memory paymentToken,
        uint256 amount
    ) internal {
        uint256 expiryTime = block.timestamp + 30 days; // 30 days subscription
        string memory licenseKey = _generateLicenseKey(buyer, block.timestamp);
        
        License memory newLicense = License({
            buyer: buyer,
            email: email,
            name: name,
            productType: productType,
            purchaseTime: block.timestamp,
            expiryTime: expiryTime,
            txHash: "",
            isActive: true
        });
        
        userLicenses[buyer].push(newLicense);
        licensesByKey[licenseKey] = newLicense;
        
        emit LicensePurchased(
            buyer,
            email,
            productType,
            paymentToken,
            amount,
            licenseKey,
            expiryTime
        );
        
        // Trigger webhook if contract is set
        if (webhookContract != address(0)) {
            bytes memory webhookData = abi.encode(
                buyer,
                email,
                productType,
                paymentToken,
                amount,
                licenseKey
            );
            IWebhookContract(webhookContract).triggerWebhooks(1, webhookData); // 1 = LicenseCreated
        }
    }
    
    // Internal function to record payment
    function _recordPayment(
        address buyer,
        string memory productType,
        uint256 amount,
        string memory paymentToken,
        string memory email
    ) internal {
        Payment memory newPayment = Payment({
            buyer: buyer,
            productType: productType,
            amount: amount,
            paymentToken: paymentToken,
            timestamp: block.timestamp,
            email: email
        });
        
        userPayments[buyer].push(newPayment);
        
        emit PaymentReceived(buyer, productType, amount, paymentToken);
        
        // Trigger webhook for payment received
        if (webhookContract != address(0)) {
            bytes memory webhookData = abi.encode(
                buyer,
                productType,
                amount,
                paymentToken,
                block.timestamp
            );
            IWebhookContract(webhookContract).triggerWebhooks(0, webhookData); // 0 = PaymentReceived
        }
    }
    
    // Generate unique license key
    function _generateLicenseKey(address buyer, uint256 timestamp) internal pure returns (string memory) {
        bytes32 hash = keccak256(abi.encodePacked(buyer, timestamp));
        return _toHexString(hash);
    }
    
    // Convert bytes32 to hex string
    function _toHexString(bytes32 data) internal pure returns (string memory) {
        bytes memory alphabet = "0123456789ABCDEF";
        bytes memory str = new bytes(64);
        for (uint256 i = 0; i < 32; i++) {
            str[i * 2] = alphabet[uint8(data[i] >> 4)];
            str[i * 2 + 1] = alphabet[uint8(data[i] & 0x0f)];
        }
        return string(str);
    }
    
    // Get product price
    function getProductPrice(string memory productType) public pure returns (uint256) {
        if (keccak256(bytes(productType)) == keccak256(bytes("starter"))) {
            return STARTER_PRICE;
        } else if (keccak256(bytes(productType)) == keccak256(bytes("professional"))) {
            return PROFESSIONAL_PRICE;
        }
        revert("Invalid product type");
    }
    
    // Check if license is valid
    function isLicenseValid(string memory licenseKey) public view returns (bool) {
        License memory license = licensesByKey[licenseKey];
        return license.isActive && block.timestamp < license.expiryTime;
    }
    
    // Get user licenses
    function getUserLicenses(address user) public view returns (License[] memory) {
        return userLicenses[user];
    }
    
    // Get user payments
    function getUserPayments(address user) public view returns (Payment[] memory) {
        return userPayments[user];
    }
    
    // Admin functions
    function updatePaymentRecipient(address newRecipient) external onlyOwner {
        require(newRecipient != address(0), "Invalid address");
        paymentRecipient = newRecipient;
    }
    
    function revokeLicense(string memory licenseKey) external onlyOwner {
        License storage license = licensesByKey[licenseKey];
        license.isActive = false;
        emit LicenseRevoked(licenseKey, license.buyer);
        
        // Trigger webhook for license revoked
        if (webhookContract != address(0)) {
            bytes memory webhookData = abi.encode(licenseKey, license.buyer);
            IWebhookContract(webhookContract).triggerWebhooks(3, webhookData); // 3 = LicenseRevoked
        }
    }
    
    function setWebhookContract(address _webhookContract) external onlyOwner {
        webhookContract = _webhookContract;
    }
    
    // Emergency withdrawal (only owner)
    function emergencyWithdraw() external onlyOwner {
        uint256 balance = address(this).balance;
        require(balance > 0, "No funds to withdraw");
        (bool success, ) = owner().call{value: balance}("");
        require(success, "Withdrawal failed");
    }
}