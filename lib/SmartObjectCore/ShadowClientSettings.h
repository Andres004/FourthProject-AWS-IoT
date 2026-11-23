/**
 * @file ShadowClientSettings.h
 * @brief AWS IoT connection data of one board.
 */
#pragma once

/**
 * @brief Endpoint, certificates and Thing suffix used by ShadowClient.
 *
 * Values come from the board's secrets_<board>.h (never committed) and its
 * config_<board>.h. Every string must outlive the client that uses it.
 */
struct ShadowClientSettings {
  const char* endpoint;     ///< iot:Data-ATS domain name
  const char* rootCa;       ///< AmazonRootCA1.pem contents
  const char* certificate;  ///< Device certificate (PEM)
  const char* privateKey;   ///< Device private key (PEM)
  const char* thingSuffix;  ///< "-vent" or "-lights"
};
