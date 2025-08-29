// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/security/Pausable.sol";

contract SRPKWebhooks is Ownable, Pausable {
    // Webhook structure
    struct Webhook {
        string url;
        address registrar;
        bool isActive;
        uint256 createdAt;
        uint256 lastTriggered;
        uint256 triggerCount;
    }
    
    // Event types
    enum EventType {
        PaymentReceived,
        LicenseCreated,
        LicenseExpired,
        LicenseRevoked,
        PriceUpdated
    }
    
    // Mappings
    mapping(bytes32 => Webhook) public webhooks;
    mapping(address => bytes32[]) public userWebhooks;
    mapping(EventType => bytes32[]) public eventSubscribers;
    
    // Events
    event WebhookRegistered(
        bytes32 indexed webhookId,
        address indexed registrar,
        string url
    );
    
    event WebhookTriggered(
        bytes32 indexed webhookId,
        EventType indexed eventType,
        bytes data
    );
    
    event WebhookRemoved(
        bytes32 indexed webhookId,
        address indexed registrar
    );
    
    event WebhookUpdated(
        bytes32 indexed webhookId,
        string newUrl
    );
    
    // Payment contract interface
    interface IPaymentContract {
        function paymentRecipient() external view returns (address);
    }
    
    // Reference to payment contract
    address public paymentContract;
    
    // Maximum webhooks per user
    uint256 public constant MAX_WEBHOOKS_PER_USER = 10;
    
    // Webhook registration fee (to prevent spam)
    uint256 public webhookFee = 0.001 ether;
    
    constructor(address _paymentContract) {
        paymentContract = _paymentContract;
    }
    
    // Register a new webhook
    function registerWebhook(
        string memory url,
        EventType[] memory eventTypes
    ) external payable whenNotPaused {
        require(msg.value >= webhookFee, "Insufficient fee");
        require(bytes(url).length > 0, "Empty URL");
        require(eventTypes.length > 0, "No events specified");
        require(
            userWebhooks[msg.sender].length < MAX_WEBHOOKS_PER_USER,
            "Max webhooks reached"
        );
        
        // Generate webhook ID
        bytes32 webhookId = keccak256(
            abi.encodePacked(msg.sender, url, block.timestamp)
        );
        
        require(!webhooks[webhookId].isActive, "Webhook already exists");
        
        // Create webhook
        webhooks[webhookId] = Webhook({
            url: url,
            registrar: msg.sender,
            isActive: true,
            createdAt: block.timestamp,
            lastTriggered: 0,
            triggerCount: 0
        });
        
        // Add to user's webhooks
        userWebhooks[msg.sender].push(webhookId);
        
        // Subscribe to events
        for (uint i = 0; i < eventTypes.length; i++) {
            eventSubscribers[eventTypes[i]].push(webhookId);
        }
        
        // Transfer fee to payment recipient
        if (msg.value > 0) {
            address paymentRecipient = IPaymentContract(paymentContract).paymentRecipient();
            (bool success, ) = paymentRecipient.call{value: msg.value}("");
            require(success, "Fee transfer failed");
        }
        
        emit WebhookRegistered(webhookId, msg.sender, url);
    }
    
    // Update webhook URL
    function updateWebhook(bytes32 webhookId, string memory newUrl) external {
        require(webhooks[webhookId].registrar == msg.sender, "Not webhook owner");
        require(webhooks[webhookId].isActive, "Webhook not active");
        require(bytes(newUrl).length > 0, "Empty URL");
        
        webhooks[webhookId].url = newUrl;
        
        emit WebhookUpdated(webhookId, newUrl);
    }
    
    // Remove webhook
    function removeWebhook(bytes32 webhookId) external {
        require(webhooks[webhookId].registrar == msg.sender, "Not webhook owner");
        require(webhooks[webhookId].isActive, "Webhook not active");
        
        webhooks[webhookId].isActive = false;
        
        // Remove from user's webhooks
        bytes32[] storage userHooks = userWebhooks[msg.sender];
        for (uint i = 0; i < userHooks.length; i++) {
            if (userHooks[i] == webhookId) {
                userHooks[i] = userHooks[userHooks.length - 1];
                userHooks.pop();
                break;
            }
        }
        
        emit WebhookRemoved(webhookId, msg.sender);
    }
    
    // Trigger webhooks for an event (called by payment contract or oracle)
    function triggerWebhooks(
        EventType eventType,
        bytes memory data
    ) external {
        require(msg.sender == paymentContract || msg.sender == owner(), "Unauthorized");
        
        bytes32[] memory subscribers = eventSubscribers[eventType];
        
        for (uint i = 0; i < subscribers.length; i++) {
            bytes32 webhookId = subscribers[i];
            
            if (webhooks[webhookId].isActive) {
                webhooks[webhookId].lastTriggered = block.timestamp;
                webhooks[webhookId].triggerCount++;
                
                emit WebhookTriggered(webhookId, eventType, data);
            }
        }
    }
    
    // Get user's webhooks
    function getUserWebhooks(address user) external view returns (bytes32[] memory) {
        return userWebhooks[user];
    }
    
    // Get webhook details
    function getWebhook(bytes32 webhookId) external view returns (
        string memory url,
        address registrar,
        bool isActive,
        uint256 createdAt,
        uint256 lastTriggered,
        uint256 triggerCount
    ) {
        Webhook memory webhook = webhooks[webhookId];
        return (
            webhook.url,
            webhook.registrar,
            webhook.isActive,
            webhook.createdAt,
            webhook.lastTriggered,
            webhook.triggerCount
        );
    }
    
    // Get event subscribers
    function getEventSubscribers(EventType eventType) external view returns (bytes32[] memory) {
        return eventSubscribers[eventType];
    }
    
    // Admin functions
    function updateWebhookFee(uint256 newFee) external onlyOwner {
        webhookFee = newFee;
    }
    
    function updatePaymentContract(address newContract) external onlyOwner {
        require(newContract != address(0), "Invalid address");
        paymentContract = newContract;
    }
    
    function pause() external onlyOwner {
        _pause();
    }
    
    function unpause() external onlyOwner {
        _unpause();
    }
    
    // Emergency withdrawal
    function emergencyWithdraw() external onlyOwner {
        uint256 balance = address(this).balance;
        require(balance > 0, "No funds to withdraw");
        (bool success, ) = owner().call{value: balance}("");
        require(success, "Withdrawal failed");
    }
}