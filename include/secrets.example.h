/**
 * @file secrets.example.h
 * @brief Template for secrets.h, without real values.
 *
 * Copy this file to include/secrets.h and fill in the values. secrets.h is
 * excluded by .gitignore: never commit credentials, certificates or keys.
 */
#pragma once

namespace secrets {

constexpr char WIFI_SSID[] = "YOUR_WIFI_SSID";
constexpr char WIFI_PASSWORD[] = "YOUR_WIFI_PASSWORD";

// AWS IoT -> Connect -> Domain configurations -> iot:Data-ATS domain name.
constexpr char AWS_IOT_ENDPOINT[] = "xxxxxxxx-ats.iot.us-east-2.amazonaws.com";

// Contents of AmazonRootCA1.pem.
constexpr char ROOT_CA[] = R"PEM(-----BEGIN CERTIFICATE-----
PASTE_ROOT_CA_HERE
-----END CERTIFICATE-----
)PEM";

// Contents of the ...-certificate.pem.crt file.
constexpr char DEVICE_CERTIFICATE[] = R"PEM(-----BEGIN CERTIFICATE-----
PASTE_DEVICE_CERTIFICATE_HERE
-----END CERTIFICATE-----
)PEM";

// Contents of the ...-private.pem.key file.
constexpr char DEVICE_PRIVATE_KEY[] = R"PEM(-----BEGIN RSA PRIVATE KEY-----
PASTE_PRIVATE_KEY_HERE
-----END RSA PRIVATE KEY-----
)PEM";

}  // namespace secrets
