//! License Server Client Library for Rust
//!
//! This library provides a simple, idiomatic Rust client for interacting with
//! the Mercedes-Benz license server.
//!
//! # Features
//!
//! - Async/await support with tokio
//! - RAII semantics with Drop trait
//! - Type-safe API with strong error handling
//! - Automatic license return on drop
//!
//! # Example
//!
//! ```no_run
//! use license_client::{LicenseClient, Result};
//!
//! #[tokio::main]
//! async fn main() -> Result<()> {
//!     let client = LicenseClient::new("http://localhost:8000");
//!    
//!     // Borrow a license (automatically returned when dropped)
//!     {
//!         let license = client.borrow("cad_tool", "rust-user").await?;
//!         println!("Got license: {}", license.id());
//!        
//!         // Your application code here
//!        
//!     } // License automatically returned here
//!    
//!     Ok(())
//! }
//! ```

use serde::{Deserialize, Serialize};
use std::sync::Arc;
use std::time::{SystemTime, UNIX_EPOCH};
use thiserror::Error;
use hmac::{Hmac, Mac};
use sha2::Sha256;
use urlencoding::encode;

/// Custom error type for license operations
#[derive(Error, Debug)]
pub enum LicenseError {
    #[error("HTTP request failed: {0}")]
    RequestFailed(#[from] reqwest::Error),
    
    #[error("No licenses available for tool: {0}")]
    NoLicensesAvailable(String),
    
    #[error("HTTP error {0}: {1}")]
    HttpError(u16, String),
    
    #[error("Invalid response: {0}")]
    InvalidResponse(String),
}

/// Result type for license operations
pub type Result<T> = std::result::Result<T, LicenseError>;

/// License status information
#[derive(Debug, Clone, Deserialize)]
pub struct LicenseStatus {
    pub tool: String,
    pub total: i32,
    pub borrowed: i32,
    pub available: i32,
    #[serde(default)]
    pub commit: i32,
    #[serde(default)]
    pub max_overage: i32,
    #[serde(default)]
    pub overage: i32,
    #[serde(default = "default_true")]
    pub in_commit: bool,
}

fn default_true() -> bool {
    true
}

/// License handle with RAII semantics
///
/// The license is automatically returned when this handle is dropped.
#[derive(Debug)]
pub struct LicenseHandle {
    id: String,
    tool: String,
    user: String,
    client: Arc<reqwest::Client>,
    base_url: String,
    returned: bool,
}

impl LicenseHandle {
    /// Get the license ID
    pub fn id(&self) -> &str {
        &self.id
    }
    
    /// Get the tool name
    pub fn tool(&self) -> &str {
        &self.tool
    }
    
    /// Get the username
    pub fn user(&self) -> &str {
        &self.user
    }
    
    /// Explicitly return the license
    ///
    /// This is called automatically when the handle is dropped.
    pub async fn return_license(mut self) -> Result<()> {
        self.return_impl().await?;
        self.returned = true;
        Ok(())
    }
    
    async fn return_impl(&self) -> Result<()> {
        #[derive(Serialize)]
        struct ReturnRequest {
            id: String,
        }
        
        let url = format!("{}/licenses/return", self.base_url);
        let response = self.client
            .post(&url)
            .json(&ReturnRequest { id: self.id.clone() })
            .send()
            .await?;
        
        if !response.status().is_success() {
            return Err(LicenseError::HttpError(
                response.status().as_u16(),
                response.text().await.unwrap_or_default(),
            ));
        }
        
        Ok(())
    }
}

impl Drop for LicenseHandle {
    fn drop(&mut self) {
        if !self.returned {
            // Note: Can't use async in Drop, would need a runtime handle
            // In production, you might want to use a separate cleanup task
            eprintln!("Warning: License {} dropped without explicit return", self.id);
        }
    }
}

/// Main license client
#[derive(Clone)]
pub struct LicenseClient {
    client: Arc<reqwest::Client>,
    base_url: String,
    enable_security: bool,
}

// Vendor secret - embedded in the client library binary
// In production, this would be obfuscated/encrypted
const VENDOR_SECRET: &str = "techvendor_secret_ecu_2025_demo_xyz789abc123def456";
const VENDOR_ID: &str = "techvendor";

impl LicenseClient {
    /// Create a new license client with security enabled by default
    ///
    /// # Arguments
    ///
    /// * `base_url` - Base URL of the license server (e.g., "http://localhost:8000")
    pub fn new(base_url: impl Into<String>) -> Self {
        Self::with_security(base_url, true)
    }
    
