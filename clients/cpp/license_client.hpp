/**
 * @file license_client.hpp
 * @brief License Server Client Library for C++
 * 
 * Modern C++ client for borrowing and returning licenses from the
 * Mercedes-Benz license server.
 */

#ifndef LICENSE_CLIENT_HPP
#define LICENSE_CLIENT_HPP

#include <string>
#include <memory>
#include <optional>
#include <stdexcept>
#include <vector>

namespace license {

/**
 * @brief License handle with RAII semantics
 * 
 * Automatically returns the license when destroyed (goes out of scope)
 */
class LicenseHandle {
public:
    LicenseHandle(const std::string& id, const std::string& tool, 
                  const std::string& user);
    ~LicenseHandle();
    
    // Move-only semantics
    LicenseHandle(LicenseHandle&& other) noexcept;
    LicenseHandle& operator=(LicenseHandle&& other) noexcept;
    
    // Deleted copy constructor and assignment
    LicenseHandle(const LicenseHandle&) = delete;
    LicenseHandle& operator=(const LicenseHandle&) = delete;
    
    /**
     * @brief Get the license ID
     */
    const std::string& id() const { return id_; }
    
    /**
     * @brief Get the tool name
     */
    const std::string& tool() const { return tool_; }
    
    /**
     * @brief Get the username
     */
    const std::string& user() const { return user_; }
    
    /**
     * @brief Check if license is valid
     */
    bool is_valid() const { return valid_; }
    
    /**
     * @brief Explicitly return the license (automatic on destruction)
     */
    void return_license();

private:
    std::string id_;
    std::string tool_;
    std::string user_;
    bool valid_;
    
    friend class LicenseClient;
};

/**
 * @brief License status information
 */
struct LicenseStatus {
    std::string tool;
    int total = 0;
    int borrowed = 0;
    int available = 0;
    int commit = 0;
    int max_overage = 0;
    int overage = 0;
    bool in_commit = true;
};

/**
 * @brief Exception thrown when license operations fail
 */
class LicenseException : public std::runtime_error {
public:
    explicit LicenseException(const std::string& message)
        : std::runtime_error(message) {}
};

/**
 * @brief Exception thrown when no licenses are available
 */
class NoLicensesAvailableException : public LicenseException {
public:
    explicit NoLicensesAvailableException(const std::string& tool)
        : LicenseException("No licenses available for tool: " + tool) {}
};

/**
 * @brief Main license client class
 */
class LicenseClient {
public:
    /**
     * @brief Construct a license client
     * 
     * @param base_url Base URL of the license server
     */
    explicit LicenseClient(const std::string& base_url);
    
    /**
     * @brief Destructor
     */
    ~LicenseClient();
    
    /**
     * @brief Borrow a license for a specific tool
     * 
     * @param tool Tool name (e.g., "cad_tool")
     * @param user Username
     * @return LicenseHandle that automatically returns the license when destroyed
     * @throws NoLicensesAvailableException if no licenses available
     * @throws LicenseException on other errors
     */
    LicenseHandle borrow(const std::string& tool, const std::string& user);
    
    /**
     * @brief Return a borrowed license
     * 
     * @param handle License handle to return
     * @throws LicenseException on error
     */
    void return_license(const LicenseHandle& handle);
    
    /**
     * @brief Get status for a specific tool
     * 
     * @param tool Tool name
     * @return License status information
     * @throws LicenseException on error
     */
    LicenseStatus get_status(const std::string& tool);
    
    /**
     * @brief Get all license statuses
     * 
     * @return Vector of license statuses for all tools
     * @throws LicenseException on error
     */
    std::vector<LicenseStatus> get_all_statuses();

private:
    class Impl;
    std::unique_ptr<Impl> pimpl_;
};

} // namespace license

#endif // LICENSE_CLIENT_HPP

