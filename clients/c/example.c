/**
 * @file example.c
 * @brief Example usage of the license client library
 */

#include "license_client.h"
#include <stdio.h>
#include <unistd.h>

int main(int argc, char *argv[]) {
    const char *server_url = "http://localhost:8000";
    const char *tool = "ECU Development Suite";
    const char *user = "c-client-user";
    
    // Allow custom server URL from command line
    if (argc > 1) {
        server_url = argv[1];
    }
    
    printf("===========================================\n");
    printf("  License Client Example (C)\n");
    printf("===========================================\n");
    printf("Server: %s\n", server_url);
    printf("Tool:   %s\n", tool);
    printf("User:   %s\n", user);
    printf("===========================================\n\n");
    
    // Initialize client
    if (license_client_init(server_url) != 0) {
        fprintf(stderr, "❌ Failed to initialize client: %s\n", 
                license_get_error());
        return 1;
    }
    
    printf("✅ Client initialized\n\n");
    
    // Get status before borrowing
    license_status_t status;
    if (license_get_status(tool, &status) == 0) {
        printf("📊 Status before borrow:\n");
        printf("   Total:     %d\n", status.total);
        printf("   Borrowed:  %d\n", status.borrowed);
        printf("   Available: %d\n\n", status.available);
    }
    
    // Borrow a license
    license_handle_t handle = {0};
    printf("🎫 Borrowing license...\n");
    int result = license_borrow(tool, user, &handle);
    
    if (result == 0) {
        printf("✅ License borrowed successfully\n");
        printf("   ID: %s\n\n", handle.id);
        
        // Simulate work
        printf("💼 Working with %s for 5 seconds...\n", tool);
        sleep(5);
        
        // Return the license
        printf("🔄 Returning license...\n");
        if (license_return(&handle) == 0) {
            printf("✅ License returned successfully\n\n");
        } else {
            fprintf(stderr, "❌ Failed to return license: %s\n", 
                    license_get_error());
        }
    } else if (result == -2) {
        fprintf(stderr, "⚠️  No licenses available\n");
    } else {
        fprintf(stderr, "❌ Failed to borrow license: %s\n", 
                license_get_error());
    }
    
    // Get status after returning
    if (license_get_status(tool, &status) == 0) {
        printf("📊 Status after return:\n");
        printf("   Total:     %d\n", status.total);
        printf("   Borrowed:  %d\n", status.borrowed);
        printf("   Available: %d\n\n", status.available);
    }
    
    // Cleanup
    license_client_cleanup();
    printf("✅ Client cleaned up\n");
    
    return 0;
}

