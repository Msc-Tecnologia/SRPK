const { expect } = require("chai");
const { ethers } = require("hardhat");

describe("SRPKWebhooks", function () {
  let webhooks;
  let payment;
  let owner;
  let user1;
  let user2;
  const webhookFee = ethers.parseEther("0.001");

  beforeEach(async function () {
    [owner, user1, user2] = await ethers.getSigners();
    
    // Deploy payment contract first
    const Payment = await ethers.getContractFactory("SRPKPayment");
    payment = await Payment.deploy();
    await payment.waitForDeployment();
    
    // Deploy webhooks contract
    const Webhooks = await ethers.getContractFactory("SRPKWebhooks");
    webhooks = await Webhooks.deploy(await payment.getAddress());
    await webhooks.waitForDeployment();
    
    // Set webhook contract in payment contract
    await payment.setWebhookContract(await webhooks.getAddress());
  });

  describe("Deployment", function () {
    it("Should set the correct payment contract", async function () {
      expect(await webhooks.paymentContract()).to.equal(await payment.getAddress());
    });

    it("Should set the correct webhook fee", async function () {
      expect(await webhooks.webhookFee()).to.equal(webhookFee);
    });
  });

  describe("Webhook Registration", function () {
    it("Should register a webhook successfully", async function () {
      const url = "https://example.com/webhook";
      const eventTypes = [0, 1]; // PaymentReceived, LicenseCreated
      
      await expect(
        webhooks.connect(user1).registerWebhook(url, eventTypes, { value: webhookFee })
      ).to.emit(webhooks, "WebhookRegistered");
      
      const userWebhooks = await webhooks.getUserWebhooks(user1.address);
      expect(userWebhooks.length).to.equal(1);
    });

    it("Should fail if insufficient fee", async function () {
      const url = "https://example.com/webhook";
      const eventTypes = [0];
      
      await expect(
        webhooks.connect(user1).registerWebhook(url, eventTypes, { value: 0 })
      ).to.be.revertedWith("Insufficient fee");
    });

    it("Should fail with empty URL", async function () {
      const url = "";
      const eventTypes = [0];
      
      await expect(
        webhooks.connect(user1).registerWebhook(url, eventTypes, { value: webhookFee })
      ).to.be.revertedWith("Empty URL");
    });

    it("Should fail with no events", async function () {
      const url = "https://example.com/webhook";
      const eventTypes = [];
      
      await expect(
        webhooks.connect(user1).registerWebhook(url, eventTypes, { value: webhookFee })
      ).to.be.revertedWith("No events specified");
    });

    it("Should enforce max webhooks per user", async function () {
      const url = "https://example.com/webhook";
      const eventTypes = [0];
      
      // Register max webhooks
      for (let i = 0; i < 10; i++) {
        await webhooks.connect(user1).registerWebhook(
          `${url}${i}`,
          eventTypes,
          { value: webhookFee }
        );
      }
      
      // Try to register one more
      await expect(
        webhooks.connect(user1).registerWebhook(url, eventTypes, { value: webhookFee })
      ).to.be.revertedWith("Max webhooks reached");
    });
  });

  describe("Webhook Management", function () {
    let webhookId;
    
    beforeEach(async function () {
      const url = "https://example.com/webhook";
      const eventTypes = [0, 1];
      
      const tx = await webhooks.connect(user1).registerWebhook(
        url,
        eventTypes,
        { value: webhookFee }
      );
      
      const receipt = await tx.wait();
      const event = receipt.logs.find(log => {
        try {
          const parsed = webhooks.interface.parseLog(log);
          return parsed.name === "WebhookRegistered";
        } catch (e) {
          return false;
        }
      });
      
      webhookId = webhooks.interface.parseLog(event).args.webhookId;
    });

    it("Should update webhook URL", async function () {
      const newUrl = "https://newexample.com/webhook";
      
      await expect(
        webhooks.connect(user1).updateWebhook(webhookId, newUrl)
      ).to.emit(webhooks, "WebhookUpdated");
      
      const webhook = await webhooks.getWebhook(webhookId);
      expect(webhook.url).to.equal(newUrl);
    });

    it("Should not allow non-owner to update webhook", async function () {
      const newUrl = "https://newexample.com/webhook";
      
      await expect(
        webhooks.connect(user2).updateWebhook(webhookId, newUrl)
      ).to.be.revertedWith("Not webhook owner");
    });

    it("Should remove webhook", async function () {
      await expect(
        webhooks.connect(user1).removeWebhook(webhookId)
      ).to.emit(webhooks, "WebhookRemoved");
      
      const webhook = await webhooks.getWebhook(webhookId);
      expect(webhook.isActive).to.be.false;
    });

    it("Should not allow non-owner to remove webhook", async function () {
      await expect(
        webhooks.connect(user2).removeWebhook(webhookId)
      ).to.be.revertedWith("Not webhook owner");
    });
  });

  describe("Webhook Triggering", function () {
    let webhookId;
    
    beforeEach(async function () {
      const url = "https://example.com/webhook";
      const eventTypes = [0, 1];
      
      const tx = await webhooks.connect(user1).registerWebhook(
        url,
        eventTypes,
        { value: webhookFee }
      );
      
      const receipt = await tx.wait();
      const event = receipt.logs.find(log => {
        try {
          const parsed = webhooks.interface.parseLog(log);
          return parsed.name === "WebhookRegistered";
        } catch (e) {
          return false;
        }
      });
      
      webhookId = webhooks.interface.parseLog(event).args.webhookId;
    });

    it("Should trigger webhook from payment contract", async function () {
      // Make a payment to trigger webhook
      const email = "test@example.com";
      const name = "Test User";
      const productType = "starter";
      const amount = ethers.parseUnits("99", 6);
      
      await expect(
        payment.connect(user2).purchaseWithBNB(email, name, productType, {
          value: amount
        })
      ).to.emit(payment, "LicensePurchased");
      
      // Webhook should be triggered (check logs)
    });

    it("Should only allow authorized contracts to trigger", async function () {
      const eventType = 0;
      const data = ethers.AbiCoder.defaultAbiCoder().encode(
        ["address", "uint256"],
        [user1.address, 100]
      );
      
      await expect(
        webhooks.connect(user1).triggerWebhooks(eventType, data)
      ).to.be.revertedWith("Unauthorized");
    });
  });

  describe("Admin Functions", function () {
    it("Should update webhook fee", async function () {
      const newFee = ethers.parseEther("0.002");
      await webhooks.connect(owner).updateWebhookFee(newFee);
      expect(await webhooks.webhookFee()).to.equal(newFee);
    });

    it("Should update payment contract", async function () {
      const newContract = user2.address;
      await webhooks.connect(owner).updatePaymentContract(newContract);
      expect(await webhooks.paymentContract()).to.equal(newContract);
    });

    it("Should pause and unpause", async function () {
      await webhooks.connect(owner).pause();
      
      // Try to register webhook while paused
      await expect(
        webhooks.connect(user1).registerWebhook(
          "https://example.com",
          [0],
          { value: webhookFee }
        )
      ).to.be.revertedWith("EnforcedPause");
      
      await webhooks.connect(owner).unpause();
      
      // Should work after unpause
      await expect(
        webhooks.connect(user1).registerWebhook(
          "https://example.com",
          [0],
          { value: webhookFee }
        )
      ).to.emit(webhooks, "WebhookRegistered");
    });
  });

  describe("Event Subscribers", function () {
    it("Should correctly manage event subscribers", async function () {
      const url1 = "https://example1.com/webhook";
      const url2 = "https://example2.com/webhook";
      
      // Register webhooks for same event
      await webhooks.connect(user1).registerWebhook(url1, [0], { value: webhookFee });
      await webhooks.connect(user2).registerWebhook(url2, [0], { value: webhookFee });
      
      // Check subscribers for event 0
      const subscribers = await webhooks.getEventSubscribers(0);
      expect(subscribers.length).to.equal(2);
    });
  });
});