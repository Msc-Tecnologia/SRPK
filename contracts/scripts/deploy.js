const hre = require("hardhat");

async function main() {
  console.log("Deploying SRPKPayment contract...");

  // Get the contract factory
  const SRPKPayment = await hre.ethers.getContractFactory("SRPKPayment");
  
  // Deploy the contract
  const srpkPayment = await SRPKPayment.deploy();
  
  // Wait for deployment to finish
  await srpkPayment.waitForDeployment();
  
  const contractAddress = await srpkPayment.getAddress();
  
  console.log("SRPKPayment deployed to:", contractAddress);
  console.log("Payment recipient:", await srpkPayment.paymentRecipient());
  
  // Wait for a few block confirmations before verifying
  console.log("Waiting for block confirmations...");
  await srpkPayment.deploymentTransaction().wait(5);
  
  // Verify the contract on BscScan
  if (hre.network.name !== "hardhat" && hre.network.name !== "localhost") {
    console.log("Verifying contract on BscScan...");
    try {
      await hre.run("verify:verify", {
        address: contractAddress,
        constructorArguments: [],
      });
      console.log("Contract verified successfully!");
    } catch (error) {
      console.error("Error verifying contract:", error);
    }
  }
  
  // Save deployment info
  const fs = require("fs");
  const deploymentInfo = {
    network: hre.network.name,
    contractAddress: contractAddress,
    deploymentTime: new Date().toISOString(),
    paymentRecipient: await srpkPayment.paymentRecipient(),
    starterPrice: (await srpkPayment.STARTER_PRICE()).toString(),
    professionalPrice: (await srpkPayment.PROFESSIONAL_PRICE()).toString()
  };
  
  fs.writeFileSync(
    `./deployments/${hre.network.name}-deployment.json`,
    JSON.stringify(deploymentInfo, null, 2)
  );
  
  console.log("Deployment info saved to:", `./deployments/${hre.network.name}-deployment.json`);
}

main()
  .then(() => process.exit(0))
  .catch((error) => {
    console.error(error);
    process.exit(1);
  });