/**
 * @file license_client.c
 * @brief Implementation of License Server Client Library for C
 */

#include "license_client.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <curl/curl.h>

static char g_base_url[256] = {0};
static char g_error_msg[512] = {0};
static CURL *g_curl = NULL;
static char g_api_key[256] = {0};

typedef struct {
    char *data;
    size_t size;
} response_buffer_t;

static size_t write_callback(void *contents, size_t size, size_t nmemb, void *userp) {
    size_t realsize = size * nmemb;
    response_buffer_t *buf = (response_buffer_t *)userp;
    
    char *ptr = realloc(buf->data, buf->size + realsize + 1);
    if (ptr == NULL) {
        return 0;
    }
    
    buf->data = ptr;
    memcpy(&(buf->data[buf->size]), contents, realsize);
    buf->size += realsize;
    buf->data[buf->size] = 0;
    
    return realsize;
}

int license_client_init(const char *base_url) {
    if (base_url == NULL) {
        snprintf(g_error_msg, sizeof(g_error_msg), "Base URL cannot be NULL");
        return -1;
    }
    
    strncpy(g_base_url, base_url, sizeof(g_base_url) - 1);
    const char *env_key = getenv("LICENSE_API_KEY");
    if (env_key) {
        strncpy(g_api_key, env_key, sizeof(g_api_key) - 1);
    }
    
    curl_global_init(CURL_GLOBAL_DEFAULT);
    g_curl = curl_easy_init();
    
    if (g_curl == NULL) {
        snprintf(g_error_msg, sizeof(g_error_msg), "Failed to initialize CURL");
        return -1;
    }
    
    return 0;
}

void license_client_cleanup(void) {
    if (g_curl) {
        curl_easy_cleanup(g_curl);
        g_curl = NULL;
    }
    curl_global_cleanup();
}

int license_borrow(const char *tool, const char *user, license_handle_t *handle) {
    if (tool == NULL || user == NULL || handle == NULL) {
        snprintf(g_error_msg, sizeof(g_error_msg), "Invalid parameters");
        return -1;
    }
    
    char url[512];
    snprintf(url, sizeof(url), "%s/licenses/borrow", g_base_url);
    
    char post_data[256];
    snprintf(post_data, sizeof(post_data), 
             "{\"tool\":\"%s\",\"user\":\"%s\"}", tool, user);
    
    response_buffer_t response = {0};
    
    curl_easy_setopt(g_curl, CURLOPT_URL, url);
    curl_easy_setopt(g_curl, CURLOPT_POSTFIELDS, post_data);
    curl_easy_setopt(g_curl, CURLOPT_WRITEFUNCTION, write_callback);
    curl_easy_setopt(g_curl, CURLOPT_WRITEDATA, (void *)&response);
    
    struct curl_slist *headers = NULL;
    headers = curl_slist_append(headers, "Content-Type: application/json");
    if (g_api_key[0] != '\0') {
        char auth_header[320];
        snprintf(auth_header, sizeof(auth_header), "Authorization: Bearer %s", g_api_key);
        headers = curl_slist_append(headers, auth_header);
    }
    curl_easy_setopt(g_curl, CURLOPT_HTTPHEADER, headers);
    
    CURLcode res = curl_easy_perform(g_curl);
    curl_slist_free_all(headers);
    
    if (res != CURLE_OK) {
        snprintf(g_error_msg, sizeof(g_error_msg), 
                 "CURL error: %s", curl_easy_strerror(res));
        free(response.data);
        return -1;
    }
    
    long http_code = 0;
    curl_easy_getinfo(g_curl, CURLINFO_RESPONSE_CODE, &http_code);
    
    if (http_code == 409) {
        snprintf(g_error_msg, sizeof(g_error_msg), "No licenses available");
        free(response.data);
        return -2;
    }
    
    if (http_code != 200) {
        snprintf(g_error_msg, sizeof(g_error_msg), 
                 "HTTP error: %ld", http_code);
        free(response.data);
        return -1;
    }
    
    // Parse JSON response (simple parsing for "id" field)
    char *id_start = strstr(response.data, "\"id\":\"");
    if (id_start) {
        id_start += 6;
        char *id_end = strchr(id_start, '\"');
        if (id_end) {
            size_t len = id_end - id_start;
            if (len < sizeof(handle->id)) {
                strncpy(handle->id, id_start, len);
                handle->id[len] = '\0';
                strncpy(handle->tool, tool, sizeof(handle->tool) - 1);
                strncpy(handle->user, user, sizeof(handle->user) - 1);
                handle->valid = 1;
            }
        }
    }
    
    free(response.data);
    
    if (!handle->valid) {
        snprintf(g_error_msg, sizeof(g_error_msg), "Failed to parse response");
        return -1;
    }
    
    return 0;
}

