const { expect } = require("chai");
const { ethers } = require("hardhat");

describe("SRPKPayment", function () {
  let srpkPayment;
  let owner;
  let buyer;
  let paymentRecipient;
  const STARTER_PRICE = ethers.parseUnits("99", 6); // $99 with 6 decimals
  const PROFESSIONAL_PRICE = ethers.parseUnits("299", 6); // $299 with 6 decimals

  beforeEach(async function () {
    [owner, buyer, paymentRecipient] = await ethers.getSigners();
    
    const SRPKPayment = await ethers.getContractFactory("SRPKPayment");
    srpkPayment = await SRPKPayment.deploy();
    await srpkPayment.waitForDeployment();
  });

  describe("Deployment", function () {
    it("Should set the correct payment recipient", async function () {
      expect(await srpkPayment.paymentRecipient()).to.equal("0x680c48F49187a2121a25e3F834585a8b82DfdC16");
    });

    it("Should set the correct product prices", async function () {
      expect(await srpkPayment.STARTER_PRICE()).to.equal(STARTER_PRICE);
      expect(await srpkPayment.PROFESSIONAL_PRICE()).to.equal(PROFESSIONAL_PRICE);
    });
  });

  describe("BNB Payments", function () {
    it("Should process BNB payment for starter plan", async function () {
      const email = "test@example.com";
      const name = "Test User";
      const productType = "starter";
      
      // Send BNB payment
      await expect(
        srpkPayment.connect(buyer).purchaseWithBNB(email, name, productType, {
          value: STARTER_PRICE
        })
      ).to.emit(srpkPayment, "LicensePurchased");
      
      // Check user licenses
      const licenses = await srpkPayment.getUserLicenses(buyer.address);
      expect(licenses.length).to.equal(1);
      expect(licenses[0].email).to.equal(email);
      expect(licenses[0].productType).to.equal(productType);
    });

    it("Should fail if insufficient BNB sent", async function () {
      const email = "test@example.com";
      const name = "Test User";
      const productType = "starter";
      
      await expect(
        srpkPayment.connect(buyer).purchaseWithBNB(email, name, productType, {
          value: ethers.parseUnits("50", 6) // Only $50
        })
      ).to.be.revertedWith("Insufficient BNB sent");
    });
  });

  describe("Product Validation", function () {
    it("Should reject invalid product types", async function () {
      const email = "test@example.com";
      const name = "Test User";
      const invalidProduct = "invalid";
      
      await expect(
        srpkPayment.connect(buyer).purchaseWithBNB(email, name, invalidProduct, {
          value: STARTER_PRICE
        })
      ).to.be.revertedWith("Invalid product type");
    });
  });

  describe("License Management", function () {
    it("Should generate unique license keys", async function () {
      const email1 = "user1@example.com";
      const email2 = "user2@example.com";
      const name = "Test User";
      const productType = "starter";
      
      // Purchase two licenses
      await srpkPayment.connect(buyer).purchaseWithBNB(email1, name, productType, {
        value: STARTER_PRICE
      });
      
      await srpkPayment.connect(buyer).purchaseWithBNB(email2, name, productType, {
        value: STARTER_PRICE
      });
      
      const licenses = await srpkPayment.getUserLicenses(buyer.address);
      expect(licenses.length).to.equal(2);
      // License keys should be different (generated based on timestamp)
      expect(licenses[0].purchaseTime).to.not.equal(licenses[1].purchaseTime);
    });
  });

  describe("Admin Functions", function () {
    it("Should allow owner to update payment recipient", async function () {
      const newRecipient = buyer.address;
      await srpkPayment.connect(owner).updatePaymentRecipient(newRecipient);
      expect(await srpkPayment.paymentRecipient()).to.equal(newRecipient);
    });

    it("Should not allow non-owner to update payment recipient", async function () {
      const newRecipient = buyer.address;
      await expect(
        srpkPayment.connect(buyer).updatePaymentRecipient(newRecipient)
      ).to.be.revertedWithCustomError(srpkPayment, "OwnableUnauthorizedAccount");
    });
  });
});