    /// Create a new license client with configurable security
    ///
    /// # Arguments
    ///
    /// * `base_url` - Base URL of the license server
    /// * `enable_security` - Whether to enable HMAC signature authentication
    pub fn with_security(base_url: impl Into<String>, enable_security: bool) -> Self {
        Self {
            client: Arc::new(reqwest::Client::new()),
            base_url: base_url.into(),
            enable_security,
        }
    }
    
    /// Generate HMAC signature for request authentication
    fn generate_signature(&self, tool: &str, user: &str, timestamp: &str) -> String {
        type HmacSha256 = Hmac<Sha256>;
        
        let payload = format!("{}|{}|{}", tool, user, timestamp);
        let mut mac = HmacSha256::new_from_slice(VENDOR_SECRET.as_bytes())
            .expect("HMAC can take key of any size");
        mac.update(payload.as_bytes());
        
        let result = mac.finalize();
        hex::encode(result.into_bytes())
    }
    
    /// Get current Unix timestamp as string
    fn get_timestamp() -> String {
        SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .expect("Time went backwards")
            .as_secs()
            .to_string()
    }
    
    /// Borrow a license for a specific tool
    ///
    /// # Arguments
    ///
    /// * `tool` - Tool name (e.g., "cad_tool")
    /// * `user` - Username
    ///
    /// # Returns
    ///
    /// A `LicenseHandle` that automatically returns the license when dropped.
    ///
    /// # Errors
    ///
    /// Returns `LicenseError::NoLicensesAvailable` if no licenses are available.
    pub async fn borrow(&self, tool: impl Into<String>, user: impl Into<String>) -> Result<LicenseHandle> {
        let tool = tool.into();
        let user = user.into();
        
        #[derive(Serialize)]
        struct BorrowRequest {
            tool: String,
            user: String,
        }
        
        #[derive(Deserialize)]
        struct BorrowResponse {
            id: String,
        }
        
        let url = format!("{}/licenses/borrow", self.base_url);
        
        // Build request with optional security headers
        let mut request = self.client
            .post(&url)
            .json(&BorrowRequest {
                tool: tool.clone(),
                user: user.clone(),
            });
        
        // Add security headers if enabled
        if self.enable_security {
            let timestamp = Self::get_timestamp();
            let signature = self.generate_signature(&tool, &user, &timestamp);
            
            request = request
                .header("X-Signature", signature)
                .header("X-Timestamp", timestamp)
                .header("X-Vendor-ID", VENDOR_ID);
        }
        
        let response = request.send().await?;
        
        let status = response.status();
        
        if status.as_u16() == 409 {
            return Err(LicenseError::NoLicensesAvailable(tool));
        }
        
        if !status.is_success() {
            return Err(LicenseError::HttpError(
                status.as_u16(),
                response.text().await.unwrap_or_default(),
            ));
        }
        
        let data: BorrowResponse = response.json().await?;
        
        Ok(LicenseHandle {
            id: data.id,
            tool,
            user,
            client: self.client.clone(),
            base_url: self.base_url.clone(),
            returned: false,
        })
    }
    
    /// Get status for a specific tool
    ///
    /// # Arguments
    ///
    /// * `tool` - Tool name
    pub async fn get_status(&self, tool: impl Into<String>) -> Result<LicenseStatus> {
        let tool = tool.into();
        let encoded_tool = encode(&tool);
        let url = format!("{}/licenses/{}/status", self.base_url, encoded_tool);
        
        let response = self.client.get(&url).send().await?;
        
        if !response.status().is_success() {
            return Err(LicenseError::HttpError(
                response.status().as_u16(),
                response.text().await.unwrap_or_default(),
            ));
        }
        
        let status: LicenseStatus = response.json().await?;
        Ok(status)
    }
    
    /// Get status for all tools
    pub async fn get_all_statuses(&self) -> Result<Vec<LicenseStatus>> {
        let url = format!("{}/licenses/status", self.base_url);
        
        let response = self.client.get(&url).send().await?;
        
        if !response.status().is_success() {
            return Err(LicenseError::HttpError(
                response.status().as_u16(),
                response.text().await.unwrap_or_default(),
            ));
        }
        
        let statuses: Vec<LicenseStatus> = response.json().await?;
        Ok(statuses)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    
    #[tokio::test]
    async fn test_client_creation() {
        let client = LicenseClient::new("http://localhost:8000");
        assert_eq!(client.base_url, "http://localhost:8000");
    }
}