int license_return(const license_handle_t *handle) {
    if (handle == NULL || !handle->valid) {
        snprintf(g_error_msg, sizeof(g_error_msg), "Invalid handle");
        return -1;
    }
    
    char url[512];
    snprintf(url, sizeof(url), "%s/licenses/return", g_base_url);
    
    char post_data[256];
    snprintf(post_data, sizeof(post_data), "{\"id\":\"%s\"}", handle->id);
    
    response_buffer_t response = {0};
    
    curl_easy_setopt(g_curl, CURLOPT_URL, url);
    curl_easy_setopt(g_curl, CURLOPT_POSTFIELDS, post_data);
    curl_easy_setopt(g_curl, CURLOPT_WRITEFUNCTION, write_callback);
    curl_easy_setopt(g_curl, CURLOPT_WRITEDATA, (void *)&response);
    
    struct curl_slist *headers = NULL;
    headers = curl_slist_append(headers, "Content-Type: application/json");
    if (g_api_key[0] != '\0') {
        char auth_header[320];
        snprintf(auth_header, sizeof(auth_header), "Authorization: Bearer %s", g_api_key);
        headers = curl_slist_append(headers, auth_header);
    }
    curl_easy_setopt(g_curl, CURLOPT_HTTPHEADER, headers);
    
    CURLcode res = curl_easy_perform(g_curl);
    curl_slist_free_all(headers);
    
    free(response.data);
    
    if (res != CURLE_OK) {
        snprintf(g_error_msg, sizeof(g_error_msg), 
                 "CURL error: %s", curl_easy_strerror(res));
        return -1;
    }
    
    long http_code = 0;
    curl_easy_getinfo(g_curl, CURLINFO_RESPONSE_CODE, &http_code);
    
    if (http_code != 200) {
        snprintf(g_error_msg, sizeof(g_error_msg), 
                 "HTTP error: %ld", http_code);
        return -1;
    }
    
    return 0;
}

int license_get_status(const char *tool, license_status_t *status) {
    if (tool == NULL || status == NULL) {
        snprintf(g_error_msg, sizeof(g_error_msg), "Invalid parameters");
        return -1;
    }
    
    char url[1024];
    // URL-encode tool using curl
    char *escaped = curl_easy_escape(g_curl, tool, (int)strlen(tool));
    snprintf(url, sizeof(url), "%s/licenses/%s/status", g_base_url, escaped ? escaped : tool);
    if (escaped) curl_free(escaped);
    
    response_buffer_t response = {0};
    
    curl_easy_setopt(g_curl, CURLOPT_URL, url);
    curl_easy_setopt(g_curl, CURLOPT_HTTPGET, 1L);
    curl_easy_setopt(g_curl, CURLOPT_WRITEFUNCTION, write_callback);
    curl_easy_setopt(g_curl, CURLOPT_WRITEDATA, (void *)&response);
    
    CURLcode res = curl_easy_perform(g_curl);
    
    if (res != CURLE_OK) {
        snprintf(g_error_msg, sizeof(g_error_msg), 
                 "CURL error: %s", curl_easy_strerror(res));
        free(response.data);
        return -1;
    }
    
    // Simple JSON parsing
    strncpy(status->tool, tool, sizeof(status->tool) - 1);
    
    char *total_str = strstr(response.data, "\"total\":");
    if (total_str) sscanf(total_str + 8, "%d", &status->total);
    
    char *borrowed_str = strstr(response.data, "\"borrowed\":");
    if (borrowed_str) sscanf(borrowed_str + 11, "%d", &status->borrowed);
    
    char *available_str = strstr(response.data, "\"available\":");
    if (available_str) sscanf(available_str + 12, "%d", &status->available);
    
    free(response.data);
    return 0;
}

const char* license_get_error(void) {
    return g_error_msg;
}

