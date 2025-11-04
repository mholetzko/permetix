/**
 * @file license_client.cpp
 * @brief Implementation of License Server Client Library for C++
 */

#include "license_client.hpp"
#include <curl/curl.h>
#include <json/json.h>
#include <sstream>
#include <iomanip>
#include <chrono>
#include <openssl/hmac.h>
#include <openssl/sha.h>

namespace license {

// Helper for CURL response handling
struct Response {
    std::string data;
    long http_code = 0;
};

static size_t write_callback(void* contents, size_t size, size_t nmemb, void* userp) {
    ((std::string*)userp)->append((char*)contents, size * nmemb);
    return size * nmemb;
}

// Vendor secret - embedded in the client library binary
// In production, this would be obfuscated/encrypted
static const std::string VENDOR_SECRET = "techvendor_secret_ecu_2025_demo_xyz789abc123def456";
static const std::string VENDOR_ID = "techvendor";

// PIMPL implementation
class LicenseClient::Impl {
public:
    std::string base_url;
    CURL* curl;
    bool enable_security;
    std::string api_key;
    
    Impl(const std::string& url, bool security = true) 
        : base_url(url), enable_security(security) {
        curl_global_init(CURL_GLOBAL_DEFAULT);
        curl = curl_easy_init();
        if (!curl) {
            throw LicenseException("Failed to initialize CURL");
        }
        const char* env_key = std::getenv("LICENSE_API_KEY");
        if (env_key) {
            api_key = env_key;
        }
    }
    
    ~Impl() {
        if (curl) {
            curl_easy_cleanup(curl);
        }
        // Note: avoid curl_global_cleanup to prevent segfaults due to
        // static destructor ordering in some environments
    }
    
    // Generate HMAC-SHA256 signature
    std::string generate_signature(const std::string& tool, 
                                   const std::string& user, 
                                   const std::string& timestamp) {
        std::string payload;
        if (!api_key.empty()) {
            payload = tool + "|" + user + "|" + timestamp + "|" + api_key;
        } else {
            payload = tool + "|" + user + "|" + timestamp;
        }
        
        unsigned char* digest = HMAC(EVP_sha256(),
                                     VENDOR_SECRET.c_str(), VENDOR_SECRET.length(),
                                     (unsigned char*)payload.c_str(), payload.length(),
                                     nullptr, nullptr);
        
        // Convert to hex string
        std::stringstream ss;
        for (int i = 0; i < SHA256_DIGEST_LENGTH; i++) {
            ss << std::hex << std::setw(2) << std::setfill('0') << (int)digest[i];
        }
        return ss.str();
    }
    
    // Get current Unix timestamp as string
    std::string get_timestamp() {
        auto now = std::chrono::system_clock::now();
        auto seconds = std::chrono::duration_cast<std::chrono::seconds>(
            now.time_since_epoch()
        ).count();
        return std::to_string(seconds);
    }
    
    Response http_post(const std::string& endpoint, const std::string& json_data,
                       const std::string& tool = "", const std::string& user = "") {
        Response response;
        std::string url = base_url + endpoint;
        
        curl_easy_setopt(curl, CURLOPT_URL, url.c_str());
        curl_easy_setopt(curl, CURLOPT_POSTFIELDS, json_data.c_str());
        curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, write_callback);
        curl_easy_setopt(curl, CURLOPT_WRITEDATA, &response.data);
        
        struct curl_slist* headers = nullptr;
        headers = curl_slist_append(headers, "Content-Type: application/json");
        
        // Add security headers if enabled and tool/user provided
        if (enable_security && !tool.empty() && !user.empty()) {
            std::string timestamp = get_timestamp();
            std::string signature = generate_signature(tool, user, timestamp);
            
            std::string sig_header = "X-Signature: " + signature;
            std::string ts_header = "X-Timestamp: " + timestamp;
            std::string vendor_header = "X-Vendor-ID: " + VENDOR_ID;
            
            headers = curl_slist_append(headers, sig_header.c_str());
            headers = curl_slist_append(headers, ts_header.c_str());
            headers = curl_slist_append(headers, vendor_header.c_str());
            if (!api_key.empty()) {
                std::string auth_header = "Authorization: Bearer " + api_key;
                headers = curl_slist_append(headers, auth_header.c_str());
            }
        }
        
        curl_easy_setopt(curl, CURLOPT_HTTPHEADER, headers);
        
        CURLcode res = curl_easy_perform(curl);
        curl_slist_free_all(headers);
        
        if (res != CURLE_OK) {
            throw LicenseException(std::string("CURL error: ") + curl_easy_strerror(res));
        }
        
        curl_easy_getinfo(curl, CURLINFO_RESPONSE_CODE, &response.http_code);
        return response;
    }
    
    Response http_get(const std::string& endpoint) {
        Response response;
        std::string url = base_url + endpoint;
        
        curl_easy_setopt(curl, CURLOPT_URL, url.c_str());
        curl_easy_setopt(curl, CURLOPT_HTTPGET, 1L);
        curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, write_callback);
        curl_easy_setopt(curl, CURLOPT_WRITEDATA, &response.data);
        
        CURLcode res = curl_easy_perform(curl);
        
        if (res != CURLE_OK) {
            throw LicenseException(std::string("CURL error: ") + curl_easy_strerror(res));
        }
        
        curl_easy_getinfo(curl, CURLINFO_RESPONSE_CODE, &response.http_code);
        return response;
    }
};

