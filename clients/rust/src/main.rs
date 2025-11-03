//! Example usage of the license client library

use license_client::{LicenseClient, LicenseError, Result};
use std::env;
use tokio::time::{sleep, Duration};

#[tokio::main]
async fn main() -> Result<()> {
    let server_url = env::args()
        .nth(1)
        .unwrap_or_else(|| "http://localhost:8000".to_string());
    
    let tool = "Vector - DaVinci Configurator SE";
    let user = "rust-client-user";
    
    println!("===========================================");
    println!("  License Client Example (Rust)");
    println!("===========================================");
    println!("Server: {}", server_url);
    println!("Tool:   {}", tool);
    println!("User:   {}", user);
    println!("===========================================\n");
    
    // Create client
    let client = LicenseClient::new(server_url);
    println!("✅ Client initialized\n");
    
    // Get status before borrowing
    match client.get_status(tool).await {
        Ok(status) => {
            println!("📊 Status before borrow:");
            println!("   Total:     {}", status.total);
            println!("   Borrowed:  {}", status.borrowed);
            println!("   Available: {}\n", status.available);
        }
        Err(e) => eprintln!("⚠️  Could not get status: {}\n", e),
    }
    
    // Borrow a license (RAII - automatically returned when dropped)
    println!("🎫 Borrowing license...");
    match client.borrow(tool, user).await {
        Ok(license) => {
            println!("✅ License borrowed successfully");
            println!("   ID: {}\n", license.id());
            
            // Simulate work
            println!("💼 Working with {} for 5 seconds...", tool);
            sleep(Duration::from_secs(5)).await;
            
            println!("🔄 Explicitly returning license...");
            license.return_license().await?;
            println!("✅ License returned\n");
        }
        Err(LicenseError::NoLicensesAvailable(t)) => {
            eprintln!("⚠️  No licenses available for {}", t);
            return Ok(());
        }
        Err(e) => {
            eprintln!("❌ Failed to borrow license: {}", e);
            return Err(e);
        }
    }
    
    // Get status after returning
    match client.get_status(tool).await {
        Ok(status) => {
            println!("📊 Status after return:");
            println!("   Total:     {}", status.total);
            println!("   Borrowed:  {}", status.borrowed);
            println!("   Available: {}\n", status.available);
        }
        Err(e) => eprintln!("⚠️  Could not get status: {}\n", e),
    }
    
    println!("✅ Example complete");
    
    Ok(())
}
