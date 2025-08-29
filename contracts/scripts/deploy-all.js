const hre = require("hardhat");
const fs = require("fs");
const path = require("path");

async function main() {
  console.log("Deploying SRPK Pro Smart Contracts...");
  console.log("=====================================");

  // Get deployer account
  const [deployer] = await hre.ethers.getSigners();
  console.log("Deploying with account:", deployer.address);
  
  const balance = await hre.ethers.provider.getBalance(deployer.address);
  console.log("Account balance:", hre.ethers.formatEther(balance), "BNB");
  
  // Deploy Payment Contract
  console.log("\n1. Deploying SRPKPayment contract...");
  const SRPKPayment = await hre.ethers.getContractFactory("SRPKPayment");
  const srpkPayment = await SRPKPayment.deploy();
  await srpkPayment.waitForDeployment();
  
  const paymentAddress = await srpkPayment.getAddress();
  console.log("   ✓ SRPKPayment deployed to:", paymentAddress);
  console.log("   ✓ Payment recipient:", await srpkPayment.paymentRecipient());
  
  // Deploy Webhooks Contract
  console.log("\n2. Deploying SRPKWebhooks contract...");
  const SRPKWebhooks = await hre.ethers.getContractFactory("SRPKWebhooks");
  const srpkWebhooks = await SRPKWebhooks.deploy(paymentAddress);
  await srpkWebhooks.waitForDeployment();
  
  const webhooksAddress = await srpkWebhooks.getAddress();
  console.log("   ✓ SRPKWebhooks deployed to:", webhooksAddress);
  console.log("   ✓ Webhook fee:", hre.ethers.formatEther(await srpkWebhooks.webhookFee()), "BNB");
  
  // Link contracts
  console.log("\n3. Linking contracts...");
  const setWebhookTx = await srpkPayment.setWebhookContract(webhooksAddress);
  await setWebhookTx.wait();
  console.log("   ✓ Webhook contract set in payment contract");
  
  // Wait for confirmations
  console.log("\n4. Waiting for block confirmations...");
  await srpkPayment.deploymentTransaction().wait(5);
  await srpkWebhooks.deploymentTransaction().wait(5);
  console.log("   ✓ Confirmations received");
  
  // Verify contracts on BscScan
  if (hre.network.name !== "hardhat" && hre.network.name !== "localhost") {
    console.log("\n5. Verifying contracts on BscScan...");
    
    try {
      // Verify Payment Contract
      console.log("   Verifying SRPKPayment...");
      await hre.run("verify:verify", {
        address: paymentAddress,
        constructorArguments: [],
      });
      console.log("   ✓ SRPKPayment verified");
    } catch (error) {
      console.error("   ✗ Error verifying SRPKPayment:", error.message);
    }
    
    try {
      // Verify Webhooks Contract
      console.log("   Verifying SRPKWebhooks...");
      await hre.run("verify:verify", {
        address: webhooksAddress,
        constructorArguments: [paymentAddress],
      });
      console.log("   ✓ SRPKWebhooks verified");
    } catch (error) {
      console.error("   ✗ Error verifying SRPKWebhooks:", error.message);
    }
  }
  
  // Create deployments directory
  const deploymentsDir = path.join(__dirname, "..", "deployments");
  if (!fs.existsSync(deploymentsDir)) {
    fs.mkdirSync(deploymentsDir);
  }
  
  // Save deployment info
  console.log("\n6. Saving deployment information...");
  const deploymentInfo = {
    network: hre.network.name,
    chainId: hre.network.config.chainId,
    deploymentTime: new Date().toISOString(),
    deployer: deployer.address,
    contracts: {
      payment: {
        address: paymentAddress,
        paymentRecipient: await srpkPayment.paymentRecipient(),
        starterPrice: (await srpkPayment.STARTER_PRICE()).toString(),
        professionalPrice: (await srpkPayment.PROFESSIONAL_PRICE()).toString(),
        usdtAddress: await srpkPayment.USDT_ADDRESS(),
        ethAddress: await srpkPayment.ETH_ADDRESS()
      },
      webhooks: {
        address: webhooksAddress,
        paymentContract: await srpkWebhooks.paymentContract(),
        webhookFee: (await srpkWebhooks.webhookFee()).toString(),
        maxWebhooksPerUser: (await srpkWebhooks.MAX_WEBHOOKS_PER_USER()).toString()
      }
    }
  };
  
  const deploymentPath = path.join(deploymentsDir, `${hre.network.name}-deployment.json`);
  fs.writeFileSync(deploymentPath, JSON.stringify(deploymentInfo, null, 2));
  console.log("   ✓ Deployment info saved to:", deploymentPath);
  
  // Get ABIs
  const paymentArtifact = await hre.artifacts.readArtifact("SRPKPayment");
  const webhooksArtifact = await hre.artifacts.readArtifact("SRPKWebhooks");
  
  // Save ABIs
  const abisPath = path.join(deploymentsDir, `${hre.network.name}-abis.json`);
  fs.writeFileSync(abisPath, JSON.stringify({
    payment: paymentArtifact.abi,
    webhooks: webhooksArtifact.abi
  }, null, 2));
  console.log("   ✓ Contract ABIs saved to:", abisPath);
  
  // Print summary
  console.log("\n========================================");
  console.log("DEPLOYMENT SUMMARY");
  console.log("========================================");
  console.log("Network:", hre.network.name);
  console.log("Chain ID:", hre.network.config.chainId);
  console.log("\nContracts:");
  console.log("- SRPKPayment:", paymentAddress);
  console.log("- SRPKWebhooks:", webhooksAddress);
  console.log("\nPayment Configuration:");
  console.log("- Payment Recipient:", await srpkPayment.paymentRecipient());
  console.log("- Starter Price: $99 (99 USDT)");
  console.log("- Professional Price: $299 (299 USDT)");
  console.log("\nWebhook Configuration:");
  console.log("- Registration Fee:", hre.ethers.formatEther(await srpkWebhooks.webhookFee()), "BNB");
  console.log("- Max Webhooks/User:", await srpkWebhooks.MAX_WEBHOOKS_PER_USER());
  console.log("\n✓ Deployment complete!");
  
  // Instructions
  console.log("\nNext Steps:");
  console.log("1. Update .env with CONTRACT_ADDRESS=" + paymentAddress);
  console.log("2. Update .env with WEBHOOK_CONTRACT_ADDRESS=" + webhooksAddress);
  console.log("3. Copy the Payment ABI from", abisPath, "to CONTRACT_ABI in .env");
  console.log("4. Run 'docker-compose -f docker-compose.crypto.yml up -d' to start services");
}

main()
  .then(() => process.exit(0))
  .catch((error) => {
    console.error(error);
    process.exit(1);
  });