// LicenseHandle implementation
LicenseHandle::LicenseHandle(const std::string& id, const std::string& tool, 
                             const std::string& user)
    : id_(id), tool_(tool), user_(user), valid_(true) {}

LicenseHandle::~LicenseHandle() {
    if (valid_) {
        try {
            return_license();
        } catch (...) {
            // Suppress exceptions in destructor
        }
    }
}

LicenseHandle::LicenseHandle(LicenseHandle&& other) noexcept
    : id_(std::move(other.id_))
    , tool_(std::move(other.tool_))
    , user_(std::move(other.user_))
    , valid_(other.valid_) {
    other.valid_ = false;
}

LicenseHandle& LicenseHandle::operator=(LicenseHandle&& other) noexcept {
    if (this != &other) {
        if (valid_) {
            try {
                return_license();
            } catch (...) {}
        }
        id_ = std::move(other.id_);
        tool_ = std::move(other.tool_);
        user_ = std::move(other.user_);
        valid_ = other.valid_;
        other.valid_ = false;
    }
    return *this;
}

void LicenseHandle::return_license() {
    if (!valid_) return;
    
    // Note: This would need a reference to the client to actually return
    // For now, mark as invalid
    valid_ = false;
}

// LicenseClient implementation
LicenseClient::LicenseClient(const std::string& base_url)
    : pimpl_(std::make_unique<Impl>(base_url)) {}

LicenseClient::~LicenseClient() = default;

LicenseHandle LicenseClient::borrow(const std::string& tool, const std::string& user) {
    Json::Value request;
    request["tool"] = tool;
    request["user"] = user;
    
    Json::StreamWriterBuilder writer;
    std::string json_data = Json::writeString(writer, request);
    
    // Pass tool and user for HMAC signature generation
    auto response = pimpl_->http_post("/licenses/borrow", json_data, tool, user);
    
    if (response.http_code == 409) {
        throw NoLicensesAvailableException(tool);
    }
    
    if (response.http_code != 200) {
        throw LicenseException("HTTP error: " + std::to_string(response.http_code));
    }
    
    Json::Value json_response;
    Json::CharReaderBuilder reader;
    std::istringstream iss(response.data);
    std::string errs;
    
    if (!Json::parseFromStream(reader, iss, &json_response, &errs)) {
        throw LicenseException("Failed to parse response: " + errs);
    }
    
    std::string id = json_response["id"].asString();
    return LicenseHandle(id, tool, user);
}

void LicenseClient::return_license(const LicenseHandle& handle) {
    if (!handle.is_valid()) {
        throw LicenseException("Invalid license handle");
    }
    
    Json::Value request;
    request["id"] = handle.id();
    
    Json::StreamWriterBuilder writer;
    std::string json_data = Json::writeString(writer, request);
    
    auto response = pimpl_->http_post("/licenses/return", json_data);
    
    if (response.http_code != 200) {
        throw LicenseException("HTTP error: " + std::to_string(response.http_code));
    }
}

LicenseStatus LicenseClient::get_status(const std::string& tool) {
    // URL-encode tool using curl
    char* escaped = curl_easy_escape(pimpl_->curl, tool.c_str(), static_cast<int>(tool.size()));
    std::string encoded_tool = escaped ? std::string(escaped) : tool;
    if (escaped) curl_free(escaped);
    auto response = pimpl_->http_get("/licenses/" + encoded_tool + "/status");
    
    if (response.http_code != 200) {
        throw LicenseException("HTTP error: " + std::to_string(response.http_code));
    }
    
    Json::Value json_response;
    Json::CharReaderBuilder reader;
    std::istringstream iss(response.data);
    std::string errs;
    
    if (!Json::parseFromStream(reader, iss, &json_response, &errs)) {
        throw LicenseException("Failed to parse response: " + errs);
    }
    
    LicenseStatus status;
    status.tool = json_response["tool"].asString();
    status.total = json_response["total"].asInt();
    status.borrowed = json_response["borrowed"].asInt();
    status.available = json_response["available"].asInt();
    status.commit = json_response.get("commit", 0).asInt();
    status.max_overage = json_response.get("max_overage", 0).asInt();
    status.overage = json_response.get("overage", 0).asInt();
    status.in_commit = json_response.get("in_commit", true).asBool();
    
    return status;
}

std::vector<LicenseStatus> LicenseClient::get_all_statuses() {
    auto response = pimpl_->http_get("/licenses/status");
    
    if (response.http_code != 200) {
        throw LicenseException("HTTP error: " + std::to_string(response.http_code));
    }
    
    Json::Value json_response;
    Json::CharReaderBuilder reader;
    std::istringstream iss(response.data);
    std::string errs;
    
    if (!Json::parseFromStream(reader, iss, &json_response, &errs)) {
        throw LicenseException("Failed to parse response: " + errs);
    }
    
    std::vector<LicenseStatus> statuses;
    for (const auto& item : json_response) {
        LicenseStatus status;
        status.tool = item["tool"].asString();
        status.total = item["total"].asInt();
        status.borrowed = item["borrowed"].asInt();
        status.available = item["available"].asInt();
        status.commit = item.get("commit", 0).asInt();
        status.max_overage = item.get("max_overage", 0).asInt();
        status.overage = item.get("overage", 0).asInt();
        status.in_commit = item.get("in_commit", true).asBool();
        statuses.push_back(status);
    }
    
    return statuses;
}

} // namespace license

