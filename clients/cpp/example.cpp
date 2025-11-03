/**
 * @file example.cpp
 * @brief Example usage of the license client library (C++)
 */

#include "license_client.hpp"
#include <iostream>
#include <thread>
#include <chrono>

using namespace license;

int main(int argc, char* argv[]) {
    const std::string server_url = (argc > 1) ? argv[1] : "http://localhost:8000";
    const std::string tool = "Vector - DaVinci Configurator SE";
    const std::string user = "cpp-client-user";
    
    std::cout << "==========================================="  << std::endl;
    std::cout << "  License Client Example (C++)" << std::endl;
    std::cout << "===========================================" << std::endl;
    std::cout << "Server: " << server_url << std::endl;
    std::cout << "Tool:   " << tool << std::endl;
    std::cout << "User:   " << user << std::endl;
    std::cout << "===========================================" << std::endl << std::endl;
    
    try {
        // Create client
        LicenseClient client(server_url);
        std::cout << "✅ Client initialized" << std::endl << std::endl;
        
        // Get status before borrowing
        auto status = client.get_status(tool);
        std::cout << "📊 Status before borrow:" << std::endl;
        std::cout << "   Total:     " << status.total << std::endl;
        std::cout << "   Borrowed:  " << status.borrowed << std::endl;
        std::cout << "   Available: " << status.available << std::endl << std::endl;
        
        // Borrow a license (RAII - automatically returned when out of scope)
        {
            std::cout << "🎫 Borrowing license..." << std::endl;
            auto handle = client.borrow(tool, user);
            std::cout << "✅ License borrowed successfully" << std::endl;
            std::cout << "   ID: " << handle.id() << std::endl << std::endl;
            
            // Simulate work
            std::cout << "💼 Working with " << tool << " for 5 seconds..." << std::endl;
            std::this_thread::sleep_for(std::chrono::seconds(5));
            
            std::cout << "🔄 License will be automatically returned..." << std::endl;
            // handle automatically returns license when destroyed
        }
        
        std::cout << "✅ License returned (RAII)" << std::endl << std::endl;
        
        // Get status after returning
        status = client.get_status(tool);
        std::cout << "📊 Status after return:" << std::endl;
        std::cout << "   Total:     " << status.total << std::endl;
        std::cout << "   Borrowed:  " << status.borrowed << std::endl;
        std::cout << "   Available: " << status.available << std::endl << std::endl;
        
        std::cout << "✅ Example complete" << std::endl;
        
    } catch (const NoLicensesAvailableException& e) {
        std::cerr << "⚠️  " << e.what() << std::endl;
        return 1;
    } catch (const LicenseException& e) {
        std::cerr << "❌ " << e.what() << std::endl;
        return 1;
    }
    
    return 0;
}

